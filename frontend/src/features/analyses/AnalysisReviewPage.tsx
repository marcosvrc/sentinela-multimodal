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
import { RiskBadge } from "@/components/ui/RiskBadge";
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
import { AnalysisReviewStats } from "./AnalysisReviewStats";

const EVIDENCE_PAGE_SIZE = 5;

type ModalityEvidenceItem = ReportContent["modality_evidence"][number];
interface IndexedModalityEvidenceItem {
  item: ModalityEvidenceItem;
  index: number;
}

const evidenceColumns: DataTableColumn<IndexedModalityEvidenceItem>[] = [
  {
    key: "modality_type",
    header: "Modalidade",
    render: ({ item }) => modalityLabel(item.modality_type),
  },
  { key: "summary", header: "Evidência", render: ({ item }) => item.summary },
  {
    key: "observed_at",
    header: "Observado em",
    render: ({ item }) => new Date(item.observed_at).toLocaleString("pt-BR"),
  },
  {
    key: "quality_state",
    header: "Qualidade",
    // `item.quality_state`/`quality_factors` podem estar ausentes em
    // relatorios gerados ANTES da unificacao desta tabela (Report.content
    // e um snapshot JSONB persistido no momento da geracao, nunca
    // recalculado) - "-" e o fallback honesto para dado desconhecido,
    // nao um valor inventado.
    render: ({ item }) => (item.quality_state ? modalityQualityStateLabel(item.quality_state) : "-"),
  },
  {
    key: "quality_factors",
    header: "Fatores de qualidade",
    render: ({ item }) => item.quality_factors?.join(", ") || "-",
  },
];

type ModalitySummaryItem = NonNullable<ReportContent["modality_summary"]>[number];

