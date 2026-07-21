import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { X } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/data-display/DataTable";
import { Pagination } from "@/components/data-display/Pagination";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { Button } from "@/components/ui/Button";
import { Section } from "@/components/ui/Section";
import { SelectField } from "@/components/ui/SelectField";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TextField } from "@/components/ui/TextField";
import { useDevSession } from "@/hooks/useDevSession";
import { listAnalyses, listAnalysisProfessionals } from "@/services/api/analyses";
import type { Analysis } from "@/types/analysis";

const PAGE_SIZE = 5;

const columns: DataTableColumn<Analysis>[] = [
  {
    key: "id",
    header: "Analise",
    render: (analysis) => <Link to={`/analyses/${analysis.id}`}>{analysis.id.slice(0, 8)}</Link>,
  },
  {
    key: "patient_full_name",
    header: "Paciente",
    render: (analysis) => (
      <Link to={`/patients/${analysis.patient_id}`}>
        {analysis.patient_full_name ?? analysis.patient_id.slice(0, 8)}
      </Link>
    ),
  },
  {
    key: "patient_medical_record_number",
    header: "Prontuario",
    render: (analysis) => analysis.patient_medical_record_number ?? "-",
  },
  { key: "status", header: "Estado", render: (analysis) => <StatusBadge status={analysis.status} /> },
  {
    key: "created_at",
    header: "Criada em",
    render: (analysis) => new Date(analysis.created_at).toLocaleString("pt-BR"),
  },
  {
    key: "created_by",
    header: "Medico",
    // Nome completo resolvido pelo backend; recai no identificador tecnico
    // apenas se o usuario nao existir mais (nao deveria ocorrer em uso normal).
    render: (analysis) => analysis.created_by_full_name ?? analysis.created_by,
  },
];

export function AnalysesListPage() {
  const { subject } = useDevSession();
  const [searchParams] = useSearchParams();
  // Chegando pelo icone "Analise" da listagem de pacientes (`/analyses?patientId=...`):
  // fixa o historico neste paciente, sem entrar nos filtros de texto abaixo
  // (que buscam por nome/prontuario quando NAO se sabe o id exato).
  const patientIdFilter = searchParams.get("patientId") ?? undefined;
  const [page, setPage] = useState(1);
  const [createdByFilter, setCreatedByFilter] = useState("");
  const [createdFromFilter, setCreatedFromFilter] = useState("");
  const [createdToFilter, setCreatedToFilter] = useState("");
  const [patientNameFilter, setPatientNameFilter] = useState("");
  const [medicalRecordFilter, setMedicalRecordFilter] = useState("");

  const professionalsQuery = useQuery({
    queryKey: ["analyses", "professionals", subject],
    queryFn: () => listAnalysisProfessionals(subject as string),
    enabled: Boolean(subject),
  });

  const query = useQuery({
    queryKey: [
      "analyses",
      subject,
      page,
      createdByFilter,
      createdFromFilter,
      createdToFilter,
      patientNameFilter,
      medicalRecordFilter,
      patientIdFilter,
    ],
    queryFn: () =>
      listAnalyses(subject as string, {
        page,
        pageSize: PAGE_SIZE,
        createdBy: createdByFilter,
        createdFrom: createdFromFilter,
        createdTo: createdToFilter,
        patientName: patientNameFilter,
        patientMedicalRecordNumber: medicalRecordFilter,
        patientId: patientIdFilter,
      }),
    enabled: Boolean(subject),
  });

  const professionalOptions = [
    { value: "", label: "Todos os medicos" },
    ...(Array.isArray(professionalsQuery.data)
      ? professionalsQuery.data.map((p) => ({ value: p.external_subject, label: p.full_name }))
      : []),
  ];

  const hasActiveFilters = Boolean(
    createdByFilter ||
      createdFromFilter ||
      createdToFilter ||
      patientNameFilter ||
      medicalRecordFilter,
  );

  function clearFilters() {
    setCreatedByFilter("");
    setCreatedFromFilter("");
    setCreatedToFilter("");
    setPatientNameFilter("");
    setMedicalRecordFilter("");
    setPage(1);
  }

  return (
    <>
      <PageHeader
        title="Historico de analises"
        description="Analises multimodais e seus estados."
      />

      {!subject && (
        <EmptyState title="Configure o usuario de desenvolvimento acima para continuar." />
      )}

      {subject && (
        <Section title="Filtros">
          <form
            style={{
              display: "flex",
              gap: "var(--space-3)",
              alignItems: "flex-end",
              flexWrap: "wrap",
            }}
            onSubmit={(event) => {
              event.preventDefault();
              setPage(1);
            }}
          >
            <TextField
              id="analyses-filter-patient-name"
              label="Nome do paciente"
              placeholder="Ex.: Maria Souza"
              value={patientNameFilter}
              onChange={(event) => {
                setPatientNameFilter(event.target.value);
                setPage(1);
              }}
            />
            <TextField
              id="analyses-filter-medical-record"
              label="Prontuario"
              placeholder="Ex.: SEED-PAT-0001"
              value={medicalRecordFilter}
              onChange={(event) => {
                setMedicalRecordFilter(event.target.value);
                setPage(1);
              }}
            />
            <SelectField
              id="analyses-filter-doctor"
              label="Medico"
              options={professionalOptions}
              value={createdByFilter}
              onChange={(event) => {
                setCreatedByFilter(event.target.value);
                setPage(1);
              }}
            />
            <TextField
              id="analyses-filter-from"
              label="De"
              type="date"
              value={createdFromFilter}
              onChange={(event) => {
                setCreatedFromFilter(event.target.value);
                setPage(1);
              }}
            />
            <TextField
              id="analyses-filter-to"
              label="Até"
              type="date"
              value={createdToFilter}
              onChange={(event) => {
                setCreatedToFilter(event.target.value);
                setPage(1);
              }}
            />
            {hasActiveFilters && (
              <Button type="button" variant="secondary" onClick={clearFilters}>
                <X size={14} strokeWidth={2} aria-hidden="true" />
                Limpar filtros
              </Button>
            )}
          </form>
        </Section>
      )}

      {subject && query.isLoading && <Skeleton rows={5} />}

      {subject && query.isError && (
        <ErrorState description={(query.error as Error).message} onRetry={() => query.refetch()} />
      )}

      {subject && query.isSuccess && query.data.items.length === 0 && (
        <EmptyState
          title={
            hasActiveFilters
              ? "Nenhuma analise encontrada para os filtros informados"
              : "Nenhuma analise registrada ainda"
          }
        />
      )}

      {subject && query.isSuccess && query.data.items.length > 0 && (
        <Section title="Análises registradas">
          <DataTable columns={columns} rows={query.data.items} getRowKey={(analysis) => analysis.id} />
          <Pagination
            page={query.data.page}
            totalPages={query.data.total_pages}
            totalItems={query.data.total_items}
            onPageChange={setPage}
          />
        </Section>
      )}
    </>
  );
}
