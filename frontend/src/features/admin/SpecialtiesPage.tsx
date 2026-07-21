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
import { createSpecialty, listSpecialties, updateSpecialty } from "@/services/api/administration";
import { ApiRequestError } from "@/types/api";
import type { MedicalSpecialty } from "@/types/administration";

const PAGE_SIZE = 5;

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "active", label: "Ativa" },
  { value: "inactive", label: "Inativa" },
];

/**
 * Tela de especialidade medica (rota `/admin/specialties`). Segue o
 * padrao de CRUD completo das telas de administracao: inclusao e edicao
 * via modal, consulta paginada e filtrada (nome/status), e "exclusao"
 * como desativacao confirmada.
 */
export function SpecialtiesPage() {
  const { subject } = useDevSession();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [page, setPage] = useState(1);

  const [nameFilterInput, setNameFilterInput] = useState("");
  const nameFilter = useDebouncedValue(nameFilterInput);
  const [statusFilter, setStatusFilter] = useState("");

  const [formOpen, setFormOpen] = useState(false);
  const [editingSpecialty, setEditingSpecialty] = useState<MedicalSpecialty | null>(null);
  const [name, setName] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const [deactivateTarget, setDeactivateTarget] = useState<MedicalSpecialty | null>(null);

  const activeFilter =
    statusFilter === "active" ? true : statusFilter === "inactive" ? false : undefined;

  const query = useQuery({
    queryKey: ["admin", "specialties", subject, page, nameFilter, statusFilter],
    queryFn: () =>
      listSpecialties(subject as string, {
        page,
        pageSize: PAGE_SIZE,
        search: nameFilter.trim(),
        active: activeFilter,
      }),
    enabled: Boolean(subject),
  });

  const visibleItems = query.data?.items ?? [];

  function openCreateForm() {
    setEditingSpecialty(null);
    setName("");
    setFieldErrors({});
    setFormOpen(true);
  }

  function openEditForm(specialty: MedicalSpecialty) {
    setEditingSpecialty(specialty);
    setName(specialty.name);
    setFieldErrors({});
    setFormOpen(true);
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      editingSpecialty
        ? updateSpecialty(subject as string, editingSpecialty.id, { name })
        : createSpecialty(subject as string, { name }),
    onSuccess: () => {
      setFormOpen(false);
      queryClient.invalidateQueries({ queryKey: ["admin", "specialties"] });
      showSuccess(
        editingSpecialty ? "Especialidade atualizada com sucesso." : "Especialidade criada com sucesso.",
      );
    },
    onError: (error: unknown) => {
      if (error instanceof ApiRequestError) setFieldErrors(error.fieldErrors);
      showError(extractErrorMessage(error, "Não foi possível salvar a especialidade."));
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (specialty: MedicalSpecialty) =>
      updateSpecialty(subject as string, specialty.id, { active: !specialty.active }),
    onSuccess: (_data, specialty) => {
      setDeactivateTarget(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "specialties"] });
      showSuccess(
        specialty.active ? "Especialidade excluída com sucesso." : "Especialidade reativada com sucesso.",
      );
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível concluir a operação."));
    },
  });

  const columns: DataTableColumn<MedicalSpecialty>[] = [
    { key: "name", header: "Especialidade", render: (s) => s.name },
    {
      key: "active",
      header: "Status",
      render: (s) => <StatusBadge status={s.active ? "ATIVA" : "INATIVA"} />,
    },
    {
      key: "actions",
      header: "Acoes",
      render: (s) => (
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button type="button" variant="secondary" onClick={() => openEditForm(s)}>
            <Pencil size={14} strokeWidth={2} aria-hidden="true" />
            Editar
          </Button>
          <Button type="button" variant="danger" onClick={() => setDeactivateTarget(s)}>
            {s.active ? (
              <Trash2 size={14} strokeWidth={2} aria-hidden="true" />
            ) : (
              <RotateCcw size={14} strokeWidth={2} aria-hidden="true" />
            )}
            {s.active ? "Excluir" : "Reativar"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <section>
      <PageHeader
        title="Especialidades medicas"
        description="Cadastro de especialidades usadas para vincular funcionarios."
        action={
          <Button type="button" onClick={openCreateForm} disabled={!subject}>
            <Plus size={16} strokeWidth={2} aria-hidden="true" />
            Nova especialidade
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
              id="specialty-filter-name"
              label="Nome da especialidade"
              placeholder="Ex.: Cardiologia"
              value={nameFilterInput}
              onChange={(event) => {
                setNameFilterInput(event.target.value);
                setPage(1);
              }}
            />
            <SelectField
              id="specialty-filter-status"
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
      {query.isSuccess && visibleItems.length === 0 && (
        <EmptyState
          title={
            nameFilter || statusFilter
              ? "Nenhuma especialidade encontrada para os filtros informados"
              : "Nenhuma especialidade cadastrada ainda"
          }
        />
      )}
      {query.isSuccess && visibleItems.length > 0 && (
        <Section title="Especialidades cadastradas">
          <DataTable columns={columns} rows={visibleItems} getRowKey={(s) => s.id} />
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
        title={editingSpecialty ? "Editar especialidade" : "Nova especialidade"}
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
            id="specialty-name"
            label="Nome da especialidade"
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
        title={deactivateTarget?.active ? "Excluir especialidade" : "Reativar especialidade"}
        description={
          deactivateTarget?.active
            ? `A especialidade "${deactivateTarget?.name}" sera desativada e deixara de aparecer nas novas vinculacoes de funcionarios. O registro nao e apagado e pode ser reativado depois.`
            : `A especialidade "${deactivateTarget?.name}" voltara a ficar disponivel para vinculacao de funcionarios.`
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
