import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, RotateCcw, Trash2 } from "lucide-react";
import { DataTable, type DataTableColumn } from "@/components/data-display/DataTable";
import { Pagination } from "@/components/data-display/Pagination";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { useToast } from "@/components/feedback/ToastProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Section } from "@/components/ui/Section";
import { SelectField } from "@/components/ui/SelectField";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TextField } from "@/components/ui/TextField";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useDevSession } from "@/hooks/useDevSession";
import { extractErrorMessage } from "@/lib/errorMessage";
import { listUsers, updateUser } from "@/services/api/administration";
import { UserRole } from "@/types/enums.generated";
import { roleLabel } from "@/app/enumLabels";
import type { AdminUser } from "@/types/administration";

const PAGE_SIZE = 5;

const ROLE_FILTER_OPTIONS = [
  { value: "", label: "Todos os papeis" },
  ...Object.values(UserRole).map((role) => ({ value: role, label: roleLabel(role) })),
];

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "active", label: "Ativo" },
  { value: "inactive", label: "Desativado" },
];

/**
 * Tela de usuarios e papeis de acesso (rota `/admin/users`).
 *
 * Sem formulario de inclusao: a conta de acesso e criada junto com o
 * cadastro de Funcionario (`/admin/employees`) - esta tela nao tem (nem
 * exibe) nome do profissional, so o Identificador Externo, Papel, Status
 * e Acoes, com filtro por identificador, papel e status. "Excluir"
 * desativa a conta (nunca apaga o registro - auditoria e analises
 * passadas continuam integras).
 */
export function UsersPage() {
  const { subject } = useDevSession();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [page, setPage] = useState(1);

  const [searchInput, setSearchInput] = useState("");
  const searchFilter = useDebouncedValue(searchInput);
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const activeFilter =
    statusFilter === "active" ? true : statusFilter === "inactive" ? false : undefined;

  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [editingRole, setEditingRole] = useState<string>(UserRole.MEDICO);

  const [deactivateTarget, setDeactivateTarget] = useState<AdminUser | null>(null);

  const usersQuery = useQuery({
    queryKey: ["admin", "users", subject, page, searchFilter, roleFilter, statusFilter],
    queryFn: () =>
      listUsers(subject as string, {
        page,
        pageSize: PAGE_SIZE,
        search: searchFilter.trim(),
        role: roleFilter,
        active: activeFilter,
      }),
    enabled: Boolean(subject),
  });

  const roleMutation = useMutation({
    mutationFn: (user: AdminUser) => updateUser(subject as string, user.id, { role: editingRole }),
    onSuccess: () => {
      setEditingUser(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      showSuccess("Papel atualizado com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível atualizar o papel."));
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: (user: AdminUser) => updateUser(subject as string, user.id, { active: !user.active }),
    onSuccess: (_data, user) => {
      setDeactivateTarget(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      showSuccess(user.active ? "Usuário excluído com sucesso." : "Usuário reativado com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível concluir a operação."));
    },
  });

  function openEditRole(user: AdminUser) {
    setEditingUser(user);
    setEditingRole(user.role);
  }

  const columns: DataTableColumn<AdminUser>[] = [
    { key: "external_subject", header: "Identificador externo", render: (u) => u.external_subject },
    { key: "role", header: "Papel", render: (u) => roleLabel(u.role) },
    {
      key: "active",
      header: "Status",
      render: (u) => <StatusBadge status={u.active ? "ATIVO" : "DESATIVADO"} />,
    },
    {
      key: "actions",
      header: "Acoes",
      render: (u) => (
        <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
          <Button type="button" variant="secondary" onClick={() => openEditRole(u)}>
            <Pencil size={14} strokeWidth={2} aria-hidden="true" />
            Editar papel
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
        title="Usuarios e papeis de acesso"
        description="Contas de acesso sao criadas junto com o cadastro de funcionário (Administração → Funcionário). Desativar aqui nunca apaga o registro; apenas impede novas autenticações."
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
              id="user-filter-search"
              label="Identificador externo"
              placeholder="Ex.: dev-medico"
              value={searchInput}
              onChange={(event) => {
                setSearchInput(event.target.value);
                setPage(1);
              }}
            />
            <SelectField
              id="user-filter-role"
              label="Papel"
              options={ROLE_FILTER_OPTIONS}
              value={roleFilter}
              onChange={(event) => {
                setRoleFilter(event.target.value);
                setPage(1);
              }}
            />
            <SelectField
              id="user-filter-status"
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

      {usersQuery.isLoading && <Skeleton rows={3} />}
      {usersQuery.isError && (
        <ErrorState
          description={(usersQuery.error as Error).message}
          onRetry={() => usersQuery.refetch()}
        />
      )}
      {usersQuery.isSuccess && usersQuery.data.items.length === 0 && (
        <EmptyState
          title={
            searchFilter || roleFilter || statusFilter
              ? "Nenhum usuario encontrado para os filtros informados"
              : "Nenhum usuario cadastrado ainda"
          }
        />
      )}
      {usersQuery.isSuccess && usersQuery.data.items.length > 0 && (
        <Section title="Usuários cadastrados">
          <DataTable columns={columns} rows={usersQuery.data.items} getRowKey={(u) => u.id} />
          <Pagination
            page={usersQuery.data.page}
            totalPages={usersQuery.data.total_pages}
            totalItems={usersQuery.data.total_items}
            onPageChange={setPage}
          />
        </Section>
      )}

      <ConfirmDialog
        open={Boolean(editingUser)}
        title="Editar papel do usuario"
        description={`Confirme a troca de papel para "${editingUser?.external_subject}".`}
        confirmLabel="Salvar"
        pending={roleMutation.isPending}
        onConfirm={() => editingUser && roleMutation.mutate(editingUser)}
        onCancel={() => setEditingUser(null)}
      >
        <SelectField
          id="edit-user-role"
          label="Papel"
          options={Object.values(UserRole).map((role) => ({ value: role, label: roleLabel(role) }))}
          value={editingRole}
          onChange={(event) => setEditingRole(event.target.value)}
        />
      </ConfirmDialog>

      <ConfirmDialog
        open={Boolean(deactivateTarget)}
        title={deactivateTarget?.active ? "Excluir usuario" : "Reativar usuario"}
        description={
          deactivateTarget?.active
            ? `O usuario "${deactivateTarget?.external_subject}" sera desativado e nao podera mais autenticar. O registro nao e apagado (auditoria e analises passadas continuam integras) e pode ser reativado depois.`
            : `O usuario "${deactivateTarget?.external_subject}" voltara a poder autenticar normalmente.`
        }
        confirmLabel={deactivateTarget?.active ? "Excluir" : "Reativar"}
        variant={deactivateTarget?.active ? "danger" : "primary"}
        pending={toggleActiveMutation.isPending}
        onConfirm={() => deactivateTarget && toggleActiveMutation.mutate(deactivateTarget)}
        onCancel={() => setDeactivateTarget(null)}
      />
    </section>
  );
}
