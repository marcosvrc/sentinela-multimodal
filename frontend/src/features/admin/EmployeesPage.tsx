import { useEffect, useState, type CSSProperties } from "react";
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
import {
  createEmployee,
  getAvailableRoles,
  listEmployees,
  listSpecialties,
  updateEmployee,
} from "@/services/api/administration";
import { ApiRequestError } from "@/types/api";
import { roleLabel } from "@/app/enumLabels";
import type {
  Employee,
  EmployeeCreateInput,
  EmployeeProfessionalType,
} from "@/types/administration";

const PAGE_SIZE = 5;

const formGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  columnGap: "var(--space-4)",
};

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "active", label: "Ativo" },
  { value: "inactive", label: "Inativo" },
];

const PROFESSIONAL_TYPE_FORM_OPTIONS = [
  { value: "MEDICO", label: "Médico" },
  { value: "ENFERMEIRO", label: "Enfermeiro" },
];

const EMPTY_EMPLOYEE_FORM: EmployeeCreateInput = {
  full_name: "",
  cpf: "",
  registration_number: "",
  email: "",
  specialty_id: undefined,
  professional_type: "MEDICO",
  role: "MEDICO",
  external_subject: "",
};

/**
 * Tela de funcionarios (rota `/admin/employees`). Segue o padrao de CRUD
 * completo das telas de administracao: inclusao e edicao via modal,
 * consulta paginada e filtrada (matricula/nome/status), e "exclusao"
 * como desativacao confirmada.
 *
 * O cadastro cria tambem a conta de acesso vinculada (papel escolhido
 * dentre as opcoes permitidas para o tipo profissional - Enfermeiro so
 * pode ser ENFERMEIRO; Medico pode ser MEDICO ou um papel administrativo/
 * de auditoria) - ver `/admin/users`, que passou a ser somente
 * consulta/gestao dessas contas.
 */
