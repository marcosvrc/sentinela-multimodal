import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye } from "lucide-react";
import styles from "./AlertsPanel.module.css";
import { DataTable, type DataTableColumn } from "@/components/data-display/DataTable";
import { Pagination } from "@/components/data-display/Pagination";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { useToast } from "@/components/feedback/ToastProvider";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { extractErrorMessage } from "@/lib/errorMessage";
import {
  acknowledgeAlert,
  escalateAlert,
  getPatientAlertsSummary,
  listPatientAlerts,
  resolveAlert,
} from "@/services/api/alerts";
import { alertSeverityLabel, alertStatusLabel } from "@/app/enumLabels";
import { AlertSeverity } from "@/types/enums.generated";
import type { AlertSeverityCounts, ClinicalAlert } from "@/types/alerts";

const PAGE_SIZE = 5;

const SEVERITY_COLOR: Record<string, string> = {
  MODERATE: "var(--risk-mild)",
  HIGH: "var(--risk-high)",
  CRITICAL: "var(--risk-critical)",
};

/** Ordem da mais alta para a mais baixa criticidade - reflete a ordem dos
 * "big numbers" e das chaves de `AlertSeverityCounts`. */
const SEVERITY_ORDER: { severity: AlertSeverity; countKey: keyof AlertSeverityCounts }[] = [
  { severity: AlertSeverity.CRITICAL, countKey: "critical" },
  { severity: AlertSeverity.HIGH, countKey: "high" },
  { severity: AlertSeverity.MODERATE, countKey: "moderate" },
];

interface AlertsPanelProps {
  devSubject: string;
  patientId: string;
  /** Quando `true`, exibe uma tabela adicional com TODOS os alertas (todas
   * as severidades), sem paginacao - usada pela exportacao em PDF, que
   * deve conter o historico completo em vez de depender do usuario ter
   * escolhido uma severidade na tela. */
  printMode?: boolean;
}

/**
 * Painel de alertas de anomalia, disparados automaticamente ao registrar
 * uma observacao clinica anomala em relacao ao historico recente do
 * paciente (ver `app.anomaly_detection`).
 *
 * Layout em dois niveis: "big numbers" com a contagem por criticidade
 * (da mais alta para a mais baixa) sempre visiveis, e a tabela detalhada
 * (paginada de 5 em 5) so aparece depois de escolher uma criticidade via
 * "Ver detalhes" - evita uma tabela longa e sem filtro como ponto de
 * entrada da tela do paciente.
 */
const PRINT_PAGE_SIZE = 200;

