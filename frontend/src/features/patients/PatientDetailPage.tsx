import { useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { FileDown, Pencil, Plus } from "lucide-react";
import pageStyles from "./PatientDetailPage.module.css";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { Button } from "@/components/ui/Button";
import { LinkButton } from "@/components/ui/LinkButton";
import { Modal } from "@/components/ui/Modal";
import { Section } from "@/components/ui/Section";
import { useDevSession } from "@/hooks/useDevSession";
import { ObservationType } from "@/types/enums.generated";
import { getPatient, listObservations } from "@/services/api/patients";
import { AlertsPanel } from "./AlertsPanel";
import { ClinicalSupportPanel } from "./ClinicalSupportPanel";
import { ObservationForm } from "./ObservationForm";
import { ObservationTypePanel } from "./ObservationTypePanel";
import {
  classifyBmi,
  computeBmi,
  groupObservationsByType,
  latestWeightKg,
  OBSERVATION_TYPE_CONFIG,
} from "./observationConfig";
import { exportElementToPdf } from "./patientReportPdf";

export function PatientDetailPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const { subject } = useDevSession();
  const [formOpen, setFormOpen] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const printableRef = useRef<HTMLDivElement>(null);
  // Resolve a promise aguardada por `handleExportPdf` quando o
  // `AlertsPanel` avisa (via `onPrintDataReady`) que a busca de "todos os
  // alertas" (disparada por `printMode`) terminou - a captura do DOM so
  // deve acontecer depois disso, senao `html2canvas` fotografa o
  // `Skeleton` de carregamento (a barra cinza animada) parado no meio do
  // PDF gerado.
  const alertsPrintReadyResolveRef = useRef<(() => void) | null>(null);

  const patientQuery = useQuery({
    queryKey: ["patient", subject, patientId],
    queryFn: () => getPatient(subject as string, patientId as string),
    enabled: Boolean(subject && patientId),
  });

  const observationsQuery = useQuery({
    queryKey: ["observations", patientId],
    queryFn: () => listObservations(subject as string, patientId as string),
    enabled: Boolean(subject && patientId),
  });

  const groupedObservations = useMemo(
    () => groupObservationsByType(observationsQuery.data ?? []),
    [observationsQuery.data],
  );

  const patient = patientQuery.data;
  const weightKg = latestWeightKg(groupedObservations.get(ObservationType.WEIGHT));
  const bmi = patient ? computeBmi(patient.height_cm, weightKg) : null;

  if (!subject || !patientId) {
    return <EmptyState title="Configure o usuário de desenvolvimento primeiro." />;
  }

  if (patientQuery.isLoading) return <Skeleton rows={4} />;
  if (patientQuery.isError) {
    return (
      <ErrorState
        description={(patientQuery.error as Error).message}
        onRetry={() => patientQuery.refetch()}
      />
    );
  }

  if (!patient) return null;

  const currentHeightCm = patient.height_cm;
  const bmiDescription = bmi !== null ? `${bmi.toFixed(1)} · ${classifyBmi(bmi)}` : null;

  async function handleExportPdf() {
    if (!printableRef.current) return;
    setPdfError(null);
    setIsExportingPdf(true);
    try {
      // Forca a expansao de todos os paineis (via `forceOpen`, re-render
      // sincrono) antes de capturar o DOM - sem isso, apenas os paineis
      // que o usuario ja tinha aberto apareceriam no PDF. Alem de deixar
      // o navegador pintar o novo layout (e o `recharts` recalcular o
      // `ResponsiveContainer`), espera de fato a busca de "todos os
      // alertas" do `AlertsPanel` terminar - sem isso, a captura pode
      // acontecer com o `Skeleton` de carregamento ainda visivel.
      const alertsReady = new Promise<void>((resolve) => {
        alertsPrintReadyResolveRef.current = resolve;
      });
      await new Promise((resolve) => requestAnimationFrame(resolve));
      await alertsReady;
      await new Promise((resolve) => requestAnimationFrame(resolve));
      await exportElementToPdf(printableRef.current, {
        patientName: patient?.full_name ?? "Paciente",
        medicalRecordNumber: patient?.medical_record_number ?? "",
        ageLabel: patient ? `${patient.age} anos` : "-",
        registeredSex: patient?.registered_sex ?? "-",
        heightLabel: currentHeightCm ? `${currentHeightCm} cm` : "nao informada",
        bmiLabel: bmiDescription ?? "indisponivel",
      });
    } catch (error) {
      setPdfError(
        error instanceof Error ? error.message : "Nao foi possivel gerar o PDF desta tela.",
      );
    } finally {
      alertsPrintReadyResolveRef.current = null;
      setIsExportingPdf(false);
    }
  }

  return (
    <>
      <PageHeader
        title={patient.full_name}
        description={`Prontuario ${patient.medical_record_number} · ${patient.age} anos`}
        action={
          <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
            <Button type="button" variant="secondary" onClick={handleExportPdf} disabled={isExportingPdf}>
              <FileDown size={14} strokeWidth={2} aria-hidden="true" />
              {isExportingPdf ? "Gerando PDF..." : "Gerar PDF"}
            </Button>
            <LinkButton variant="secondary" to={`/patients/${patientId}/edit`}>
              <Pencil size={14} strokeWidth={2} aria-hidden="true" />
              Editar paciente
            </LinkButton>
            <LinkButton to={`/patients/${patientId}/analyses/new`}>Nova analise</LinkButton>
          </div>
        }
      />

      {pdfError && (
        <p role="alert" style={{ color: "var(--risk-high)", marginBottom: "var(--space-3)" }}>
          {pdfError}
        </p>
      )}

      <div ref={printableRef}>
        <Section title="Resumo">
          <div className={pageStyles.metaRow}>
            <span className={pageStyles.metaChip}>
              Altura: {currentHeightCm ? `${currentHeightCm} cm` : "nao informada"}
            </span>
            <span className={pageStyles.metaChip}>IMC: {bmiDescription ?? "indisponivel"}</span>
          </div>
        </Section>

        <AlertsPanel
          devSubject={subject}
          patientId={patientId}
          printMode={isExportingPdf}
          onPrintDataReady={() => alertsPrintReadyResolveRef.current?.()}
        />

        <ClinicalSupportPanel devSubject={subject} patientId={patientId} />

        <Section
          title="Observações clínicas"
          action={
            <Button type="button" onClick={() => setFormOpen(true)}>
              <Plus size={16} strokeWidth={2} aria-hidden="true" />
              Registrar observacao
            </Button>
          }
        >
          {observationsQuery.isLoading && <Skeleton rows={3} />}
          {observationsQuery.isError && (
            <ErrorState
              description={(observationsQuery.error as Error).message}
              onRetry={() => observationsQuery.refetch()}
            />
          )}
          {observationsQuery.isSuccess && observationsQuery.data.length === 0 && (
            <EmptyState title="Nenhuma observação registrada ainda." />
          )}
          {observationsQuery.isSuccess && observationsQuery.data.length > 0 && (
            <>
              {Array.from(groupedObservations.entries()).map(([type, observations]) => (
                <ObservationTypePanel
                  key={type}
                  config={OBSERVATION_TYPE_CONFIG[type]}
                  observations={observations}
                  forceOpen={isExportingPdf}
                  showAllRows={isExportingPdf}
                />
              ))}
            </>
          )}
        </Section>
      </div>

      <Modal
        open={formOpen}
        title="Registrar observação clínica"
        onClose={() => setFormOpen(false)}
        size="md"
      >
        <ObservationForm
          devSubject={subject}
          patientId={patientId}
          onCreated={() => setFormOpen(false)}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>
    </>
  );
}