const modalitySummaryColumns: DataTableColumn<ModalitySummaryItem>[] = [
  {
    key: "modality_type",
    header: "Modalidade",
    render: (item) => modalityLabel(item.modality_type),
  },
  {
    key: "quality_state",
    header: "Qualidade",
    render: (item) => (item.quality_state ? modalityQualityStateLabel(item.quality_state) : "-"),
  },
  {
    key: "clinically_relevant",
    header: "Dados clínicos?",
    render: (item) => (item.clinically_relevant ? "Sim" : "Não"),
  },
  { key: "summary", header: "Resumo", render: (item) => item.summary },
  {
    key: "used_in_final_analysis",
    header: "Usado na análise final",
    render: (item) => (item.used_in_final_analysis ? "Sim" : "Não"),
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
    return <p style={{ color: "var(--color-text-muted)" }}>Nenhuma evidencia registrada.</p>;
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
    return <EmptyState title="Configure o usuario de desenvolvimento primeiro." />;
  }

  if (reportQuery.isLoading) return <Skeleton rows={6} />;

  if (reportQuery.isError) {
    const isNotFound =
      reportQuery.error instanceof ApiRequestError && reportQuery.error.status === 404;
    if (isNotFound) {
      return (
        <EmptyState
          title="Relatorio ainda nao disponivel"
          description="O relatorio e gerado assim que o processamento das modalidades e consolidado. Acompanhe o estado da analise e volte aqui em seguida."
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
        title="Revisao da analise"
        description={`Paciente ${content.identification.patient.full_name} - relatorio ${report.state === "CONFIRMED" ? "confirmado" : "em rascunho"}`}
        action={
          <RiskBadge
            outcome={content.calculated_risk.outcome}
            riskLevel={content.calculated_risk.risk_level}
            classificationLabel={content.calculated_risk.classification_label}
          />
        }
      />

      <AnalysisReviewStats content={content} stats={statsQuery.data} />

      {content.modality_summary && content.modality_summary.length > 0 && (
        <Section
          title="Resumo por modalidade"
          description="Para cada modalidade informada: qualidade dos dados, se há relação com informações clínicas, resumo do que foi encontrado e se será usado na análise final. Ausente apenas quando o relatório de qualquer modalidade contiver dados de qualidade."
        >
          <DataTable
            columns={modalitySummaryColumns}
            rows={content.modality_summary}
            getRowKey={(item) => item.modality_type}
          />
        </Section>
      )}

      {content.clinical_correlation_summary && (
        <Section
          title="Resumo final correlacionado"
          description={
            'Correlaciona apenas as modalidades marcadas como "usada na análise final" na ' +
            "tabela acima. Resumo determinístico (não depende de provedor de IA em nuvem) - " +
            "distinto do resumo assistido por IA abaixo."
          }
        >
          <p>{content.clinical_correlation_summary.text}</p>
          {content.clinical_correlation_summary.excluded_modality_types.length > 0 && (
            <p style={{ color: "var(--color-text-muted)", fontSize: 14, margin: 0 }}>
              Modalidades desconsideradas por falta de dados clínicos relevantes:{" "}
              {content.clinical_correlation_summary.excluded_modality_types
                .map((modalityType) => modalityLabel(modalityType))
                .join(", ")}
              .
            </p>
          )}
        </Section>
      )}

      <Section title="Resumo assistido por IA">
        <p>{content.ai_summary.text ?? "Resumo nao disponivel."}</p>
        {content.ai_summary.uncertainty_note && (
          <p style={{ color: "var(--color-text-muted)", fontSize: 14, margin: 0 }}>
            {content.ai_summary.uncertainty_note}
          </p>
        )}
      </Section>

      <AnalysisClinicalSupportPanel
        devSubject={subject}
        analysisId={analysisId}
        persistedSummary={content.clinical_support_summary}
        autoModeEnabled={featureFlagsQuery.data?.auto_clinical_support_enabled ?? false}
      />

      <Section title="Achados deterministicos">
        {content.deterministic_findings.length === 0 && (
          <p style={{ color: "var(--color-text-muted)" }}>
            Nenhuma entrada clinica estruturada avaliada.
          </p>
        )}
        {content.deterministic_findings.map((finding) => (
          <p key={finding.code}>
            <strong>{ruleSetCodeLabel(finding.code)}</strong>: {ruleEvaluationOutcomeLabel(finding.outcome)}
            {finding.classification_label ? ` - ${finding.classification_label}` : ""}
            {finding.inconclusive_reason
              ? ` (${ruleEvaluationInconclusiveReasonLabel(finding.inconclusive_reason)})`
              : ""}
          </p>
        ))}
      </Section>

      <Section title="Observacoes derivadas dos modelos">
        {content.model_observations.length === 0 && (
          <p style={{ color: "var(--color-text-muted)" }}>
            Nenhuma observacao de modelo disponivel (modalidade sem processador de
            reconhecimento de conteudo, ou nenhum termo candidato identificado).
          </p>
        )}
        {content.model_observations.map((item, index) => (
          <p key={index}>
            <strong>{modalityLabel(item.modality_type)}</strong>: {item.summary}
          </p>
        ))}
      </Section>

      {content.assisted_hypotheses.length > 0 && (
        <Section title="Hipoteses assistidas nao confirmadas">
          {content.assisted_hypotheses.map((item, index) => (
            <p key={index}>
              <strong>{modalityLabel(item.modality_type)}</strong>: {item.summary}{" "}
              <em style={{ color: "var(--color-text-muted)" }}>(hipotese nao confirmada)</em>
            </p>
          ))}
        </Section>
      )}

      <Section title="Evidências por modalidade e qualidade técnica">
        <ModalityEvidenceTable items={content.modality_evidence} />
      </Section>

      {content.inconsistencies.length > 0 && (
        <Section title="Inconsistencias e dados ausentes">
          <ul style={{ margin: 0 }}>
            {content.inconsistencies.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Conduta prevista pelo protocolo">
        <p>{content.protocol_conduct ?? "Nenhuma conduta associada."}</p>
      </Section>

      <Section title="Decisao">
        <div style={{ display: "flex", gap: "var(--space-3)" }}>
          {report.state === "DRAFT" && (
            <Button disabled={confirmMutation.isPending} onClick={() => confirmMutation.mutate()}>
              <CheckCircle size={14} strokeWidth={2} aria-hidden="true" />
              {confirmMutation.isPending ? "Confirmando..." : "Confirmar relatorio"}
            </Button>
          )}
          {report.state === "CONFIRMED" && (
            <Button
              variant="secondary"
              disabled={downloadMutation.isPending}
              onClick={() => downloadMutation.mutate()}
            >
              <Download size={14} strokeWidth={2} aria-hidden="true" />
              {downloadMutation.isPending ? "Baixando..." : "Baixar PDF"}
            </Button>
          )}
        </div>

        {report.state === "CONFIRMED" && (
          <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)", fontSize: 14 }}>
            Confirmado por {report.confirmed_by} em{" "}
            {report.confirmed_at && new Date(report.confirmed_at).toLocaleString("pt-BR")}.
          </p>
        )}
      </Section>
    </>
  );
}
