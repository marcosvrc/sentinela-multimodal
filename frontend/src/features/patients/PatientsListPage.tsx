import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ClipboardList, Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/data-display/DataTable";
import { Pagination } from "@/components/data-display/Pagination";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { useToast } from "@/components/feedback/ToastProvider";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { LinkButton } from "@/components/ui/LinkButton";
import { Section } from "@/components/ui/Section";
import { SelectField } from "@/components/ui/SelectField";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TextField } from "@/components/ui/TextField";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useDevSession } from "@/hooks/useDevSession";
import { extractErrorMessage } from "@/lib/errorMessage";
import { listPatients, updatePatient } from "@/services/api/patients";
import type { Patient } from "@/types/patient";

const PAGE_SIZE = 5;
// Evita disparar busca a cada tecla para termos muito curtos, exceto
// quando o termo parece um prontuario exato (somente digitos).
const MIN_SEARCH_LENGTH = 3;

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "active", label: "Ativo" },
  { value: "inactive", label: "Inativo" },
];

const HAS_ANALYSES_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "yes", label: "Com analise" },
  { value: "no", label: "Sem analise" },
];

function isSearchable(term: string): boolean {
  const trimmed = term.trim();
  if (trimmed.length === 0) return true;
  if (/^\d+$/.test(trimmed)) return true; // prontuario exato, mesmo curto
  return trimmed.length >= MIN_SEARCH_LENGTH;
}

/**
 * Listagem de pacientes. Edicao e "exclusao" ficam aqui (nao mais na tela
 * de detalhe do paciente, que e
 * uma tela de trabalho clinico, nao de cadastro): editar abre a tela
 * dedicada `/patients/:id/edit`, com os dados atuais ja carregados;
 * "excluir" desativa o registro (nunca apaga - historico de observacoes/
 * analises/auditoria permanece integro, mesmo principio das telas de
 * administracao) e pode ser revertido reativando.
 */
