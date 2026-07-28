import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { CheckCircle, Download } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/data-display/DataTable";
import { Pagination } from "@/components/data-display/Pagination";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { Button } from "@/components/ui/Button";
import { Section } from "@/components/ui/Section";
import { useDevSession } from "@/hooks/useDevSession";
import { confirmReport, downloadReportPdf, getAnalysisStats, getReport } from "@/services/api/analyses";
import { getFeatureFlags } from "@/services/api/administration";
import {
  modalityLabel,
  modalityQualityStateLabel,
  ruleEvaluationInconclusiveReasonLabel,
  ruleEvaluationOutcomeLabel,
} from "@/app/enumLabels";
import { ruleSetCodeLabel } from "@/features/admin/clinicalDataLabels";
import { useToast } from "@/components/feedback/ToastProvider";
import { extractErrorMessage } from "@/lib/errorMessage";
import { ApiRequestError } from "@/types/api";
import type { ReportContent } from "@/types/analysis";
import { AnalysisClinicalSupportPanel } from "./AnalysisClinicalSupportPanel";
import { ClinicalDataStats, MultimodalStats } from "./AnalysisReviewStats";
import { InfoButton } from "@/components/ui/InfoButton";

const EVIDENCE_PAGE_SIZE = 5;

type ModalityEvidenceItem = ReportContent["modality_evidence"][number];
interface IndexedModalityEvidenceItem {
  item: ModalityEvidenceItem;
  index: number;
}

// Tradução dos valores NegEx/ConText para linguagem assistencial
const NEGATION_LABELS: Record<string, string> = {
  AFFIRMED: "Presente",
  NEGATED: "Negado pelo paciente",
};
const TEMPORALITY_LABELS: Record<string, string> = {
  CURRENT: "Atual",
  PAST: "Passado",
  FUTURE: "Hipotético/futuro",
};
const CERTAINTY_LABELS: Record<string, string> = {
  CONFIRMED: "Confirmado",
  SUSPECTED: "Suspeito",
  POSSIBLE: "Possível",
  CONDITIONAL: "Condicional",
};
const EXPERIENCER_LABELS: Record<string, string> = {
  PATIENT: "Paciente",
  FAMILY_MEMBER: "Familiar",
  OTHER: "Outro",
};

function negationLabel(value: string | undefined): string {
  return (value && NEGATION_LABELS[value]) || value || "-";
}
function temporalityLabel(value: string | undefined): string {
  return (value && TEMPORALITY_LABELS[value]) || value || "-";
}
function certaintyLabel(value: string | undefined): string {
  return (value && CERTAINTY_LABELS[value]) || value || "-";
}
function experiencerLabel(value: string | undefined): string {
  return (value && EXPERIENCER_LABELS[value]) || value || "-";
}

const evidenceColumns: DataTableColumn<IndexedModalityEvidenceItem>[] = [
  {
    key: "modality_type",
    header: "Tipo de dado",
    render: ({ item }) => modalityLabel(item.modality_type),
  },
  { key: "summary", header: "Achado", render: ({ item }) => {
    return <span style={{ fontSize: 13 }}>{item.summary}</span>;
  }},
  {
    key: "observed_at",
    header: "Registrado em",
    render: ({ item }) => new Date(item.observed_at).toLocaleString("pt-BR"),
  },
  {
    key: "quality_state",
    header: "Qualidade técnica",
    render: ({ item }) => (item.quality_state ? modalityQualityStateLabel(item.quality_state) : "-"),
  },
  {
    key: "quality_factors",
    header: "Observações de qualidade",
    render: ({ item }) => item.quality_factors?.join(", ") || "Sem ressalvas",
  },
];

/** Tabela paginada de evidencias por modalidade + qualidade tecnica,
 * unificadas em uma unica secao (mesmo padrao de 5 em 5 das demais
 * tabelas do sistema) - paginacao no cliente porque `Report.content` ja
 * chega completo do backend (nao ha paginacao de servidor para o
 * conteudo de um unico relatorio). */
