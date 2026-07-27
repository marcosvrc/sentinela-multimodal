import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Sparkles, Eye } from "lucide-react";
import styles from "../patients/ClinicalSupportPanel.module.css";
import { Button } from "@/components/ui/Button";
import { InfoButton } from "@/components/ui/InfoButton";
import { Modal } from "@/components/ui/Modal";
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
  /** Resumo por modalidade do relatório (se disponível), usado para
   * informar quais modalidades foram consideradas na análise clínica. */
  modalitySummary?: ReportContent["modality_summary"];
  /** Evidências por modalidade para o popup de detalhes. */
  modalityEvidence?: ReportContent["modality_evidence"];
  /** Observações de modelo para o popup de detalhes. */
  modelObservations?: ReportContent["model_observations"];
  /** Texto adicional informado pelo profissional na análise. */
  additionalText?: string | null;
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
/**
 * Converte markdown simplificado (headings, bold, bullets) em HTML para
 * exibir textos estruturados do GPT-4 Vision de forma legível.
 */
function formatObservationText(text: string): string {
  // Remove o prefixo técnico se presente
  let cleaned = text.replace(/^Análise contextual de vídeo \(GPT-4 Vision, \d+ quadros\): /, "");
  cleaned = cleaned.replace(/^Análise contextual \(GPT-4 Vision\): /, "");

  // Converte markdown para HTML
  let html = cleaned
    // Headers: ## ou numerados (1. **Titulo**)
    .replace(/^(\d+)\.\s*\*\*(.+?)\*\*\s*:?\s*(.*)$/gm, '<h4 style="margin: 12px 0 6px; font-size: 14px; color: #333">$2</h4><p style="margin: 0 0 8px">$3</p>')
    // Bold: **texto**
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Bullets: - texto
    .replace(/^- (.+)$/gm, '<li style="margin-bottom: 4px">$1</li>')
    // Newlines para <br>
    .replace(/\n\n/g, '</p><p style="margin: 8px 0">')
    .replace(/\n/g, '<br/>');

  // Wrap <li> em <ul>
  html = html.replace(/(<li[^>]*>.*?<\/li>\s*)+/g, (match) => `<ul style="margin: 4px 0 8px 16px; padding: 0">${match}</ul>`);

  return `<div style="font-size: 13px; line-height: 1.6">${html}</div>`;
}

