import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Section } from "@/components/ui/Section";
import { SelectField } from "@/components/ui/SelectField";
import { Switch } from "@/components/ui/Switch";
import { useToast } from "@/components/feedback/ToastProvider";
import { useDevSession } from "@/hooks/useDevSession";
import { extractErrorMessage } from "@/lib/errorMessage";
import { getFeatureFlags, updateFeatureFlags } from "@/services/api/administration";
import {
  ImageRecognitionProvider,
  LlmProvider,
  SentimentAnalysisProvider,
} from "@/types/enums.generated";
import type { FeatureFlags } from "@/types/featureFlags";

const LLM_PROVIDER_OPTIONS = [
  { value: LlmProvider.OPENAI, label: "OpenAI (GPT)" },
  { value: LlmProvider.BEDROCK, label: "Amazon Bedrock" },
  { value: LlmProvider.GEMINI, label: "Google Gemini" },
];

const IMAGE_RECOGNITION_PROVIDER_OPTIONS = [
  { value: ImageRecognitionProvider.AWS_REKOGNITION, label: "Amazon Rekognition Image" },
  { value: ImageRecognitionProvider.AZURE_VISION, label: "Azure AI Vision" },
];

const SENTIMENT_ANALYSIS_PROVIDER_OPTIONS = [
  { value: SentimentAnalysisProvider.AWS_COMPREHEND, label: "Amazon Comprehend" },
  { value: SentimentAnalysisProvider.AZURE_LANGUAGE, label: "Azure AI Language" },
];

/**
 * Tela de feature flags (rota `/admin/feature-flags`, acesso restrito a
 * administrador). Permite, sem reiniciar o backend: ligar/desligar o uso
 * de LLM real (OpenAI/Gemini) e
 * escolher o modelo, ligar/desligar cada modalidade de midia aceita em
 * novas analises, e ligar/desligar YOLOv8/OpenPose de forma independente
 * (ver `app.feature_flags`).
 *
 * Estado local (`draft`) separado do estado persistido (`query.data`):
 * o formulario acumula mudancas antes de salvar, permitindo trocar varios
 * campos (ex.: desligar OpenAI e ligar Gemini) em uma unica operacao
 * atomica, em vez de uma chamada PATCH por clique.
 */