export function PatientsListPage() {
  const { subject } = useDevSession();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebouncedValue(searchInput);
  const effectiveSearch = isSearchable(debouncedSearch) ? debouncedSearch.trim() : "";
  const [statusFilter, setStatusFilter] = useState("");
  const activeFilter =
    statusFilter === "active" ? true : statusFilter === "inactive" ? false : undefined;
  const [hasAnalysesFilter, setHasAnalysesFilter] = useState("");
  const hasAnalysesValue =
    hasAnalysesFilter === "yes" ? true : hasAnalysesFilter === "no" ? false : undefined;

  const [deactivateTarget, setDeactivateTarget] = useState<Patient | null>(null);

  const query = useQuery({
    queryKey: ["patients", subject, page, effectiveSearch, statusFilter, hasAnalysesFilter],
    queryFn: () =>
      listPatients(subject as string, {
        page,
        pageSize: PAGE_SIZE,
        search: effectiveSearch,
        active: activeFilter,
        hasAnalyses: hasAnalysesValue,
      }),
    enabled: Boolean(subject),
  });

  const deactivateMutation = useMutation({
    mutationFn: (patient: Patient) =>
      updatePatient(subject as string, patient.id, { active: !patient.active }),
    onSuccess: (_data, patient) => {
      setDeactivateTarget(null);
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      showSuccess(patient.active ? "Paciente excluído com sucesso." : "Paciente reativado com sucesso.");
    },
    onError: (error: unknown) => {
      showError(extractErrorMessage(error, "Não foi possível concluir a operação."));
    },
  });

  const columns: DataTableColumn<Patient>[] = [
    {
      key: "full_name",
      header: "Paciente",
      render: (patient) => <Link to={`/patients/${patient.id}`}>{patient.full_name}</Link>,
    },
    {
      key: "medical_record_number",
      header: "Prontuario",
      render: (patient) => patient.medical_record_number,
    },
    { key: "age", header: "Idade", render: (patient) => `${patient.age} anos` },
    {
      key: "registered_sex",
      header: "Sexo registrado",
      render: (patient) => patient.registered_sex,
    },
    {
      key: "active",
      header: "Status",
      render: (patient) => <StatusBadge status={patient.active ? "ATIVO" : "INATIVO"} />,
    },
    {
      key: "analyses",
      header: "Analise",
      render: (patient) =>
        patient.has_analyses ? (
          <Link
            to={`/analyses?patientId=${patient.id}`}
            title="Ver histórico de análises deste paciente"
            aria-label={`Ver historico de analises de ${patient.full_name}`}
          >
            <ClipboardList size={18} strokeWidth={2} aria-hidden="true" />
          </Link>
        ) : (
          <span aria-hidden="true">-</span>
        ),
    },
    {
      key: "actions",
      header: "Acoes",
      render: (patient) => (
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <LinkButton variant="secondary" to={`/patients/${patient.id}/edit`}>
            <Pencil size={14} strokeWidth={2} aria-hidden="true" />
            Editar
          </LinkButton>
          <Button type="button" variant="danger" onClick={() => setDeactivateTarget(patient)}>
            {patient.active ? (
              <Trash2 size={14} strokeWidth={2} aria-hidden="true" />
            ) : (
              <RotateCcw size={14} strokeWidth={2} aria-hidden="true" />
            )}
            {patient.active ? "Excluir" : "Reativar"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Pacientes"
        description="Busca e consulta de pacientes autorizados."
        action={
          <LinkButton to="/patients/new">
            <Plus size={16} strokeWidth={2} aria-hidden="true" />
            Novo paciente
          </LinkButton>
        }
      />

      {!subject && (
        <EmptyState title="Configure o usuário de desenvolvimento acima para continuar." />
      )}

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
              id="patient-search"
              label="Buscar por nome ou prontuário"
              placeholder="Ex.: Maria Souza ou 000123"
              value={searchInput}
              onChange={(event) => {
                setSearchInput(event.target.value);
                setPage(1);
              }}
              hint="Digite ao menos 3 letras, ou o numero completo/parcial do prontuario."
            />
            <SelectField
              id="patient-filter-status"
              label="Status"
              options={STATUS_OPTIONS}
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setPage(1);
              }}
              // Mesma altura de hint do campo de busca ao lado (texto
              // invisivel, nao lido por leitor de tela) - sem isso os dois
              // inputs ficam desalinhados dentro da linha de filtros
              // (`alignItems: flex-end` alinha pelo fundo do bloco inteiro,
              // que inclui o hint).
              hint="\u00A0"
            />
            <SelectField
              id="patient-filter-has-analyses"
              label="Analise"
              options={HAS_ANALYSES_OPTIONS}
              value={hasAnalysesFilter}
              onChange={(event) => {
                setHasAnalysesFilter(event.target.value);
                setPage(1);
              }}
              hint="\u00A0"
            />
          </div>
        </Section>
      )}

      {subject && query.isLoading && <Skeleton rows={5} />}

      {subject && query.isError && (
        <ErrorState description={(query.error as Error).message} onRetry={() => query.refetch()} />
      )}

      {subject && query.isSuccess && query.data.items.length === 0 && (
        <EmptyState
          title={
            effectiveSearch || statusFilter || hasAnalysesFilter
              ? "Nenhum paciente encontrado para os filtros informados"
              : "Nenhum paciente cadastrado ainda"
          }
          description={
            effectiveSearch || statusFilter || hasAnalysesFilter
              ? undefined
              : "Cadastre o primeiro paciente para comecar."
          }
          action={
            effectiveSearch || statusFilter || hasAnalysesFilter ? undefined : (
              <LinkButton to="/patients/new">
                <Plus size={16} strokeWidth={2} aria-hidden="true" />
                Novo paciente
              </LinkButton>
            )
          }
        />
      )}

      {subject && query.isSuccess && query.data.items.length > 0 && (
        <Section title="Pacientes cadastrados">
          <DataTable
            columns={columns}
            rows={query.data.items}
            getRowKey={(patient) => patient.id}
          />
          <Pagination
            page={query.data.page}
            totalPages={query.data.total_pages}
            totalItems={query.data.total_items}
            onPageChange={setPage}
          />
        </Section>
      )}

      <ConfirmDialog
        open={Boolean(deactivateTarget)}
        title={deactivateTarget?.active ? "Excluir paciente" : "Reativar paciente"}
        description={
          deactivateTarget?.active
            ? `O paciente "${deactivateTarget?.full_name}" sera desativado e deixara de aparecer na listagem padrao. O registro nao e apagado (historico clinico e de auditoria permanece integro) e pode ser reativado depois.`
            : `O paciente "${deactivateTarget?.full_name}" voltara a aparecer na listagem padrao.`
        }
        confirmLabel={deactivateTarget?.active ? "Excluir" : "Reativar"}
        variant={deactivateTarget?.active ? "danger" : "primary"}
        pending={deactivateMutation.isPending}
        onConfirm={() => deactivateTarget && deactivateMutation.mutate(deactivateTarget)}
        onCancel={() => setDeactivateTarget(null)}
      />
    </>
  );
}
