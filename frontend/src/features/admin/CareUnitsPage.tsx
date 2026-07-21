import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { DataTable, type DataTableColumn } from "@/components/data-display/DataTable";
import { Pagination } from "@/components/data-display/Pagination";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { useToast } from "@/components/feedback/ToastProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Modal } from "@/components/ui/Modal";
import { Section } from "@/components/ui/Section";
import { SelectField } from "@/components/ui/SelectField";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TextField } from "@/components/ui/TextField";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useDevSession } from "@/hooks/useDevSession";
import { extractErrorMessage } from "@/lib/errorMessage";
import { createCareUnit, listCareUnits, updateCareUnit } from "@/services/api/administration";
import { ApiRequestError } from "@/types/api";
import type { CareUnit } from "@/types/administration";

const PAGE_SIZE = 5;

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "active", label: "Ativa" },
  { value: "inactive", label: "Inativa" },
];

/**
 * Tela de unidades assistenciais (rota `/admin/care-units`). Unidade e um
 * dos dois eixos do vinculo assistencial: acesso a paciente depende de
 * papel + instituicao + unidade + vinculo. O outro eixo (o vinculo
 * profissional-paciente em si) e criado na propria tela do paciente
 * (`PatientDetailPage` -> `POST /patients/{id}/care-assignments`), nao
 * aqui, porque depende de escolher um paciente especifico.
 *
 * Segue o padrao de CRUD completo das telas de administracao, com filtro
 * por nome e status.
 */
