import { useState } from "react";
import { CollapsiblePanel } from "@/components/ui/CollapsiblePanel";
import { DataTable, type DataTableColumn } from "@/components/data-display/DataTable";
import { Pagination } from "@/components/data-display/Pagination";
import { readingQualityLabel } from "@/app/enumLabels";
import type { ClinicalObservation } from "@/types/patient";
import { formatObservationValue, type ObservationTypeConfig } from "./observationConfig";
import { ObservationTimeSeriesChart } from "./ObservationTimeSeriesChart";

const PAGE_SIZE = 5;

interface ObservationTypePanelProps {
  config: ObservationTypeConfig;
  observations: ClinicalObservation[];
  /** Ver `CollapsiblePanel.defaultOpen` - usado pelo seletor de dados
   * clinicos da nova analise (`PatientClinicalDataSelector`), onde marcar
   * o tipo ja abre o painel correspondente automaticamente. */
  defaultOpen?: boolean;
  /** Ver `CollapsiblePanel.forceOpen` - usado pela exportacao em PDF. */
  forceOpen?: boolean;
  /** Quando `true`, exibe todos os registros na tabela sem paginacao -
   * usado pela exportacao em PDF (o documento exportado deve conter o
   * historico completo, nao apenas a pagina atual). */
  showAllRows?: boolean;
}

const columns = (config: ObservationTypeConfig): DataTableColumn<ClinicalObservation>[] => [
  {
    key: "measured_at",
    header: "Medido em",
    render: (o) => new Date(o.measured_at).toLocaleString("pt-BR"),
  },
  { key: "value", header: "Valor", render: (o) => formatObservationValue(config, o.value) },
  { key: "origin", header: "Origem", render: (o) => o.origin },
  { key: "author", header: "Funcionario", render: (o) => o.author },
  {
    key: "reading_quality",
    header: "Qualidade",
    render: (o) => readingQualityLabel(o.reading_quality),
  },
];

/**
 * Painel por tipo de observacao clinica (fechado por padrao, expansivel):
 * tabela de valores + grafico de linha de serie temporal com a faixa
 * ideal do sinal (quando aplicavel). Cada tipo de observacao ganha o seu
 * proprio painel na tela de detalhe do paciente para permitir avaliar a
 * evolucao de um sinal especifico (ex.: pressao arterial) ao longo de
 * varias medicoes.
 */
export function ObservationTypePanel({
  config,
  observations,
  defaultOpen,
  forceOpen,
  showAllRows,
}: ObservationTypePanelProps) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(observations.length / PAGE_SIZE));
  const pageObservations = showAllRows
    ? observations
    : observations.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <CollapsiblePanel
      title={config.label}
      countLabel={`${observations.length} ${observations.length === 1 ? "registro" : "registros"}`}
      defaultOpen={defaultOpen}
      forceOpen={forceOpen}
    >
      {config.hasChart && observations.length > 0 && (
        <div style={{ marginBottom: "var(--space-4)" }}>
          <ObservationTimeSeriesChart config={config} observations={observations} />
        </div>
      )}
      <DataTable
        columns={columns(config)}
        rows={pageObservations}
        getRowKey={(observation) => observation.id}
      />
      {!showAllRows && (
        <Pagination
          page={page}
          totalPages={totalPages}
          totalItems={observations.length}
          onPageChange={setPage}
        />
      )}
    </CollapsiblePanel>
  );
}
