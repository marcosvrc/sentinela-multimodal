import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Eye, RefreshCw, XCircle } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { useToast } from "@/components/feedback/ToastProvider";
import { Button } from "@/components/ui/Button";
import { LinkButton } from "@/components/ui/LinkButton";
import { Section } from "@/components/ui/Section";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useDevSession } from "@/hooks/useDevSession";
import { extractErrorMessage } from "@/lib/errorMessage";
import {
  cancelAnalysis,
  getAnalysis,
  listMediaAssets,
  listModalityStates,
  retryAnalysis,
} from "@/services/api/analyses";
import { AnalysisStatus } from "@/types/enums.generated";
import { modalityLabel } from "@/app/enumLabels";
import type { AnalysisModalityState, MediaAsset } from "@/types/analysis";

// Simplificacao documentada: o backend ainda nao expoe `available_actions`
// (ver app/api/schemas/analysis.py::AnalysisStatusResponse, nao conectado
// a nenhuma rota ainda) - as regras abaixo espelham as mesmas transicoes
// que app.orchestrator.service ja aplica no backend
// (ANALYSIS_STATUS_TRANSITIONS/_CANCELLABLE_STATES), mas duplicadas aqui.
const CANCELLABLE_STATUSES = new Set<string>([
  AnalysisStatus.CREATED,
  AnalysisStatus.UPLOADING,
  AnalysisStatus.QUEUED,
  AnalysisStatus.PROCESSING,
  AnalysisStatus.PARTIALLY_COMPLETED,
]);
const RETRYABLE_STATUSES = new Set<string>([AnalysisStatus.FAILED_RETRYABLE]);
const REVIEWABLE_STATUSES = new Set<string>([
  AnalysisStatus.WAITING_REVIEW,
  AnalysisStatus.COMPLETED,
]);
const TERMINAL_STATUSES = new Set<string>([
  AnalysisStatus.COMPLETED,
  AnalysisStatus.FAILED_FINAL,
  AnalysisStatus.CANCELLED,
]);

/**
 * Colunas da tabela de processamento por modalidade - recebe o mapa de
 * midias (para exibir o nome do arquivo de origem) porque uma analise
 * pode ter mais de uma midia da mesma modalidade, cada uma com seu
 * proprio estado de processamento (ver `app.orchestrator.service.
 * submit_analysis`); sem o nome do arquivo, duas linhas "Imagem" nao
 * seriam distinguiveis.
 */
function buildModalityColumns(
  mediaAssetById: Map<string, MediaAsset>,
): DataTableColumn<AnalysisModalityState>[] {
  return [
    {
      key: "modality_type",
      header: "Modalidade",
      render: (state) => modalityLabel(state.modality_type),
    },
    {
      key: "file",
      header: "Arquivo",
      render: (state) =>
        state.media_asset_id ? mediaAssetById.get(state.media_asset_id)?.original_filename ?? "-" : "-",
    },
    { key: "status", header: "Estado", render: (state) => <StatusBadge status={state.status} /> },
    {
      key: "error_message",
      header: "Detalhe",
      render: (state) => state.error_message ?? "-",
    },
  ];
}

const mediaColumns: DataTableColumn<MediaAsset>[] = [
  { key: "modality_type", header: "Modalidade", render: (asset) => modalityLabel(asset.modality_type) },
  { key: "original_filename", header: "Arquivo", render: (asset) => asset.original_filename },
  {
    key: "upload_state",
    header: "Estado do upload",
    render: (asset) => <StatusBadge status={asset.upload_state} />,
  },
  {
    key: "rejection_reason",
    header: "Motivo de rejeicao",
    render: (asset) => asset.rejection_reason ?? "-",
  },
];