export function CareUnitsPage() {
  const { subject } = useDevSession();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [page, setPage] = useState(1);

  const [nameFilterInput, setNameFilterInput] = useState("");
  const nameFilter = useDebouncedValue(nameFilterInput);
  const [statusFilter, setStatusFilter] = useState("");
  const activeFilter =
    statusFilter === "active" ? true : statusFilter === "inactive" ? false : undefined;

  const [formOpen, setFormOpen] = useState(false);
  const [editingUnit, setEditingUnit] = useState<CareUnit | null>(null);
  const [name, setName] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const [deactivateTarget, setDeactivateTarget] = useState<CareUnit | null>(null);

  const query = useQuery({
    queryKey: ["admin", "care-units", subject, page, nameFilter, statusFilter],
    queryFn: () =>
      listCareUnits(subject as string, {
        page,
        pageSize: PAGE_SIZE,
        search: nameFilter.trim(),
        active: activeFilter,
      }),
    enabled: Boolean(subject),
  });

  function openCreateForm() {
    setEditingUnit(null);
    setName("");
    setFieldErrors({});
    setFormOpen(true);
  }

  function openEditForm(unit: CareUnit) {
    setEditingUnit(unit);
    setName(unit.name);
    setFieldErrors({});
    setFormOpen(true);
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      editingUnit
        ? updateCareUnit(subject as string, editingUnit.id, { name })
        : createCareUnit(subject as string, { name }),
    onSuccess: () => {
      setFormOpen(false);
      queryClient.invalidateQueries({ queryKey: ["admin", "care-units"] });
      showSuccess(editingUnit ? "Unidade atualizada com sucesso." : "Unidade criada com sucesso.");
    },
    onError: (error: unknown) => {
      if (error instanceof ApiRequestError) setFieldErrors(error.fieldErrors);
      showError(extractErrorMessage(error, "Não foi possível salvar a unidade."));
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (unit: CareUnit) =>
      updateCareUnit(subject as string, unit.id, { active: !unit.active }),
    onSuccess: (_data, unit) => {
      setDeactivateTarget(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "care-units"] });
      showSuccess(unit.active ? "Unidade excluída com sucesso." : "Unidade reativada com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível concluir a operação."));
    },
  });

  const columns: DataTableColumn<CareUnit>[] = [
    { key: "name", header: "Unidade", render: (u) => u.name },
    {
      key: "active",
      header: "Status",
      render: (u) => <StatusBadge status={u.active ? "ATIVA" : "INATIVA"} />,
    },
    {
      key: "actions",
      header: "Acoes",
      render: (u) => (
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button type="button" variant="secondary" onClick={() => openEditForm(u)}>
            <Pencil size={14} strokeWidth={2} aria-hidden="true" />
            Editar
          </Button>
          <Button type="button" variant="danger" onClick={() => setDeactivateTarget(u)}>
            {u.active ? (
              <Trash2 size={14} strokeWidth={2} aria-hidden="true" />
            ) : (
              <RotateCcw size={14} strokeWidth={2} aria-hidden="true" />
            )}
            {u.active ? "Excluir" : "Reativar"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <section>
      <PageHeader
        title="Unidades assistenciais"
        description="Alas, setores e ambulatorios usados no vinculo assistencial de pacientes."
        action={
          <Button type="button" onClick={openCreateForm} disabled={!subject}>
            <Plus size={16} strokeWidth={2} aria-hidden="true" />
            Nova unidade
          </Button>
        }
      />

      {!subject && <p role="alert">Configure o usuario de desenvolvimento para continuar.</p>}

      {subject && (
        <Section title="Filtros">
          <div
            style={{
              display: "flex",
              gap: "var(--space-3)",
              alignItems: "flex-end",
              flexWrap: "wrap",
            }}
          >
            <TextField
              id="care-unit-filter-name"
              label="Nome da unidade"
              placeholder="Ex.: UTI Adulto"
              value={nameFilterInput}
              onChange={(event) => {
                setNameFilterInput(event.target.value);
                setPage(1);
              }}
            />
            <SelectField
              id="care-unit-filter-status"
              label="Status"
              options={STATUS_OPTIONS}
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setPage(1);
              }}
            />
          </div>
        </Section>
      )}

      {query.isLoading && <Skeleton rows={3} />}
      {query.isError && (
        <ErrorState description={(query.error as Error).message} onRetry={() => query.refetch()} />
      )}
      {query.isSuccess && query.data.items.length === 0 && (
        <EmptyState
          title={
            nameFilter || statusFilter
              ? "Nenhuma unidade encontrada para os filtros informados"
              : "Nenhuma unidade assistencial cadastrada ainda"
          }
        />
      )}
      {query.isSuccess && query.data.items.length > 0 && (
        <Section title="Unidades cadastradas">
          <DataTable columns={columns} rows={query.data.items} getRowKey={(u) => u.id} />
          <Pagination
            page={query.data.page}
            totalPages={query.data.total_pages}
            totalItems={query.data.total_items}
            onPageChange={setPage}
          />
        </Section>
      )}

      <Modal
        open={formOpen}
        title={editingUnit ? "Editar unidade assistencial" : "Nova unidade assistencial"}
        onClose={() => setFormOpen(false)}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setFieldErrors({});
            saveMutation.mutate();
          }}
        >
          <TextField
            id="care-unit-name"
            label="Nome da unidade"
            placeholder="Ex.: UTI Adulto"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            error={fieldErrors.name}
          />

          <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setFormOpen(false)}
              disabled={saveMutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(deactivateTarget)}
        title={deactivateTarget?.active ? "Excluir unidade assistencial" : "Reativar unidade"}
        description={
          deactivateTarget?.active
            ? `A unidade "${deactivateTarget?.name}" sera desativada e deixara de aparecer em novos vinculos assistenciais. O registro nao e apagado e pode ser reativado depois.`
            : `A unidade "${deactivateTarget?.name}" voltara a ficar disponivel para novos vinculos assistenciais.`
        }
        confirmLabel={deactivateTarget?.active ? "Excluir" : "Reativar"}
        variant={deactivateTarget?.active ? "danger" : "primary"}
        pending={deactivateMutation.isPending}
        onConfirm={() => deactivateTarget && deactivateMutation.mutate(deactivateTarget)}
        onCancel={() => setDeactivateTarget(null)}
      />
    </section>
  );
}