export function FeatureFlagsPage() {
  const { subject } = useDevSession();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [draft, setDraft] = useState<FeatureFlags | null>(null);

  const query = useQuery({
    queryKey: ["admin", "feature-flags", subject],
    queryFn: () => getFeatureFlags(subject as string),
    enabled: Boolean(subject),
  });

  useEffect(() => {
    if (query.data) setDraft(query.data);
  }, [query.data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!draft) throw new Error("Nada para salvar.");
      return updateFeatureFlags(subject as string, {
        llm_provider_enabled: draft.llm_provider_enabled,
        llm_provider: draft.llm_provider,
        llm_openai_model: draft.llm_openai_model,
        llm_bedrock_model: draft.llm_bedrock_model,
        llm_gemini_model: draft.llm_gemini_model,
        modality_audio_enabled: draft.modality_audio_enabled,
        modality_video_enabled: draft.modality_video_enabled,
        modality_image_enabled: draft.modality_image_enabled,
        vision_detection_enabled: draft.vision_detection_enabled,
        vision_pose_enabled: draft.vision_pose_enabled,
        image_recognition_enabled: draft.image_recognition_enabled,
        image_recognition_provider: draft.image_recognition_provider,
        vision_rekognition_video_enabled: draft.vision_rekognition_video_enabled,
        sentiment_analysis_enabled: draft.sentiment_analysis_enabled,
        sentiment_analysis_provider: draft.sentiment_analysis_provider,
        auto_clinical_support_enabled: draft.auto_clinical_support_enabled,
      });
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["admin", "feature-flags", subject], updated);
      setDraft(updated);
      showSuccess("Alterações salvas com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível salvar as alterações."));
    },
  });

  if (!subject) {
    return <EmptyState title="Configure o usuario de desenvolvimento primeiro." />;
  }

  if (query.isLoading || !draft) return <Skeleton rows={6} />;

  if (query.isError) {
    return (
      <ErrorState
        description={(query.error as Error).message}
        onRetry={() => query.refetch()}
      />
    );
  }

  function update<K extends keyof FeatureFlags>(key: K, value: FeatureFlags[K]) {
    setDraft((current) => (current ? { ...current, [key]: value } : current));
  }

  const modelOptionsByProvider: Record<LlmProvider, typeof draft.openai_model_options> = {
    [LlmProvider.LOCAL]: [],
    [LlmProvider.OPENAI]: draft.openai_model_options,
    [LlmProvider.BEDROCK]: draft.bedrock_model_options,
    [LlmProvider.GEMINI]: draft.gemini_model_options,
  };
  const selectedModelByProvider: Record<LlmProvider, string> = {
    [LlmProvider.LOCAL]: "",
    [LlmProvider.OPENAI]: draft.llm_openai_model,
    [LlmProvider.BEDROCK]: draft.llm_bedrock_model,
    [LlmProvider.GEMINI]: draft.llm_gemini_model,
  };
  const modelFieldByProvider: Record<LlmProvider, keyof FeatureFlags | null> = {
    [LlmProvider.LOCAL]: null,
    [LlmProvider.OPENAI]: "llm_openai_model",
    [LlmProvider.BEDROCK]: "llm_bedrock_model",
    [LlmProvider.GEMINI]: "llm_gemini_model",
  };
  const modelOptions = modelOptionsByProvider[draft.llm_provider];
  const selectedModel = selectedModelByProvider[draft.llm_provider];

  return (
    <>
      <PageHeader
        title="Feature flags"
        description="Ligue ou desligue integrações de IA e modalidades de mídia sem reiniciar o sistema. Alterações são registradas em auditoria."
        action={
          <Button
            type="button"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending ? "Salvando..." : "Salvar alterações"}
          </Button>
        }
      />

      <Section
        title="Modelo de linguagem (LLM)"
        description="Consolidação de risco e apoio à análise clínica assistidos por IA. Desligado, o sistema usa um resumo determinístico local, sem chamada de rede."
      >
        <Switch
          id="llm-provider-enabled"
          label="Usar LLM real"
          hint="Quando desligado, ignora o provedor escolhido abaixo e usa o template local."
          checked={draft.llm_provider_enabled}
          onChange={(checked) => update("llm_provider_enabled", checked)}
        />

        <SelectField
          id="llm-provider"
          label="Provedor"
          options={LLM_PROVIDER_OPTIONS}
          value={draft.llm_provider}
          onChange={(event) => update("llm_provider", event.target.value as LlmProvider)}
          disabled={!draft.llm_provider_enabled}
        />

        <SelectField
          id="llm-model"
          label="Modelo"
          options={modelOptions}
          value={selectedModel}
          onChange={(event) => {
            const field = modelFieldByProvider[draft.llm_provider];
            if (field) update(field, event.target.value);
          }}
          disabled={!draft.llm_provider_enabled}
        />

        {draft.llm_provider === LlmProvider.BEDROCK && (
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
            Usa as credenciais IAM do processo (mesmas de S3/SQS/Transcribe/Rekognition) - não
            depende de uma chave de API externa. Requer a permissão <code>bedrock:InvokeModel</code>{" "}
            concedida e o acesso ao modelo liberado no console Bedrock da conta/região.
          </p>
        )}

        {draft.llm_provider === LlmProvider.GEMINI && !draft.gemini_implemented && (
          <div
            role="alert"
            style={{
              display: "flex",
              gap: "var(--space-2)",
              alignItems: "flex-start",
              padding: "var(--space-3)",
              borderRadius: "var(--radius-field)",
              background: "var(--tag-warning-bg)",
              color: "var(--tag-warning-text)",
              fontSize: "var(--font-size-sm)",
            }}
          >
            <AlertTriangle size={16} strokeWidth={2} aria-hidden="true" style={{ flexShrink: 0, marginTop: 2 }} />
            <span>
              A integração com Google Gemini ainda não foi implementada neste projeto. Você pode
              salvar esta preferência para planejamento, mas chamadas de IA falharão até que o
              adaptador real exista.
            </span>
          </div>
        )}
      </Section>

      <Section
        title="Apoio à análise clínica (IA) automático"
        description="Quando ligado, o resumo de apoio à análise clínica é gerado automaticamente ao final do processamento de cada análise, sem precisar clicar no botão manual na tela de revisão. Só executa quando há conteúdo clinicamente relevante identificado (dados clínicos estruturados, achado confirmado como relevante pelo Rekognition, termo clínico em texto/transcrição, ou análise acústica de voz) - nunca só porque a análise tem mídia. Desligado, nenhuma chamada automática ao LLM ocorre para este propósito (equivalente a nunca clicar no botão)."
      >
        <Switch
          id="auto-clinical-support"
          label="Gerar apoio à análise clínica automaticamente"
          hint="Requer o provedor de LLM real ligado na seção acima - sem ele, o resumo automático usaria o mesmo template local do botão manual."
          checked={draft.auto_clinical_support_enabled}
          onChange={(checked) => update("auto_clinical_support_enabled", checked)}
        />
      </Section>

      <Section
        title="Multimodalidade aceita em novas análises"
        description="Controla quais tipos de mídia podem ser enviados em novas análises. Análises já existentes não são afetadas."
      >
        <Switch
          id="modality-audio"
          label="Áudio"
          checked={draft.modality_audio_enabled}
          onChange={(checked) => update("modality_audio_enabled", checked)}
        />
        <Switch
          id="modality-video"
          label="Vídeo"
          checked={draft.modality_video_enabled}
          onChange={(checked) => update("modality_video_enabled", checked)}
        />
        <Switch
          id="modality-image"
          label="Imagem"
          checked={draft.modality_image_enabled}
          onChange={(checked) => update("modality_image_enabled", checked)}
        />
      </Section>

      <Section
        title="Visão computacional de vídeo"
        description="YOLOv8 (detecção de objetos) e OpenPose (estimativa de pose) podem ser ligados de forma independente. Só têm efeito quando o worker de vídeo estiver configurado com VISION_PROVIDER=OPENPOSE_YOLOV8."
      >
        <Switch
          id="vision-detection"
          label="YOLOv8 (detecção de objetos)"
          hint="Requer o pacote ultralytics instalado no worker de vídeo."
          checked={draft.vision_detection_enabled}
          onChange={(checked) => update("vision_detection_enabled", checked)}
        />
        <Switch
          id="vision-pose"
          label="OpenPose (estimativa de pose)"
          hint="Requer o binário OpenPose compilado no worker de vídeo."
          checked={draft.vision_pose_enabled}
          onChange={(checked) => update("vision_pose_enabled", checked)}
        />
      </Section>

      <Section
        title="Reconhecimento de imagem (enriquecimento complementar)"
        description="Rótulos genéricos somados às análises já existentes. Nunca substituem a categorização heurística de imagem nem a estimativa de pose do worker OpenPose/YOLOv8 (ver ADR 0016). Requer credenciais do provedor escolhido configuradas."
      >
        <Switch
          id="image-recognition"
          label="Rótulos de imagem"
          hint="Complementa a categorização heurística de imagem (foto clínica / documento / radiológica)."
          checked={draft.image_recognition_enabled}
          onChange={(checked) => update("image_recognition_enabled", checked)}
        />
        <SelectField
          id="image-recognition-provider"
          label="Provedor"
          options={IMAGE_RECOGNITION_PROVIDER_OPTIONS}
          value={draft.image_recognition_provider}
          onChange={(event) =>
            update("image_recognition_provider", event.target.value as ImageRecognitionProvider)
          }
          disabled={!draft.image_recognition_enabled}
        />
        <Switch
          id="vision-rekognition-video"
          label="Rekognition Video (rótulos de vídeo)"
          hint="Complementa o worker OpenPose/YOLOv8 com rótulos genéricos e timestamp. Não faz estimativa de pose. Sem equivalente Azure implementado ainda."
          checked={draft.vision_rekognition_video_enabled}
          onChange={(checked) => update("vision_rekognition_video_enabled", checked)}
        />
      </Section>

      <Section
        title="Análise de sentimento (enriquecimento contextual)"
        description="Sentimento identificado no texto adicional e na transcrição de áudio - sempre contextual, nunca determina risco clínico nem entra na consolidação de risco calculada pelo motor de regras. Requer credenciais do provedor escolhido configuradas."
      >
        <Switch
          id="sentiment-analysis"
          label="Analisar sentimento (texto e transcrição de áudio)"
          hint="Resultado exibido como observação contextual no laudo (ex.: positivo/negativo/neutro/misto)."
          checked={draft.sentiment_analysis_enabled}
          onChange={(checked) => update("sentiment_analysis_enabled", checked)}
        />
        <SelectField
          id="sentiment-analysis-provider"
          label="Provedor"
          options={SENTIMENT_ANALYSIS_PROVIDER_OPTIONS}
          value={draft.sentiment_analysis_provider}
          onChange={(event) =>
            update("sentiment_analysis_provider", event.target.value as SentimentAnalysisProvider)
          }
          disabled={!draft.sentiment_analysis_enabled}
        />
      </Section>

      {draft.updated_by && (
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Última alteração por {draft.updated_by} em{" "}
          {new Date(draft.updated_at).toLocaleString("pt-BR")}.
        </p>
      )}
    </>
  );
}