export function EmployeesPage() {
  const { subject } = useDevSession();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [page, setPage] = useState(1);

  const [nameFilterInput, setNameFilterInput] = useState("");
  const nameFilter = useDebouncedValue(nameFilterInput);
  const [registrationFilterInput, setRegistrationFilterInput] = useState("");
  const registrationFilter = useDebouncedValue(registrationFilterInput);
  const [statusFilter, setStatusFilter] = useState("");
  const activeFilter =
    statusFilter === "active" ? true : statusFilter === "inactive" ? false : undefined;
  // O backend usa a mesma caixa de busca para nome OU matricula - os dois
  // filtros de UI convergem para o mesmo parametro `search`.
  const searchFilter = (nameFilter || registrationFilter).trim();

  const [formOpen, setFormOpen] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [form, setForm] = useState<EmployeeCreateInput>(EMPTY_EMPLOYEE_FORM);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const [deactivateTarget, setDeactivateTarget] = useState<Employee | null>(null);

  const specialtiesQuery = useQuery({
    queryKey: ["admin", "specialties", subject],
    queryFn: () => listSpecialties(subject as string, { pageSize: 100 }),
    enabled: Boolean(subject),
  });
  const employeesQuery = useQuery({
    queryKey: ["admin", "employees", subject, page, searchFilter, statusFilter],
    queryFn: () =>
      listEmployees(subject as string, {
        page,
        pageSize: PAGE_SIZE,
        search: searchFilter,
        active: activeFilter,
      }),
    enabled: Boolean(subject),
  });

  const availableRolesQuery = useQuery({
    queryKey: ["admin", "employees", "available-roles", subject, form.professional_type],
    queryFn: () => getAvailableRoles(subject as string, form.professional_type),
    enabled: Boolean(subject) && formOpen,
  });

  // Quando o tipo profissional muda para um que nao permite mais o papel
  // selecionado (ex.: trocou de Medico para Enfermeiro com papel
  // ADMINISTRADOR_TECNICO selecionado), recai no primeiro papel permitido.
  useEffect(() => {
    if (!availableRolesQuery.data) return;
    if (!availableRolesQuery.data.roles.includes(form.role)) {
      setForm((current) => ({ ...current, role: availableRolesQuery.data!.roles[0] }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableRolesQuery.data]);

  function updateField<K extends keyof EmployeeCreateInput>(key: K, value: EmployeeCreateInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function openCreateForm() {
    setEditingEmployee(null);
    setForm(EMPTY_EMPLOYEE_FORM);
    setFieldErrors({});
    setFormOpen(true);
  }

  function openEditForm(employee: Employee) {
    setEditingEmployee(employee);
    setForm({
      full_name: employee.full_name,
      cpf: employee.cpf,
      registration_number: employee.registration_number,
      email: employee.email,
      specialty_id: employee.specialty_id ?? undefined,
      professional_type: employee.professional_type,
      role: employee.role ?? employee.professional_type,
      external_subject: employee.external_subject ?? "",
    });
    setFieldErrors({});
    setFormOpen(true);
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      editingEmployee
        ? updateEmployee(subject as string, editingEmployee.id, {
            full_name: form.full_name,
            email: form.email,
            specialty_id: form.specialty_id || undefined,
            role: form.role,
          })
        : createEmployee(subject as string, {
            ...form,
            specialty_id: form.specialty_id || undefined,
          }),
    onSuccess: () => {
      setFormOpen(false);
      queryClient.invalidateQueries({ queryKey: ["admin", "employees"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      showSuccess(
        editingEmployee ? "Funcionário atualizado com sucesso." : "Funcionário criado com sucesso.",
      );
    },
    onError: (error: unknown) => {
      if (error instanceof ApiRequestError) setFieldErrors(error.fieldErrors);
      showError(extractErrorMessage(error, "Não foi possível salvar o funcionário."));
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (employee: Employee) =>
      updateEmployee(subject as string, employee.id, { active: !employee.active }),
    onSuccess: (_data, employee) => {
      setDeactivateTarget(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "employees"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      showSuccess(
        employee.active ? "Funcionário excluído com sucesso." : "Funcionário reativado com sucesso.",
      );
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível concluir a operação."));
    },
  });

  const specialtyOptions = [
    { value: "", label: "Sem especialidade vinculada" },
    ...(specialtiesQuery.data?.items.map((s) => ({ value: s.id, label: s.name })) ?? []),
  ];

  const specialtyNameById = new Map(
    (specialtiesQuery.data?.items ?? []).map((s) => [s.id, s.name]),
  );

  const roleOptions = (
    availableRolesQuery.data?.roles ?? [form.professional_type === "MEDICO" ? "MEDICO" : "ENFERMEIRO"]
  ).map((role) => ({ value: role, label: roleLabel(role) }));

  const columns: DataTableColumn<Employee>[] = [
    { key: "full_name", header: "Nome", render: (e) => e.full_name },
    { key: "registration_number", header: "Matricula", render: (e) => e.registration_number },
    { key: "email", header: "Email", render: (e) => e.email },
    {
      key: "specialty",
      header: "Especialidade",
      render: (e) => (e.specialty_id ? specialtyNameById.get(e.specialty_id) ?? "-" : "-"),
    },
    {
      key: "professional_type",
      header: "Tipo",
      render: (e) => (e.professional_type === "MEDICO" ? "Médico" : "Enfermeiro"),
    },
    { key: "role", header: "Papel de acesso", render: (e) => (e.role ? roleLabel(e.role) : "-") },
    {
      key: "active",
      header: "Status",
      render: (e) => <StatusBadge status={e.active ? "ATIVO" : "INATIVO"} />,
    },
    {
      key: "actions",
      header: "Acoes",
      render: (e) => (
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button type="button" variant="secondary" onClick={() => openEditForm(e)}>
            <Pencil size={14} strokeWidth={2} aria-hidden="true" />
            Editar
          </Button>
          <Button type="button" variant="danger" onClick={() => setDeactivateTarget(e)}>
            {e.active ? (
              <Trash2 size={14} strokeWidth={2} aria-hidden="true" />
            ) : (
              <RotateCcw size={14} strokeWidth={2} aria-hidden="true" />
            )}
            {e.active ? "Excluir" : "Reativar"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <section>
      <PageHeader
        title="Funcionário"
        description="Cadastro de funcionarios e da conta de acesso (papel) vinculada a cada um."
        action={
          <Button type="button" onClick={openCreateForm} disabled={!subject}>
            <Plus size={16} strokeWidth={2} aria-hidden="true" />
            Novo funcionário
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
              id="employee-filter-name"
              label="Nome"
              placeholder="Ex.: Ana Souza"
              value={nameFilterInput}
              onChange={(event) => {
                setNameFilterInput(event.target.value);
                setPage(1);
              }}
            />
            <TextField
              id="employee-filter-registration"
              label="Matricula"
              placeholder="Ex.: CRM-12345"
              value={registrationFilterInput}
              onChange={(event) => {
                setRegistrationFilterInput(event.target.value);
                setPage(1);
              }}
            />
            <SelectField
              id="employee-filter-status"
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

      {employeesQuery.isLoading && <Skeleton rows={3} />}
      {employeesQuery.isError && (
        <ErrorState
          description={(employeesQuery.error as Error).message}
          onRetry={() => employeesQuery.refetch()}
        />
      )}
      {employeesQuery.isSuccess && employeesQuery.data.items.length === 0 && (
        <EmptyState
          title={
            searchFilter || statusFilter
              ? "Nenhum funcionário encontrado para os filtros informados"
              : "Nenhum funcionário cadastrado ainda"
          }
        />
      )}
      {employeesQuery.isSuccess && employeesQuery.data.items.length > 0 && (
        <Section title="Funcionários cadastrados">
          <DataTable columns={columns} rows={employeesQuery.data.items} getRowKey={(e) => e.id} />
          <Pagination
            page={employeesQuery.data.page}
            totalPages={employeesQuery.data.total_pages}
            totalItems={employeesQuery.data.total_items}
            onPageChange={setPage}
          />
        </Section>
      )}

      <Modal
        open={formOpen}
        title={editingEmployee ? "Editar funcionário" : "Novo funcionário"}
        onClose={() => setFormOpen(false)}
        size="lg"
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setFieldErrors({});
            saveMutation.mutate();
          }}
        >
          {/* Formulario dividido em 3 sub-blocos tematicos (identificacao,
              vinculo profissional, acesso ao sistema) em vez de uma lista
              unica de 8 campos - cada bloco usa a grade de 2 colunas em
              telas largas (modal `size="lg"`) para aproveitar melhor o
              espaco. */}
          <Section title="Identificação" variant="plain">
            <div style={formGridStyle}>
              <TextField
                id="employee-full-name"
                label="Nome"
                required
                value={form.full_name}
                onChange={(event) => updateField("full_name", event.target.value)}
                error={fieldErrors.full_name}
              />
              <TextField
                id="employee-email"
                label="Email"
                type="email"
                required
                value={form.email}
                onChange={(event) => updateField("email", event.target.value)}
                error={fieldErrors.email}
              />
              <TextField
                id="employee-cpf"
                label="CPF"
                required
                placeholder="000.000.000-00"
                value={form.cpf}
                onChange={(event) => updateField("cpf", event.target.value)}
                error={fieldErrors.cpf}
                disabled={Boolean(editingEmployee)}
                hint={editingEmployee ? "O CPF nao pode ser alterado apos o cadastro." : undefined}
              />
            </div>
          </Section>

          <Section title="Vínculo profissional" variant="plain">
            <div style={formGridStyle}>
              <TextField
                id="employee-registration-number"
                label="Matricula"
                required
                value={form.registration_number}
                onChange={(event) => updateField("registration_number", event.target.value)}
                error={fieldErrors.registration_number}
                disabled={Boolean(editingEmployee)}
                hint={
                  editingEmployee ? "A matricula nao pode ser alterada apos o cadastro." : undefined
                }
              />
              <SelectField
                id="employee-specialty"
                label="Especialidade medica"
                options={specialtyOptions}
                value={form.specialty_id ?? ""}
                onChange={(event) => updateField("specialty_id", event.target.value)}
              />
              <SelectField
                id="employee-professional-type"
                label="Tipo profissional"
                options={PROFESSIONAL_TYPE_FORM_OPTIONS}
                value={form.professional_type}
                onChange={(event) =>
                  updateField("professional_type", event.target.value as EmployeeProfessionalType)
                }
                disabled={Boolean(editingEmployee)}
                hint={
                  editingEmployee
                    ? "O tipo profissional nao pode ser alterado apos o cadastro."
                    : "Determina quais papeis de acesso podem ser escolhidos abaixo."
                }
              />
            </div>
          </Section>

          <Section title="Acesso ao sistema" variant="plain">
            <div style={formGridStyle}>
              <SelectField
                id="employee-role"
                label="Papel de acesso"
                options={roleOptions}
                value={form.role}
                onChange={(event) => updateField("role", event.target.value)}
                error={fieldErrors.role}
                hint="Enfermeiro so pode receber o papel Enfermeiro; Medico pode receber o papel clinico ou administrativo/de auditoria."
              />
              <TextField
                id="employee-external-subject"
                label="Identificador externo (sub do Cognito)"
                required
                value={form.external_subject}
                onChange={(event) => updateField("external_subject", event.target.value)}
                error={fieldErrors.external_subject}
                disabled={Boolean(editingEmployee)}
                hint={
                  editingEmployee
                    ? "O identificador externo nao pode ser alterado apos o cadastro."
                    : "Deve corresponder ao sub que o Cognito emitira para esta conta, criada la via AdminCreateUser."
                }
              />
            </div>
          </Section>

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
        title={deactivateTarget?.active ? "Excluir funcionário" : "Reativar funcionário"}
        description={
          deactivateTarget?.active
            ? `O funcionário "${deactivateTarget?.full_name}" sera desativado, junto com a conta de acesso vinculada. O registro nao e apagado (historico de analises/auditoria permanece intacto) e pode ser reativado depois.`
            : `O funcionário "${deactivateTarget?.full_name}" voltara a ficar ativo (a conta de acesso precisa ser reativada separadamente em Usuarios e papeis de acesso).`
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