export function AnalysisDetailPage() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const { subject } = useDevSession();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();

  const analysisQuery = useQuery({
    queryKey: ["analysis", subject, analysisId],
    queryFn: () => getAnalysis(subject as string, analysisId as string),
    enabled: Boolean(subject && analysisId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL_STATUSES.has(status) ? false : 3000;
    },
  });

  const modalitiesQuery = useQuery({
    queryKey: ["analysis-modalities", subject, analysisId],
    queryFn: () => listModalityStates(subject as string, analysisId as string),
    enabled: Boolean(subject && analysisId),
    refetchInterval: () => {
      const status = analysisQuery.data?.status;
      return status && TERMINAL_STATUSES.has(status) ? false : 3000;
    },
  });

  const mediaQuery = useQuery({
    queryKey: ["analysis-media", subject, analysisId],
    queryFn: () => listMediaAssets(subject as string, analysisId as string),
    enabled: Boolean(subject && analysisId),
  });

  const mediaAssetById = new Map((mediaQuery.data ?? []).map((asset) => [asset.id, asset]));

  const cancelMutation = useMutation({
    mutationFn: () => cancelAnalysis(subject as string, analysisId as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["analysis", subject, analysisId] });
      showSuccess("Análise cancelada com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível cancelar a análise."));
    },
  });

  const retryMutation = useMutation({
    mutationFn: () => retryAnalysis(subject as string, analysisId as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["analysis", subject, analysisId] });
      showSuccess("Análise reenviada com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível reenviar a análise."));
    },
  });

  if (!subject || !analysisId) {
    return <EmptyState title="Configure o usuario de desenvolvimento primeiro." />;
  }

  if (analysisQuery.isLoading) return <Skeleton rows={4} />;
  if (analysisQuery.isError) {
    return (
      <ErrorState
        description={(analysisQuery.error as Error).message}
        onRetry={() => analysisQuery.refetch()}
      />
    );
  }

  const analysis = analysisQuery.data;
  if (!analysis) return null;

  return (
    <>
      <PageHeader
        title={`Analise ${analysis.id.slice(0, 8)}`}
        description={`Criada em ${new Date(analysis.created_at).toLocaleString("pt-BR")} por ${analysis.created_by}`}
        action={<StatusBadge status={analysis.status} />}
      />

      {analysis.additional_text && (
        <Section title="Texto adicional">
          <p style={{ margin: 0 }}>{analysis.additional_text}</p>
        </Section>
      )}

      <Section title="Mídias">
        {mediaQuery.isLoading && <Skeleton rows={2} />}
        {mediaQuery.isSuccess && mediaQuery.data.length === 0 && (
          <EmptyState title="Nenhuma midia anexada (apenas texto adicional)." />
        )}
        {mediaQuery.isSuccess && mediaQuery.data.length > 0 && (
          <DataTable columns={mediaColumns} rows={mediaQuery.data} getRowKey={(asset) => asset.id} />
        )}
      </Section>

      <Section title="Processamento por modalidade">
        {modalitiesQuery.isLoading && <Skeleton rows={2} />}
        {modalitiesQuery.isSuccess && modalitiesQuery.data.length === 0 && (
          <EmptyState title="Processamento ainda nao iniciado." />
        )}
        {modalitiesQuery.isSuccess && modalitiesQuery.data.length > 0 && (
          <DataTable
            columns={buildModalityColumns(mediaAssetById)}
            rows={modalitiesQuery.data}
            getRowKey={(state) => state.id}
          />
        )}
      </Section>

      <Section title="Ações">
        <div style={{ display: "flex", gap: "var(--space-3)" }}>
          {CANCELLABLE_STATUSES.has(analysis.status) && (
            <Button
              variant="danger"
              disabled={cancelMutation.isPending}
              onClick={() => cancelMutation.mutate()}
            >
              <XCircle size={14} strokeWidth={2} aria-hidden="true" />
              {cancelMutation.isPending ? "Cancelando..." : "Cancelar analise"}
            </Button>
          )}
          {RETRYABLE_STATUSES.has(analysis.status) && (
            <Button
              variant="secondary"
              disabled={retryMutation.isPending}
              onClick={() => retryMutation.mutate()}
            >
              <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
              {retryMutation.isPending ? "Reenviando..." : "Tentar novamente"}
            </Button>
          )}
          {REVIEWABLE_STATUSES.has(analysis.status) && (
            <LinkButton to={`/analyses/${analysis.id}/review`}>
              <Eye size={14} strokeWidth={2} aria-hidden="true" />
              Ver revisao/relatorio
            </LinkButton>
          )}
        </div>
      </Section>

      <p style={{ marginTop: "var(--space-5)" }}>
        <Link to="/analyses">Voltar ao historico</Link>
      </p>
    </>
  );
}