export function AnalysisClinicalSupportPanel({
  devSubject,
  analysisId,
  persistedSummary,
  autoModeEnabled,
  modalitySummary,
  modalityEvidence,
  modelObservations,
  additionalText,
}: AnalysisClinicalSupportPanelProps) {
  const { showSuccess, showError } = useToast();
  const [detailModality, setDetailModality] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => generateAnalysisClinicalSupportSummary(devSubject, analysisId),
    onSuccess: () => showSuccess("Apoio à análise clínica gerado com sucesso."),
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível gerar o apoio à análise clínica."));
    },
  });

  // Auto-trigger: quando a tela abre sem resumo persistido (análise
  // processada antes da flag estar ligada, ou flag ligada agora mas o
  // worker já passou), dispara automaticamente a chamada ao LLM para que
  // o profissional não precise clicar manualmente. Roda apenas uma vez.
  useEffect(() => {
    if (!persistedSummary && !mutation.data && !mutation.isPending && !mutation.isError) {
      mutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        <div className={styles.box} role="region" aria-label="Resultado do apoio à análise clínica">
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

          {modalitySummary && modalitySummary.length > 0 && (
            <>
              <h3 className={styles.sectionTitle}>Modalidades e contribuição na análise</h3>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginTop: 4 }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid var(--color-border)" }}>
                    <th style={{ padding: "6px 8px", fontWeight: 600 }}>Tipo de dado</th>
                    <th style={{ padding: "6px 8px", fontWeight: 600 }}>Relevância clínica</th>
                    <th style={{ padding: "6px 8px", fontWeight: 600 }}>Considerada na análise</th>
                    <th style={{ padding: "6px 8px", fontWeight: 600 }}>Detalhes</th>
                    <th style={{ padding: "6px 8px", fontWeight: 600 }}>Recurso</th>
                  </tr>
                </thead>
                <tbody>
                  {modalitySummary.map((m) => {
                    // Determina o recurso usado para cada modalidade a partir das observações
                    const modalityObs = (modelObservations ?? []).filter((o) => o.modality_type === m.modality_type);
                    const providers: string[] = [];
                    if (modalityObs.some((o) => o.details?.provider === "openai" || o.details?.analysis_type === "vision_contextual")) {
                      providers.push("GPT-4 Vision");
                    }
                    if (modalityObs.some((o) => o.details?.provider === "azure_vision" || (o.details?.provider === "azure_language"))) {
                      providers.push("Azure AI");
                    }
                    if (modalityObs.some((o) => o.summary?.toLowerCase().includes("azure ai language") || o.details?.sentiment)) {
                      if (!providers.includes("Azure AI")) providers.push("Azure AI Language");
                    }
                    if (modalityObs.some((o) => o.summary?.toLowerCase().includes("azure_speech") || o.details?.engine === "azure-speech-fast-transcription")) {
                      if (!providers.includes("Azure AI")) providers.push("Azure AI Speech");
                    }
                    if (modalityObs.some((o) => o.details?.extraction_method === "rule_based_negex_context_v1")) {
                      providers.push("NegEx/ConText");
                    }
                    if (modalityObs.some((o) => o.details?.rms_energy_mean != null)) {
                      providers.push("DSP local");
                    }
                    if (providers.length === 0) providers.push("Processamento local");

                    return (
                    <tr key={m.modality_type} style={{ borderBottom: "1px solid var(--color-border)" }}>
                      <td style={{ padding: "6px 8px" }}>
                        {m.modality_type === "TEXT" ? "Texto" : m.modality_type === "AUDIO" ? "Áudio" : m.modality_type === "IMAGE" ? "Imagem" : m.modality_type === "VIDEO" ? "Vídeo" : m.modality_type}
                      </td>
                      <td style={{ padding: "6px 8px", color: m.clinically_relevant ? "inherit" : "var(--color-text-muted)" }}>
                        {m.clinically_relevant ? "✓ Dados clínicos identificados" : "✗ Sem dados clínicos relevantes"}
                      </td>
                      <td style={{ padding: "6px 8px", fontWeight: m.used_in_final_analysis ? 600 : 400 }}>
                        {m.used_in_final_analysis ? "Sim — contribuiu" : "Não — desconsiderada"}
                      </td>
                      <td style={{ padding: "6px 8px" }}>
                        <button
                          type="button"
                          onClick={() => setDetailModality(m.modality_type)}
                          style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-primary-900)", display: "inline-flex", alignItems: "center", gap: 4, fontSize: 13, padding: "2px 6px", borderRadius: 4 }}
                        >
                          <Eye size={14} strokeWidth={2} /> Ver
                        </button>
                      </td>
                      <td style={{ padding: "6px 8px" }}>
                        <InfoButton title={`Recursos utilizados — ${m.modality_type === "TEXT" ? "Texto" : m.modality_type === "AUDIO" ? "Áudio" : m.modality_type === "IMAGE" ? "Imagem" : "Vídeo"}`} size="sm">
                          <p style={{ marginBottom: 8 }}>Serviços e algoritmos que processaram esta modalidade:</p>
                          <ul style={{ margin: 0, paddingLeft: 16 }}>
                            {providers.map((p, pi) => <li key={pi} style={{ marginBottom: 4 }}><strong>{p}</strong></li>)}
                          </ul>
                          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginTop: 12 }}>
                            <thead><tr style={{ borderBottom: "1px solid #ddd", textAlign: "left" }}><th style={{ padding: "4px 6px" }}>Recurso</th><th style={{ padding: "4px 6px" }}>Descrição</th></tr></thead>
                            <tbody>
                              {providers.includes("GPT-4 Vision") && <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 6px", fontWeight: 600 }}>GPT-4 Vision</td><td style={{ padding: "4px 6px" }}>Análise contextual da imagem via OpenAI (interpreta dor, postura, sinais clínicos visíveis)</td></tr>}
                              {providers.includes("Azure AI") && <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 6px", fontWeight: 600 }}>Azure AI Vision</td><td style={{ padding: "4px 6px" }}>Detecção de rótulos genéricos de objetos (roupas, pessoa, equipamento)</td></tr>}
                              {providers.includes("Azure AI Speech") && <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 6px", fontWeight: 600 }}>Azure AI Speech</td><td style={{ padding: "4px 6px" }}>Transcrição automática de áudio para texto (pt-BR)</td></tr>}
                              {providers.includes("Azure AI Language") && <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 6px", fontWeight: 600 }}>Azure AI Language</td><td style={{ padding: "4px 6px" }}>Análise de sentimento e termos-chave do texto/transcrição</td></tr>}
                              {providers.includes("NegEx/ConText") && <tr style={{ borderBottom: "1px solid #eee" }}><td style={{ padding: "4px 6px", fontWeight: 600 }}>NegEx/ConText</td><td style={{ padding: "4px 6px" }}>Motor de extração de termos clínicos com negação, temporalidade e certeza</td></tr>}
                              {providers.includes("DSP local") && <tr><td style={{ padding: "4px 6px", fontWeight: 600 }}>DSP local</td><td style={{ padding: "4px 6px" }}>Análise acústica determinística (energia vocal, pausas, segmentos de fala)</td></tr>}
                            </tbody>
                          </table>
                        </InfoButton>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* Modal de detalhes da modalidade */}
              {detailModality && (
                <Modal
                  open={!!detailModality}
                  title={`Detalhes — ${detailModality === "TEXT" ? "Texto" : detailModality === "AUDIO" ? "Áudio" : detailModality === "IMAGE" ? "Imagem" : detailModality === "VIDEO" ? "Vídeo" : detailModality}`}
                  onClose={() => setDetailModality(null)}
                  size="lg"
                >
                  {(() => {
                    const evidence = (modalityEvidence ?? []).filter((e) => e.modality_type === detailModality);
                    const observations = (modelObservations ?? []).filter((o) => o.modality_type === detailModality);
                    return (
                      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                        {/* Texto original informado (apenas para modalidade TEXT) */}
                        {detailModality === "TEXT" && additionalText && (
                          <div>
                            <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>Texto informado pelo profissional</h4>
                            <div style={{ padding: "12px 16px", background: "#f8f9fa", borderRadius: 6, fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                              {additionalText}
                            </div>
                          </div>
                        )}
                        {/* Transcrição do áudio (para modalidade AUDIO) */}
                        {detailModality === "AUDIO" && (() => {
                          const transcriptObs = observations.find((o) => o.details?.transcript);
                          return transcriptObs?.details?.transcript ? (
                            <div>
                              <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>Transcrição do áudio</h4>
                              <div style={{ padding: "12px 16px", background: "#f8f9fa", borderRadius: 6, fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                                {transcriptObs.details.transcript as string}
                              </div>
                            </div>
                          ) : null;
                        })()}
                        {evidence.length > 0 && (
                          <div>
                            <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>Evidências e qualidade</h4>
                            {evidence.map((e, i) => (
                              <div key={i} style={{ padding: "8px 12px", marginBottom: 6, background: "#f8f9fa", borderRadius: 6, fontSize: 13, lineHeight: 1.5 }}>
                                <p style={{ margin: 0 }}>{e.summary}</p>
                                {e.quality_state && (
                                  <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                                    Qualidade: {e.quality_state} {e.quality_factors?.length ? `(${e.quality_factors.join(", ")})` : ""}
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                        {observations.length > 0 && (
                          <div>
                            <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>Observações dos modelos</h4>
                            {observations.map((o, i) => (
                              <div key={i} style={{ padding: "8px 12px", marginBottom: 6, background: "#f8f9fa", borderRadius: 6, fontSize: 13, lineHeight: 1.6 }}>
                                <div
                                  style={{ margin: 0 }}
                                  dangerouslySetInnerHTML={{ __html: formatObservationText(o.summary) }}
                                />
                              </div>
                            ))}
                          </div>
                        )}
                        {evidence.length === 0 && observations.length === 0 && (
                          <p style={{ color: "var(--color-text-muted)" }}>Nenhum detalhe disponível para esta modalidade.</p>
                        )}
                      </div>
                    );
                  })()}
                </Modal>
              )}
            </>
          )}
        </div>
      )}
    </Section>
  );
}
