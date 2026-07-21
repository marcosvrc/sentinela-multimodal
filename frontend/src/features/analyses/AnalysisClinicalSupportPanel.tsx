import { useMutation } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import styles from "../patients/ClinicalSupportPanel.module.css";
import { Button } from "@/components/ui/Button";
import { Section } from "@/components/ui/Section";
import { Skeleton } from "@/components/feedback/Skeleton";
import { ErrorState } from "@/components/feedback/ErrorState";
import { useToast } from "@/components/feedback/ToastProvider";
import { extractErrorMessage } from "@/lib/errorMessage";
import { generateAnalysisClinicalSupportSummary } from "@/services/api/analyses";
import type { ReportContent } from "@/types/analysis";

interface AnalysisClinicalSupportPanelProps {
  devSubject: string;
  analysisId: string;
  /** Ultimo resumo ja gerado e PERSISTIDO no relatorio
   * (`Report.clinical_support_summary`) - exibido de imediato ao abrir a
   * tela, antes de qualquer novo clique em "Analisar dados clinicos"
   * nesta sessao (o botao ainda gera um resumo novo a qualquer momento,
   * que sobrescreve tanto a tela quanto o valor persistido). */
  persistedSummary?: ReportContent["clinical_support_summary"];
  /** Feature flag `auto_clinical_support_enabled` (tela `/admin/
   * feature-flags`) - quando ligada, o worker ja gera este resumo
   * automaticamente ao final do processamento (ver
   * `app.orchestrator.worker._maybe_run_automatic_clinical_support`),
   * entao o botao manual e ocultado (nao ha por que rodar de novo por
   * clique - o resumo exibido e sempre o mais recente automatico).
   * Desligada, o botao manual permanece como unica forma de gerar o
   * apoio (comportamento anterior). */
  autoModeEnabled: boolean;
}

/**
 * Apoio a analise clinica assistido por LLM para UMA analise multimodal
 * especifica (tela de revisao da analise). Mesmo padrao do apoio a
 * analise clinica da tela de paciente (`ClinicalSupportPanel`), mas
 * consolida os achados JA PRODUZIDOS pelos processadores de modalidade
 * (imagem/audio/video/texto) desta analise e o risco JA CALCULADO
 * deterministicamente, em vez do historico completo do paciente - sempre
 * como apoio, nunca como diagnostico: nao impede nem substitui a propria
 * analise do profissional responsavel (ver `app.clinical_support.
 * service.generate_analysis_clinical_support_summary`).
 *
 * Gerado sob demanda (nao persiste, nao usa `useQuery`): cada clique
 * produz um resumo novo a partir do estado atual dos achados da analise.
 */
export function AnalysisClinicalSupportPanel({
  devSubject,
  analysisId,
  persistedSummary,
  autoModeEnabled,
}: AnalysisClinicalSupportPanelProps) {
  const { showSuccess, showError } = useToast();
  const mutation = useMutation({
    mutationFn: () => generateAnalysisClinicalSupportSummary(devSubject, analysisId),
    onSuccess: () => showSuccess("Apoio à análise clínica gerado com sucesso."),
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível gerar o apoio à análise clínica."));
    },
  });

  // Enquanto nao houver um resumo novo gerado nesta sessao, exibe o
  // ultimo ja persistido no relatorio (se existir) - assim reabrir a
  // tela de revisao continua mostrando o apoio gerado anteriormente, e o
  // mesmo conteudo passa a integrar o PDF exportado (ver
  // `app.reports.builder`/`app.reports.pdf`).
  const displayed = mutation.data ?? persistedSummary ?? null;

  const description = autoModeEnabled
    ? "Consolida os achados por modalidade e o risco já calculado nesta análise em um sumário explicativo, com visão clínica, causas prováveis e direcionamento sugerido - gerado automaticamente quando há conteúdo clinicamente relevante. Um apoio que não substitui a análise do profissional responsável."
    : "Consolida os achados por modalidade e o risco já calculado nesta análise em um sumário explicativo, com visão clínica, causas prováveis e direcionamento sugerido - um apoio que não substitui a análise do profissional responsável.";

  return (
    <Section
      title="Apoio à análise clínica (IA)"
      description={description}
      action={
        // Com o modo automático ligado (`auto_clinical_support_enabled`),
        // o worker ja gera este resumo sem intervencao - o botao manual
        // fica oculto para nao sugerir uma acao redundante. Continua
        // disponivel quando o modo automatico esta desligado, ou quando
        // ainda nao ha nenhum resumo persistido (ex.: flag ligada apos a
        // analise ja ter sido processada).
        (!autoModeEnabled || !displayed) && (
          <Button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            <Sparkles size={16} strokeWidth={2} aria-hidden="true" />
            {mutation.isPending
              ? "Analisando..."
              : displayed
                ? "Gerar novamente"
                : "Analisar dados clínicos"}
          </Button>
        )
      }
    >
      {mutation.isPending && <Skeleton rows={4} />}

      {mutation.isError && (
        <ErrorState
          description={(mutation.error as Error).message}
          onRetry={() => mutation.mutate()}
        />
      )}

      {!mutation.isPending && autoModeEnabled && !displayed && (
        <p style={{ color: "var(--color-text-muted)" }}>
          Nenhum apoio automático foi gerado para esta análise - não foi identificado conteúdo
          clinicamente relevante (dados clínicos estruturados, achado confirmado como relevante,
          termo clínico em texto/transcrição, ou alteração vocal detectada).
        </p>
      )}

      {!mutation.isPending && displayed && (
        <div className={styles.box} role="region" aria-label="Resultado do apoio a analise clinica">
          <h3 className={styles.sectionTitle}>Visão clínica</h3>
          <p className={styles.sectionText}>{displayed.summary_text}</p>

          <h3 className={styles.sectionTitle}>Causas prováveis</h3>
          <p className={styles.sectionText}>{displayed.probable_causes}</p>

          <h3 className={styles.sectionTitle}>Direcionamento sugerido</h3>
          <p className={styles.sectionText}>{displayed.suggested_next_steps}</p>

          <p className={styles.disclaimer} role="alert">
            {displayed.uncertainty_note}
          </p>

          <p className={styles.meta}>
            Gerado em {new Date(displayed.generated_at).toLocaleString("pt-BR")} ·{" "}
            {displayed.findings_considered} achado(s) considerados · modelo {displayed.model}
          </p>
        </div>
      )}
    </Section>
  );
}