export function AlertsPanel({ devSubject, patientId, printMode }: AlertsPanelProps) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [selectedSeverity, setSelectedSeverity] = useState<AlertSeverity | null>(null);
  const [page, setPage] = useState(1);
  const [escalateTargetId, setEscalateTargetId] = useState<string | null>(null);
  const [resolveTargetId, setResolveTargetId] = useState<string | null>(null);
  const [escalatedTo, setEscalatedTo] = useState("");
  const [escalationReason, setEscalationReason] = useState("");
  const [resolutionNotes, setResolutionNotes] = useState("");

  const summaryQuery = useQuery({
    queryKey: ["alerts", "summary", patientId],
    queryFn: () => getPatientAlertsSummary(devSubject, patientId),
  });

  const alertsQuery = useQuery({
    queryKey: ["alerts", patientId, selectedSeverity, page],
    queryFn: () =>
      listPatientAlerts(devSubject, patientId, {
        page,
        pageSize: PAGE_SIZE,
        severity: selectedSeverity ?? undefined,
      }),
    enabled: Boolean(selectedSeverity),
  });

  // Todos os alertas (qualquer severidade), sem paginacao - so buscado
  // quando `printMode` esta ativo (exportacao em PDF).
  const allAlertsQuery = useQuery({
    queryKey: ["alerts", "print-all", patientId],
    queryFn: () =>
      listPatientAlerts(devSubject, patientId, { page: 1, pageSize: PRINT_PAGE_SIZE }),
    enabled: Boolean(printMode),
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["alerts", "summary", patientId] });
    queryClient.invalidateQueries({ queryKey: ["alerts", patientId] });
  }

  function selectSeverity(severity: AlertSeverity) {
    setSelectedSeverity(severity);
    setPage(1);
  }

  const acknowledgeMutation = useMutation({
    mutationFn: (alertId: string) => acknowledgeAlert(devSubject, alertId),
    onSuccess: () => {
      invalidate();
      showSuccess("Alerta reconhecido com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível reconhecer o alerta."));
    },
  });

  const escalateMutation = useMutation({
    mutationFn: (alertId: string) =>
      escalateAlert(devSubject, alertId, { escalated_to: escalatedTo, reason: escalationReason }),
    onSuccess: () => {
      setEscalateTargetId(null);
      setEscalatedTo("");
      setEscalationReason("");
      invalidate();
      showSuccess("Alerta escalado com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível escalar o alerta."));
    },
  });

  const resolveMutation = useMutation({
    mutationFn: (alertId: string) => resolveAlert(devSubject, alertId, { notes: resolutionNotes }),
    onSuccess: () => {
      setResolveTargetId(null);
      setResolutionNotes("");
      invalidate();
      showSuccess("Alerta encerrado com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível encerrar o alerta."));
    },
  });

  const severityCell = (a: ClinicalAlert) => (
    <span style={{ color: SEVERITY_COLOR[a.severity] ?? "inherit", fontWeight: 600 }}>
      {alertSeverityLabel(a.severity)}
    </span>
  );

  const columns: DataTableColumn<ClinicalAlert>[] = [
    { key: "severity", header: "Severidade", render: severityCell },
    { key: "signal_key", header: "Sinal", render: (a) => a.signal_key },
    {
      key: "detected_at",
      header: "Detectado em",
      render: (a) => new Date(a.detected_at).toLocaleString("pt-BR"),
    },
    { key: "expected_action", header: "Acao esperada", render: (a) => a.expected_action },
    { key: "status", header: "Status", render: (a) => alertStatusLabel(a.status) },
    {
      key: "actions",
      header: "Acoes",
      render: (a) => (
        <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
          {a.status === "OPEN" && (
            <Button
              variant="secondary"
              onClick={() => acknowledgeMutation.mutate(a.id)}
              disabled={acknowledgeMutation.isPending}
            >
              Reconhecer
            </Button>
          )}
          {a.status !== "RESOLVED" && (
            <Button variant="secondary" onClick={() => setEscalateTargetId(a.id)}>
              Escalar
            </Button>
          )}
          {a.status !== "RESOLVED" && (
            <Button variant="secondary" onClick={() => setResolveTargetId(a.id)}>
              Encerrar
            </Button>
          )}
        </div>
      ),
    },
  ];

  // Tabela impressa no PDF: mesmas colunas informativas, sem a coluna de
  // acoes (nao faz sentido em um snapshot estatico) e sem paginacao.
  const printColumns: DataTableColumn<ClinicalAlert>[] = [
    { key: "severity", header: "Severidade", render: severityCell },
    { key: "signal_key", header: "Sinal", render: (a) => a.signal_key },
    {
      key: "detected_at",
      header: "Detectado em",
      render: (a) => new Date(a.detected_at).toLocaleString("pt-BR"),
    },
    { key: "expected_action", header: "Acao esperada", render: (a) => a.expected_action },
    { key: "status", header: "Status", render: (a) => alertStatusLabel(a.status) },
  ];

  return (
    <section style={{ marginBottom: "var(--space-6)" }}>
      <h2 style={{ fontSize: 20, marginBottom: "var(--space-3)" }}>
        Alertas de anomalia (monitoramento preventivo)
      </h2>
      <p style={{ color: "var(--color-text-muted)", fontSize: 14, marginBottom: "var(--space-4)" }}>
        Gerados automaticamente quando uma nova observacao clinica destoa do historico recente do
        proprio paciente (metodo estatistico, nao um diagnostico). Nunca altera a classificacao de
        risco do laudo, que continua exclusivamente do motor de regras.
      </p>

      {summaryQuery.isLoading && <Skeleton rows={1} />}
      {summaryQuery.isError && (
        <ErrorState
          description={(summaryQuery.error as Error).message}
          onRetry={() => summaryQuery.refetch()}
        />
      )}
      {summaryQuery.isSuccess && (
        <div className={styles.cardsGrid}>
          {SEVERITY_ORDER.map(({ severity, countKey }) => {
            const count = summaryQuery.data[countKey];
            const color = SEVERITY_COLOR[severity];
            const isSelected = selectedSeverity === severity;
            return (
              <button
                key={severity}
                type="button"
                className={[styles.card, isSelected && styles.cardSelected]
                  .filter(Boolean)
                  .join(" ")}
                style={{ color }}
                onClick={() => selectSeverity(severity)}
                aria-pressed={isSelected}
              >
                <span className={styles.cardNumber}>{count}</span>
                <span className={styles.cardLabel}>{alertSeverityLabel(severity)}</span>
                <span className={styles.cardHint}>
                  <Eye size={12} strokeWidth={2} aria-hidden="true" style={{ marginRight: 4 }} />
                  Ver detalhes
                </span>
              </button>
            );
          })}
        </div>
      )}

      {summaryQuery.isSuccess &&
        summaryQuery.data.critical === 0 &&
        summaryQuery.data.high === 0 &&
        summaryQuery.data.moderate === 0 && (
          <EmptyState title="Nenhum alerta de anomalia para este paciente." />
        )}

      {selectedSeverity && !printMode && (
        <div style={{ marginTop: "var(--space-2)" }}>
          <div className={styles.detailHeader}>
            <h3 style={{ fontSize: 16, margin: 0 }}>
              Detalhes - {alertSeverityLabel(selectedSeverity)}
            </h3>
            <Button type="button" variant="secondary" onClick={() => setSelectedSeverity(null)}>
              Fechar detalhes
            </Button>
          </div>

          {alertsQuery.isLoading && <Skeleton rows={2} />}
          {alertsQuery.isError && (
            <ErrorState
              description={(alertsQuery.error as Error).message}
              onRetry={() => alertsQuery.refetch()}
            />
          )}
          {alertsQuery.isSuccess && alertsQuery.data.items.length === 0 && (
            <EmptyState title="Nenhum alerta desta criticidade para este paciente." />
          )}
          {alertsQuery.isSuccess && alertsQuery.data.items.length > 0 && (
            <>
              <DataTable columns={columns} rows={alertsQuery.data.items} getRowKey={(a) => a.id} />
              <Pagination
                page={alertsQuery.data.page}
                totalPages={alertsQuery.data.total_pages}
                totalItems={alertsQuery.data.total_items}
                onPageChange={setPage}
              />
            </>
          )}
        </div>
      )}

      {printMode && (
        <div style={{ marginTop: "var(--space-2)" }}>
          <h3 style={{ fontSize: 16, margin: "0 0 var(--space-2) 0" }}>
            Todos os alertas registrados
          </h3>
          {allAlertsQuery.isLoading && <Skeleton rows={2} />}
          {allAlertsQuery.isSuccess && allAlertsQuery.data.items.length === 0 && (
            <EmptyState title="Nenhum alerta de anomalia para este paciente." />
          )}
          {allAlertsQuery.isSuccess && allAlertsQuery.data.items.length > 0 && (
            <DataTable
              columns={printColumns}
              rows={allAlertsQuery.data.items}
              getRowKey={(a) => a.id}
            />
          )}
        </div>
      )}

      {escalateTargetId && (
        <form
          style={{
            marginTop: "var(--space-4)",
            maxWidth: 480,
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-card)",
            padding: "var(--space-4)",
          }}
          onSubmit={(event) => {
            event.preventDefault();
            escalateMutation.mutate(escalateTargetId);
          }}
        >
          <p>Escalar este alerta para outro responsavel.</p>
          <TextField
            id="escalate-to"
            label="Escalar para"
            required
            value={escalatedTo}
            onChange={(event) => setEscalatedTo(event.target.value)}
          />
          <TextField
            id="escalate-reason"
            label="Motivo"
            required
            value={escalationReason}
            onChange={(event) => setEscalationReason(event.target.value)}
          />
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button type="submit" disabled={escalateMutation.isPending}>
              {escalateMutation.isPending ? "Enviando..." : "Confirmar"}
            </Button>
            <Button type="button" variant="secondary" onClick={() => setEscalateTargetId(null)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {resolveTargetId && (
        <form
          style={{
            marginTop: "var(--space-4)",
            maxWidth: 480,
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-card)",
            padding: "var(--space-4)",
          }}
          onSubmit={(event) => {
            event.preventDefault();
            resolveMutation.mutate(resolveTargetId);
          }}
        >
          <p>Encerrar este alerta.</p>
          <TextField
            id="resolve-notes"
            label="Notas de encerramento"
            required
            value={resolutionNotes}
            onChange={(event) => setResolutionNotes(event.target.value)}
          />
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button type="submit" disabled={resolveMutation.isPending}>
              {resolveMutation.isPending ? "Enviando..." : "Confirmar"}
            </Button>
            <Button type="button" variant="secondary" onClick={() => setResolveTargetId(null)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}