function ModalityEvidenceTable({ items }: { items: ModalityEvidenceItem[] }) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(items.length / EVIDENCE_PAGE_SIZE));
  // Chave estavel inclui o indice ORIGINAL (nao o de pagina) - duas
  // evidencias da mesma modalidade podem ter o mesmo `observed_at` (ex.:
  // achados gravados no mesmo milissegundo pelo mesmo processador).
  const indexedItems = useMemo(
    () => items.map((item, index) => ({ item, index })),
    [items],
  );
  const pageItems = useMemo(
    () => indexedItems.slice((page - 1) * EVIDENCE_PAGE_SIZE, page * EVIDENCE_PAGE_SIZE),
    [indexedItems, page],
  );

  if (items.length === 0) {
    return <p style={{ color: "var(--color-text-muted)" }}>Nenhuma evidência registrada.</p>;
  }

  return (
    <>
      <DataTable columns={evidenceColumns} rows={pageItems} getRowKey={({ index }) => String(index)} />
      <Pagination page={page} totalPages={totalPages} totalItems={items.length} onPageChange={setPage} />
    </>
  );
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function AnalysisReviewPage() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const { subject } = useDevSession();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();

  const reportQuery = useQuery({
    queryKey: ["report", subject, analysisId],
    queryFn: () => getReport(subject as string, analysisId as string),
    enabled: Boolean(subject && analysisId),
    retry: false,
  });

  const statsQuery = useQuery({
    queryKey: ["analyses", "stats", subject],
    queryFn: () => getAnalysisStats(subject as string),
    enabled: Boolean(subject),
  });

  // Decide se o botao manual "Analisar dados clinicos" deve aparecer
  // (ver `AnalysisClinicalSupportPanel`) - so ocultado quando o modo
  // automatico esta ligado, entao uma falha nesta consulta nao pode
  // travar a tela: assume `false` (mostra o botao, comportamento
  // anterior) enquanto carrega ou se falhar.
  const featureFlagsQuery = useQuery({
    queryKey: ["admin", "feature-flags", subject],
    queryFn: () => getFeatureFlags(subject as string),
    enabled: Boolean(subject),
  });

  const confirmMutation = useMutation({
    mutationFn: () => confirmReport(subject as string, analysisId as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["report", subject, analysisId] });
      queryClient.invalidateQueries({ queryKey: ["analysis", subject, analysisId] });
      showSuccess("Relatório confirmado com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível confirmar o relatório."));
    },
  });

  const downloadMutation = useMutation({
    mutationFn: () => downloadReportPdf(subject as string, analysisId as string),
    onSuccess: (blob) => {
      triggerBlobDownload(blob, `relatorio-${analysisId}.pdf`);
      showSuccess("PDF baixado com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível baixar o PDF."));
    },
  });

  if (!subject || !analysisId) {
    return <EmptyState title="Configure o usuário de desenvolvimento primeiro." />;
  }

  if (reportQuery.isLoading) return <Skeleton rows={6} />;

  if (reportQuery.isError) {
    const isNotFound =
      reportQuery.error instanceof ApiRequestError && reportQuery.error.status === 404;
    if (isNotFound) {
      return (
        <EmptyState
          title="Relatório ainda não disponível"
          description="O relatório é gerado assim que o processamento das modalidades é consolidado. Acompanhe o estado da análise e volte aqui em seguida."
        />
      );
    }
    return (
      <ErrorState
        description={(reportQuery.error as Error).message}
        onRetry={() => reportQuery.refetch()}
      />
    );
  }

  const report = reportQuery.data;
  if (!report) return null;
  const content = report.content;

  return (
    <>
      <PageHeader
        title="Revisão da análise"
      />

      {/* Identificação do paciente */}
      <Section title="Paciente">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-4)" }}>
          <div>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Nome completo</span>
            <p style={{ margin: "4px 0 0", fontSize: 15, fontWeight: 600 }}>{content.identification.patient.full_name}</p>
          </div>
          <div>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Prontuário</span>
            <p style={{ margin: "4px 0 0", fontSize: 15 }}>{content.identification.patient.medical_record_number}</p>
          </div>
          <div>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Data de nascimento</span>
            <p style={{ margin: "4px 0 0", fontSize: 15 }}>{new Date(content.identification.patient.birth_date + "T00:00:00").toLocaleDateString("pt-BR")}</p>
          </div>
          <div>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Profissional responsável</span>
            <p style={{ margin: "4px 0 0", fontSize: 15 }}>{content.identification.created_by}</p>
          </div>
          <div>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Data da análise</span>
            <p style={{ margin: "4px 0 0", fontSize: 15 }}>{new Date(content.identification.created_at).toLocaleString("pt-BR")}</p>
          </div>
          <div>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Status</span>
            <p style={{ margin: "4px 0 0", fontSize: 15 }}>{report.state === "CONFIRMED" ? "Relatório confirmado" : "Em rascunho (aguardando confirmação)"}</p>
          </div>
        </div>
      </Section>

      {/* BLOCO A — DADOS CLÍNICOS ESTRUTURADOS */}
      <div style={{ borderLeft: "4px solid var(--risk-low)", paddingLeft: "var(--space-4)", marginBottom: "var(--space-5)" }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)", margin: "0 0 var(--space-3) 0", textTransform: "uppercase", letterSpacing: "0.03em" }}>
          Dados clínicos estruturados
          <InfoButton title="Dados clínicos estruturados" size="sm">
            <p>Sinais vitais avaliados pelo motor de regras determinístico — <strong>única fonte de classificação de risco</strong> do sistema.</p>
          </InfoButton>
        </h2>

        {Object.keys(content.identification.structured_clinical_inputs).length === 0 ? (
          <div style={{ padding: "20px", background: "var(--color-background)", borderRadius: 8, border: "1px dashed var(--color-border)", textAlign: "center" }}>
            <p style={{ margin: 0, fontSize: 15, color: "var(--color-text-muted)", fontWeight: 500 }}>
              Dados clínicos não informados para esta análise
            </p>
            <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--color-text-muted)" }}>
              Sem sinais vitais estruturados, o motor de regras não pode calcular o nível de risco determinístico.
            </p>
          </div>
        ) : (
          <>
            <ClinicalDataStats content={content} stats={statsQuery.data} />

            <Section title="Achados determinísticos"
              action={<InfoButton title="Achados determinísticos"><p><strong>Classificado</strong> = regra encontrada, risco 1-6. <strong>Inconclusivo</strong> = sem regra aplicável (não significa "normal").</p></InfoButton>}
            >
              {content.deterministic_findings.length === 0 && (<p style={{ color: "var(--color-text-muted)" }}>Nenhuma entrada clínica estruturada avaliada.</p>)}
              {content.deterministic_findings.map((finding) => (
                <p key={finding.code}>
                  <strong>{ruleSetCodeLabel(finding.code)}</strong>: {ruleEvaluationOutcomeLabel(finding.outcome)}
                  {finding.classification_label ? ` - ${finding.classification_label}` : ""}
                  {finding.inconclusive_reason ? ` (${ruleEvaluationInconclusiveReasonLabel(finding.inconclusive_reason)})` : ""}
                </p>
              ))}
            </Section>
          </>
        )}
      </div>

      {/* BLOCO B — DADOS MULTIMODAIS */}
      <div style={{ borderLeft: "4px solid var(--color-accent-500)", paddingLeft: "var(--space-4)", marginBottom: "var(--space-5)" }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)", margin: "0 0 var(--space-3) 0", textTransform: "uppercase", letterSpacing: "0.03em" }}>
          Dados multimodais
          <InfoButton title="Dados multimodais" size="sm">
            <p>Achados de áudio, vídeo, imagem e texto. <strong>Nunca determinam o nível de risco</strong> — são informações de apoio para a revisão profissional.</p>
          </InfoButton>
        </h2>

        {content.modality_evidence.length === 0 ? (
          <div style={{ padding: "20px", background: "var(--color-background)", borderRadius: 8, border: "1px dashed var(--color-border)", textAlign: "center" }}>
            <p style={{ margin: 0, fontSize: 15, color: "var(--color-text-muted)", fontWeight: 500 }}>
              Dados multimodais não informados para esta análise
            </p>
            <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--color-text-muted)" }}>
              Nenhum arquivo de áudio, vídeo, imagem ou texto adicional foi enviado.
            </p>
          </div>
        ) : (
          <>
        <MultimodalStats content={content} />

      <Section title="Termos clínicos e observações"
        action={
          <InfoButton title="Termos clínicos e observações dos modelos" size="lg">
            <p>Esta seção mostra os achados produzidos automaticamente pelos processadores de cada tipo de dado. Divide-se em duas partes:</p>
            <h4 style={{ marginTop: 12, marginBottom: 4 }}>Tabela de termos clínicos</h4>
            <p>Termos extraídos do texto da análise (incluindo transcrições de áudio) por um motor de processamento de linguagem natural clínica (NegEx/ConText). Cada termo traz:</p>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginTop: 8, marginBottom: 12 }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "2px solid #ddd" }}>
                  <th style={{ padding: "6px 8px" }}>Coluna</th>
                  <th style={{ padding: "6px 8px" }}>Significado</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "6px 8px", fontWeight: 600 }}>Termo</td><td style={{ padding: "6px 8px" }}>Palavra ou expressão clínica identificada (ex.: "dispneia", "dor torácica")</td></tr>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "6px 8px", fontWeight: 600 }}>Status</td><td style={{ padding: "6px 8px" }}><strong>Presente</strong> = o sintoma/condição está presente; <strong>Negado pelo paciente</strong> = foi explicitamente descartado ("nega dor")</td></tr>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "6px 8px", fontWeight: 600 }}>Temporalidade</td><td style={{ padding: "6px 8px" }}><strong>Atual</strong> = está acontecendo agora; <strong>Passado</strong> = aconteceu antes; <strong>Futuro</strong> = hipotético/planejado</td></tr>
                <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "6px 8px", fontWeight: 600 }}>Certeza</td><td style={{ padding: "6px 8px" }}><strong>Confirmado</strong> = afirmado com certeza; <strong>Suspeito/Possível</strong> = não confirmado; <strong>Condicional</strong> = depende de outra condição</td></tr>
                <tr><td style={{ padding: "6px 8px", fontWeight: 600 }}>Quem relata</td><td style={{ padding: "6px 8px" }}><strong>Paciente</strong> = o próprio paciente; <strong>Familiar</strong> = um parente; <strong>Outro</strong> = outra pessoa mencionada</td></tr>
              </tbody>
            </table>
            <h4 style={{ marginTop: 12, marginBottom: 4 }}>Outras observações</h4>
            <p>Achados de outros processadores (análise de sentimento do texto, métricas acústicas do áudio, rótulos de imagem). São informações complementares que <strong>nunca determinam o nível de risco</strong> — o risco clínico é calculado exclusivamente pelo motor de regras determinístico.</p>
          </InfoButton>
        }
      >
        {content.model_observations.length === 0 && (
          <p style={{ color: "var(--color-text-muted)" }}>
            Nenhuma observação de modelo disponível para esta análise.
          </p>
        )}
        {content.model_observations.length > 0 && (() => {
          const clinicalTerms = content.model_observations.filter(
            (item) => item.details?.term && item.details?.extraction_method
          );
          const otherObservations = content.model_observations.filter(
            (item) => !(item.details?.term && item.details?.extraction_method)
              && !item.details?.category  // Exclui categorização heurística (técnica, não clínica)
          );
          return (
            <>
              {clinicalTerms.length > 0 && (
                <>
                  <p style={{ fontSize: 14, color: "var(--color-text-muted)", marginBottom: "var(--space-3)" }}>
                    Termos clínicos extraídos automaticamente do texto, com contexto linguístico
                    completo. Um termo <strong>negado</strong> indica que o paciente ou
                    profissional descartou explicitamente aquele achado.
                  </p>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14, marginBottom: "var(--space-4)" }}>
                    <thead>
                      <tr style={{ background: "var(--color-border)", textAlign: "left" }}>
                        <th style={{ padding: "8px 10px" }}>Termo</th>
                        <th style={{ padding: "8px 10px" }}>Status</th>
                        <th style={{ padding: "8px 10px" }}>Temporalidade</th>
                        <th style={{ padding: "8px 10px" }}>Certeza</th>
                        <th style={{ padding: "8px 10px" }}>Quem relata</th>
                        <th style={{ padding: "8px 10px" }}>Ocorrências</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        // Agrupa termos com mesmos atributos (termo+negação+temporalidade+certeza+experienciador)
                        const grouped = new Map<string, { item: typeof clinicalTerms[0]; count: number }>();
                        for (const item of clinicalTerms) {
                          const key = `${item.details.term}|${item.details.negation}|${item.details.temporality}|${item.details.certainty}|${item.details.experiencer}`;
                          const existing = grouped.get(key);
                          if (existing) {
                            existing.count += 1;
                          } else {
                            grouped.set(key, { item, count: 1 });
                          }
                        }
                        return Array.from(grouped.values()).map(({ item, count }, index) => (
                          <tr key={index} style={{ borderBottom: "1px solid var(--color-border)" }}>
                            <td style={{ padding: "8px 10px", fontWeight: 600 }}>{item.details.term}</td>
                            <td style={{
                              padding: "8px 10px",
                              color: item.details.negation === "NEGATED" ? "var(--color-text-muted)" : "inherit",
                              fontStyle: item.details.negation === "NEGATED" ? "italic" : "normal",
                            }}>
                              {negationLabel(item.details.negation)}
                            </td>
                            <td style={{ padding: "8px 10px" }}>{temporalityLabel(item.details.temporality)}</td>
                            <td style={{ padding: "8px 10px" }}>{certaintyLabel(item.details.certainty)}</td>
                            <td style={{ padding: "8px 10px" }}>{experiencerLabel(item.details.experiencer)}</td>
                            <td style={{ padding: "8px 10px", textAlign: "center" }}>{count > 1 ? `${count}x` : "1"}</td>
                          </tr>
                        ));
                      })()}
                    </tbody>
                  </table>
                </>
              )}
              {otherObservations.length > 0 && (
                <>
                  {clinicalTerms.length > 0 && (
                    <p style={{ fontSize: 13, color: "var(--color-text-muted)", marginTop: "var(--space-3)", marginBottom: "var(--space-2)" }}>
                      Observações complementares por tipo de dado:
                    </p>
                  )}
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                    {(() => {
                      // Agrupa por modalidade e filtra apenas dados relevantes ao profissional
                      const modalities = [...new Set(otherObservations.map((o) => o.modality_type))];

                      return modalities.map((mod) => {
                        const items = otherObservations.filter((o) => o.modality_type === mod);

                        // Filtra itens de infraestrutura (não relevantes ao profissional)
                        const relevantItems: { label: string; text: string }[] = [];

                        // Para TEXT, inclui o texto informado pelo profissional no topo
                        if (mod === "TEXT" && content.identification.additional_text) {
                          relevantItems.push({ label: "Texto informado", text: content.identification.additional_text });
                        }

                        for (const item of items) {
                          // Pular itens puramente técnicos
                          if (item.summary.toLowerCase().includes("transcricao concluida") ||
                              item.summary.toLowerCase().includes("transcricao indisponivel")) continue;

                          // Transcrição literal
                          if (item.summary.toLowerCase().includes("rascunho de nota") || item.summary.toLowerCase().includes("transcricao literal")) {
                            const raw = item.summary;
                            const qi = raw.indexOf('"');
                            const text = qi >= 0 ? raw.slice(qi + 1).replace(/"\.?$/, "") : raw;
                            relevantItems.push({ label: "Transcrição", text: `"${text}"` });
                            continue;
                          }

                          // Sentimento (Azure AI Language) - inclui o
                          // percentual de confianca do score dominante
                          // (details.scores), antes calculado mas nunca
                          // exibido ao profissional.
                          if (item.details?.sentiment) {
                            const s = item.details.sentiment as string;
                            const sl = s === "NEGATIVE" ? "Negativo" : s === "POSITIVE" ? "Positivo" : s === "MIXED" ? "Misto" : "Neutro";
                            const scoreKey = s === "NEGATIVE" ? "negative" : s === "POSITIVE" ? "positive" : s === "MIXED" ? "mixed" : "neutral";
                            const scores = item.details?.scores as Record<string, number> | undefined;
                            const scoreValue = scores?.[scoreKey];
                            const pct = typeof scoreValue === "number" ? ` (${Math.round(scoreValue * 100)}%)` : "";
                            const kp = item.summary.match(/Termos-chave identificados: (.+)/)?.[1] || "";
                            relevantItems.push({ label: "Sentimento", text: `${sl}${pct}${kp ? ` — ${kp}` : ""}` });
                            continue;
                          }

                          // Rotulos reconhecidos por Azure AI Vision -
                          // confianca por rotulo (details.labels), antes
                          // calculada no backend mas nunca exibida.
                          if (Array.isArray(item.details?.labels) && (item.details.labels as unknown[]).length > 0) {
                            const labels = item.details.labels as Array<{ label: string; confidence: number }>;
                            const text = labels
                              .map((l) => `${l.label} (${Math.round(l.confidence)}%)`)
                              .join(", ");
                            relevantItems.push({ label: "Rótulos reconhecidos (confiança)", text });
                            continue;
                          }

                          // Visao computacional de video (YOLOv8/OpenPose) -
                          // confianca media por objeto detectado e
                          // confianca media dos keypoints de pose, ambas
                          // calculadas no backend mas antes nunca exibidas
                          // (so a contagem aparecia no resumo textual).
                          if (item.details?.provider === "openpose_yolov8" && item.details?.status === "COMPLETED") {
                            const detFindings = (item.details?.detection_findings as Array<{ label: string; confidence: number }> | undefined) || [];
                            const poseFindings = (item.details?.pose_findings as Array<{ person_count: number; mean_keypoint_confidence: number | null }> | undefined) || [];
                            const parts: string[] = [];
                            if (detFindings.length > 0) {
                              const byLabel = new Map<string, number[]>();
                              for (const d of detFindings) {
                                byLabel.set(d.label, [...(byLabel.get(d.label) || []), d.confidence]);
                              }
                              const labelText = Array.from(byLabel.entries())
                                .map(([label, confs]) => `${label} (${Math.round((confs.reduce((a, b) => a + b, 0) / confs.length) * 100)}%)`)
                                .join(", ");
                              parts.push(`Objetos (YOLOv8): ${labelText}`);
                            }
                            const validPoseConf = poseFindings
                              .map((p) => p.mean_keypoint_confidence)
                              .filter((c): c is number => c != null);
                            if (validPoseConf.length > 0) {
                              const avgPersons = poseFindings.reduce((a, p) => a + p.person_count, 0) / poseFindings.length;
                              const avgConf = validPoseConf.reduce((a, b) => a + b, 0) / validPoseConf.length;
                              parts.push(`Pose (OpenPose): ${avgPersons.toFixed(1)} pessoa(s)/quadro em média, confiança média dos keypoints ${Math.round(avgConf * 100)}%`);
                            }
                            if (parts.length > 0) {
                              relevantItems.push({ label: "Visão computacional (confiança)", text: parts.join(" · ") });
                              continue;
                            }
                          }

                          // Acústica
                          if (item.details?.rms_energy_mean != null) {
                            const rms = item.details.rms_energy_mean as number;
                            const p = item.details?.pause_ratio as number | undefined;
                            let d = rms < 0.05 ? "Energia vocal baixa (possível voz fraca)" : "Energia vocal normal";
                            if (p != null) d += ` · Pausas: ${Math.round(p * 100)}%`;
                            relevantItems.push({ label: "Voz", text: d });
                            continue;
                          }

                          // GPT-4 Vision / análise contextual (imagem)
                          if (item.details?.analysis_type === "vision_contextual") {
                            const desc = item.summary.replace(/^Análise contextual \(GPT-4 Vision\): /, "");
                            relevantItems.push({ label: "Contexto visual", text: desc });
                            continue;
                          }

                          // GPT-4 Vision / análise contextual (vídeo) — resumo curto
                          if (item.details?.analysis_type === "vision_contextual_video") {
                            const fullText = item.summary.replace(/^Análise contextual de vídeo \(GPT-4 Vision, \d+ quadros\): /, "");
                            // Pega apenas a primeira seção (até o primeiro \n\n ou as primeiras 200 chars)
                            const firstParagraph = fullText.split(/\n\n/)[0];
                            const summary = firstParagraph.length > 200 ? firstParagraph.slice(0, 200) + "..." : firstParagraph;
                            relevantItems.push({ label: "Análise de vídeo (resumo)", text: summary });
                            continue;
                          }

                          // Relevância clínica do texto (não-relevante)
                          if (item.details?.clinical_relevance === "NOT_RELEVANT" && item.details?.relevance_percent != null) {
                            relevantItems.push({ label: "Avaliação de relevância", text: item.summary });
                            continue;
                          }

                          // Fallback: inclui qualquer outro achado
                          relevantItems.push({ label: "Observação", text: item.summary });
                        }

                        if (relevantItems.length === 0) return null;

                        return (
                          <div key={mod} style={{ padding: "12px 16px", background: "var(--color-background)", borderRadius: 8, border: "1px solid var(--color-border)" }}>
                            <p style={{ margin: "0 0 8px", fontWeight: 600, fontSize: 13, textTransform: "uppercase", letterSpacing: "0.03em", color: "var(--color-text-muted)" }}>
                              {modalityLabel(mod)}
                            </p>
                            {relevantItems.map((ri, idx) => (
                              <div key={idx} style={{ marginBottom: idx < relevantItems.length - 1 ? 8 : 0 }}>
                                <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)" }}>{ri.label}: </span>
                                <span style={{ fontSize: 14, lineHeight: 1.5 }}>{ri.text}</span>
                              </div>
                            ))}
                          </div>
                        );
                      }).filter(Boolean);
                    })()}
                  </div>
                </>
              )}
            </>
          );
        })()}
      </Section>

      {content.assisted_hypotheses.length > 0 && (
        <Section title="Hipóteses assistidas não confirmadas">
          {content.assisted_hypotheses.map((item, index) => (
            <p key={index}>
              <strong>{modalityLabel(item.modality_type)}</strong>: {item.summary}{" "}
              <em style={{ color: "var(--color-text-muted)" }}>(hipótese não confirmada)</em>
            </p>
          ))}
        </Section>
      )}

      <Section title="Detalhamento técnico"
        action={<InfoButton title="Detalhamento técnico"><p>Metadados de qualidade de cada dado processado.</p></InfoButton>}
      >
        <ModalityEvidenceTable items={content.modality_evidence.filter((item) =>
          !item.summary.toLowerCase().includes("termo clinico candidato") &&
          !item.summary.toLowerCase().includes("análise contextual") &&
          !item.summary.toLowerCase().includes("sentimento identificado") &&
          !item.summary.toLowerCase().includes("rascunho de nota clinica") &&
          !item.summary.toLowerCase().includes("transcricao concluida")
        )} />
      </Section>
          </>
        )}
      </div>

      {/* BLOCO C — ANÁLISE CONSOLIDADA (IA) */}
      <div style={{ borderLeft: "4px solid var(--color-primary-900)", paddingLeft: "var(--space-4)", marginBottom: "var(--space-5)" }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)", margin: "0 0 var(--space-3) 0", textTransform: "uppercase", letterSpacing: "0.03em" }}>
          Análise consolidada (IA)
          <InfoButton title="Análise consolidada" size="sm">
            <p>Correlaciona dados clínicos + multimodais via inteligência artificial. <strong>Nunca substitui</strong> a avaliação do profissional.</p>
          </InfoButton>
        </h2>

        {(() => {
          const hasClinical = Object.keys(content.identification.structured_clinical_inputs).length > 0;
          const hasMultimodal = content.modality_evidence.length > 0;
          const sourceLabel = hasClinical && hasMultimodal
            ? "Dados clínicos + multimodais"
            : hasClinical
              ? "Apenas dados clínicos (sem modalidades multimodais)"
              : hasMultimodal
                ? "Apenas dados multimodais (sem dados clínicos estruturados)"
                : "Sem dados de entrada";
          return (
            <p style={{ fontSize: 13, color: "var(--color-text-muted)", margin: "0 0 var(--space-3) 0", padding: "8px 12px", background: "var(--color-background)", borderRadius: 6, border: "1px solid var(--color-border)" }}>
              <strong>Fontes consideradas:</strong> {sourceLabel}
            </p>
          );
        })()}

        <Section title="Avaliação assistida por IA">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {content.assisted_risk && (() => {
              const level = content.assisted_risk!.risk_level;
              const colorMap: Record<number, string> = { 1: "var(--risk-low)", 2: "var(--risk-mild)", 3: "var(--risk-moderate)", 4: "var(--risk-high)", 5: "var(--risk-very-high)", 6: "var(--risk-critical)" };
              const riskColor = colorMap[level] || "var(--risk-inconclusive)";
              return (
                <div style={{ display: "flex", gap: 0, borderRadius: 10, overflow: "hidden", border: "1px solid var(--color-border)" }}>
                  {/* Bloco colorido com o nível */}
                  <div style={{ background: riskColor, color: "#fff", padding: "20px 28px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minWidth: 130 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", opacity: 0.9 }}>Risco sugerido</span>
                    <span style={{ fontSize: 36, fontWeight: 800, lineHeight: 1.1, marginTop: 4 }}>
                      {level}
                    </span>
                    <span style={{ fontSize: 13, marginTop: 4, textAlign: "center", opacity: 0.95 }}>
                      {content.assisted_risk!.classification_label}
                    </span>
                  </div>
                  {/* Justificativa ao lado */}
                  <div style={{ flex: 1, padding: "16px 20px", display: "flex", flexDirection: "column", justifyContent: "center", gap: 6 }}>
                    <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6 }}>{content.assisted_risk!.justification}</p>
                    <p style={{ margin: 0, fontSize: 12, color: "var(--color-text-muted)" }}>
                      Modelo: {content.assisted_risk!.model} ({content.assisted_risk!.provider})
                    </p>
                  </div>
                </div>
              );
            })()}

            {/* Resumo explicativo (separado do nível) */}
            <div style={{ padding: "16px", background: "var(--color-background)", borderRadius: 8, border: "1px solid var(--color-border)" }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", marginBottom: 8 }}>Resumo explicativo</p>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7 }}>{content.ai_summary.text ?? "Resumo não disponível."}</p>
              {content.ai_summary.uncertainty_note && (
                <p style={{ color: "var(--color-text-muted)", fontSize: 13, margin: "10px 0 0", fontStyle: "italic" }}>{content.ai_summary.uncertainty_note}</p>
              )}
            </div>

            {content.assisted_risk?.uncertainty_note && (
              <p style={{ color: "var(--color-text-muted)", fontSize: 13, margin: 0, fontStyle: "italic" }}>{content.assisted_risk.uncertainty_note}</p>
            )}
          </div>
        </Section>

        <AnalysisClinicalSupportPanel
          devSubject={subject}
          analysisId={analysisId}
          persistedSummary={content.clinical_support_summary}
          autoModeEnabled={featureFlagsQuery.data?.auto_clinical_support_enabled ?? false}
          modalitySummary={content.modality_summary}
          modalityEvidence={content.modality_evidence}
          modelObservations={content.model_observations}
          additionalText={content.identification.additional_text}
        />
      </div>

      {/* SEÇÕES FINAIS */}
      {content.inconsistencies.length > 0 && (
        <Section title="Inconsistências e dados ausentes">
          <ul style={{ margin: 0 }}>{content.inconsistencies.map((item, index) => <li key={index}>{item}</li>)}</ul>
        </Section>
      )}

      <Section title="Decisão">
        <div style={{ display: "flex", gap: "var(--space-3)" }}>
          {report.state === "DRAFT" && (
            <Button disabled={confirmMutation.isPending} onClick={() => confirmMutation.mutate()}>
              <CheckCircle size={14} strokeWidth={2} aria-hidden="true" />
              {confirmMutation.isPending ? "Confirmando..." : "Confirmar relatório"}
            </Button>
          )}
          {report.state === "CONFIRMED" && (
            <Button variant="secondary" disabled={downloadMutation.isPending} onClick={() => downloadMutation.mutate()}>
              <Download size={14} strokeWidth={2} aria-hidden="true" />
              {downloadMutation.isPending ? "Baixando..." : "Baixar PDF"}
            </Button>
          )}
        </div>
        {report.state === "CONFIRMED" && (
          <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)", fontSize: 14 }}>
            Confirmado por {report.confirmed_by} em {report.confirmed_at && new Date(report.confirmed_at).toLocaleString("pt-BR")}.
          </p>
        )}
      </Section>
    </>
  );
}
