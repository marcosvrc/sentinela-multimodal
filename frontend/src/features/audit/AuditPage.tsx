import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Filter, FileJson } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/data-display/DataTable";
import { Pagination } from "@/components/data-display/Pagination";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Section } from "@/components/ui/Section";
import { TextField } from "@/components/ui/TextField";
import { useDevSession } from "@/hooks/useDevSession";
import { listAuditEvents } from "@/services/api/audit";
import { auditCategoryLabel, auditResultLabel } from "@/app/enumLabels";
import type { AuditEvent } from "@/types/audit";

const PAGE_SIZE = 5;

function buildColumns(onViewDetails: (event: AuditEvent) => void): DataTableColumn<AuditEvent>[] {
  return [
    {
      key: "occurred_at",
      header: "Quando",
      render: (event) => new Date(event.occurred_at).toLocaleString("pt-BR"),
    },
    { key: "actor", header: "Ator", render: (event) => event.actor },
    {
      key: "category",
      header: "Categoria",
      render: (event) => auditCategoryLabel(event.category),
    },
    { key: "action", header: "Acao", render: (event) => event.action },
    { key: "resource_type", header: "Recurso", render: (event) => event.resource_type },
    { key: "result", header: "Resultado", render: (event) => auditResultLabel(event.result) },
    {
      key: "details",
      header: "Detalhes",
      render: (event) => (
        <button
          type="button"
          onClick={() => onViewDetails(event)}
          aria-label={`Ver detalhes completos em JSON do evento ${event.sequence}`}
          title="Ver detalhes completos (JSON)"
          style={{
            display: "inline-flex",
            alignItems: "center",
            background: "transparent",
            border: "none",
            cursor: "pointer",
            color: "var(--color-primary-800)",
            padding: 0,
          }}
        >
          <FileJson size={18} strokeWidth={2} aria-hidden="true" />
        </button>
      ),
    },
  ];
}

export function AuditPage() {
  const { subject } = useDevSession();
  const [page, setPage] = useState(1);
  const [actorFilter, setActorFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [detailsTarget, setDetailsTarget] = useState<AuditEvent | null>(null);
  const columns = buildColumns(setDetailsTarget);

  const query = useQuery({
    queryKey: ["audit-events", subject, page, actorFilter, actionFilter],
    queryFn: () =>
      listAuditEvents(subject as string, {
        actor: actorFilter,
        action: actionFilter,
        page,
        pageSize: PAGE_SIZE,
      }),
    enabled: Boolean(subject),
  });

  return (
    <>
      <PageHeader
        title="Auditoria"
        description="Trilha de eventos append-only do sistema (acesso restrito a auditor/administradores)."
      />

      {!subject && (
        <EmptyState title="Configure o usuario de desenvolvimento acima para continuar." />
      )}

      {subject && (
        <Section title="Filtros">
          <form
            style={{ display: "flex", gap: "var(--space-3)", alignItems: "flex-end", flexWrap: "wrap" }}
            onSubmit={(event) => {
              event.preventDefault();
              setPage(1);
            }}
          >
            <TextField
              id="actor-filter"
              label="Ator"
              value={actorFilter}
              onChange={(event) => setActorFilter(event.target.value)}
              placeholder="external_subject"
            />
            <TextField
              id="action-filter"
              label="Acao"
              value={actionFilter}
              onChange={(event) => setActionFilter(event.target.value)}
              placeholder="ex: ANALYSIS_CREATE"
            />
            <Button type="submit" variant="secondary">
              <Filter size={14} strokeWidth={2} aria-hidden="true" />
              Filtrar
            </Button>
          </form>
        </Section>
      )}

      {subject && query.isLoading && <Skeleton rows={5} />}

      {subject && query.isError && (
        <ErrorState description={(query.error as Error).message} onRetry={() => query.refetch()} />
      )}

      {subject && query.isSuccess && query.data.items.length === 0 && (
        <EmptyState title="Nenhum evento encontrado para os filtros informados." />
      )}

      {subject && query.isSuccess && query.data.items.length > 0 && (
        <Section title="Eventos de auditoria">
          <DataTable columns={columns} rows={query.data.items} getRowKey={(event) => event.id} />
          <Pagination
            page={query.data.page}
            totalPages={query.data.total_pages}
            totalItems={query.data.total_items}
            onPageChange={setPage}
          />
        </Section>
      )}

      <Modal
        open={Boolean(detailsTarget)}
        title={`Detalhes do evento #${detailsTarget?.sequence ?? ""}`}
        onClose={() => setDetailsTarget(null)}
        size="lg"
      >
        {detailsTarget && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-muted)" }}>
                Hash de integridade deste evento (encadeado ao evento anterior):
              </p>
              <code
                style={{
                  display: "block",
                  wordBreak: "break-all",
                  fontSize: 12,
                  background: "var(--color-background)",
                  padding: "var(--space-2)",
                  borderRadius: "var(--radius-field)",
                  marginTop: "var(--space-1)",
                }}
              >
                event_hash: {detailsTarget.event_hash}
                <br />
                prev_hash: {detailsTarget.prev_hash ?? "(primeiro evento da cadeia)"}
              </code>
            </div>
            <div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-muted)" }}>
                Detalhe completo da acao (event_metadata):
              </p>
              <pre
                style={{
                  margin: "var(--space-1) 0 0",
                  padding: "var(--space-3)",
                  background: "var(--color-background)",
                  borderRadius: "var(--radius-field)",
                  fontSize: 12,
                  overflowX: "auto",
                  maxHeight: 400,
                }}
              >
                {JSON.stringify(detailsTarget.event_metadata, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
