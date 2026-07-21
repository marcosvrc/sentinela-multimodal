import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Skeleton } from "@/components/feedback/Skeleton";
import { ErrorState } from "@/components/feedback/ErrorState";
import { listObservations } from "@/services/api/patients";
import { groupObservationsByType, OBSERVATION_TYPE_CONFIG } from "@/features/patients/observationConfig";
import { ObservationTypePanel } from "@/features/patients/ObservationTypePanel";
import { ObservationType } from "@/types/enums.generated";
import {
  BMI_CODE,
  CLINICAL_DATA_OPTIONS,
  formatBmiValue,
  latestObservationByType,
} from "./clinicalDataSelection";
import styles from "./PatientClinicalDataSelector.module.css";

interface PatientClinicalDataSelectorProps {
  devSubject: string;
  patientId: string;
  /** Altura cadastrada do paciente (`Patient.height_cm`) - usada apenas
   * para habilitar/calcular o IMC (nao vem de nenhuma observacao
   * isolada, ver `clinicalDataSelection.extractBmiInputs`). */
  patientHeightCm: number | null;
  selectedCodes: Set<string>;
  onToggle: (code: string, checked: boolean) => void;
}

/**
 * Etapa "Dados clínicos" do fluxo de nova analise: uma linha de
 * checkboxes (um por tipo de observacao clinica com registro no
 * paciente) e, para cada tipo marcado, um painel expansivel abaixo com o
 * HISTORICO COMPLETO daquele tipo (tabela paginada de 5 em 5 - mesmo
 * `ObservationTypePanel` usado na ficha do paciente).
 *
 * A analise em si usa apenas o valor MAIS RECENTE de cada tipo marcado
 * (Opcao A acordada: nunca digitar um valor novo aqui - ver
 * `clinicalDataSelection.ts`/`buildStructuredClinicalInputs`); o
 * historico completo aparece so para o profissional CONFERIR o registro
 * mais recente no contexto das medicoes anteriores antes de marcar.
 *
 * Um tipo sem nenhum registro nao aparece na lista (nada para
 * selecionar); um tipo com registro mas faltando algum campo exigido
 * pelo motor de regras (ex.: contexto de glicemia incompleto) aparece
 * desabilitado, com aviso, e nao abre painel.
 */
export function PatientClinicalDataSelector({
  devSubject,
  patientId,
  patientHeightCm,
  selectedCodes,
  onToggle,
}: PatientClinicalDataSelectorProps) {
  const observationsQuery = useQuery({
    queryKey: ["observations", patientId],
    queryFn: () => listObservations(devSubject, patientId),
    enabled: Boolean(devSubject && patientId),
  });

  const latestByType = useMemo(
    () => latestObservationByType(observationsQuery.data ?? []),
    [observationsQuery.data],
  );
  const groupedByType = useMemo(
    () => groupObservationsByType(observationsQuery.data ?? []),
    [observationsQuery.data],
  );

  if (observationsQuery.isLoading) return <Skeleton rows={2} />;
  if (observationsQuery.isError) {
    return (
      <ErrorState
        description={(observationsQuery.error as Error).message}
        onRetry={() => observationsQuery.refetch()}
      />
    );
  }

  const availableOptions = CLINICAL_DATA_OPTIONS.filter((option) =>
    latestByType.has(option.observationType),
  );

  // IMC (`bmi`) e um caso especial: nao depende de uma unica observacao
  // (nao esta em `CLINICAL_DATA_OPTIONS`), e sim da altura cadastrada do
  // paciente + o peso mais recente (`ObservationType.WEIGHT`) - ver
  // `clinicalDataSelection.extractBmiInputs`.
  const latestWeightKgValue = latestByType.get(ObservationType.WEIGHT)?.value.value;
  const latestWeightKg = typeof latestWeightKgValue === "number" ? latestWeightKgValue : null;
  const bmiDisplayValue = formatBmiValue(patientHeightCm, latestWeightKg);
  const bmiUsable = bmiDisplayValue !== null;

  if (availableOptions.length === 0 && !bmiUsable) {
    return <p className={styles.empty}>Nenhuma observacao clinica registrada para este paciente.</p>;
  }

  return (
    <div className={styles.wrapper}>
      <ul className={styles.checkboxRow}>
        {availableOptions.map((option) => {
          const observation = latestByType.get(option.observationType)!;
          const config = OBSERVATION_TYPE_CONFIG[option.observationType];
          const usable = option.extractInputs(observation) !== null;
          const inputId = `clinical-data-${option.code}`;

          return (
            <li key={option.code}>
              <label
                className={[styles.checkboxOption, !usable && styles.checkboxOptionDisabled]
                  .filter(Boolean)
                  .join(" ")}
              >
                <input
                  id={inputId}
                  type="checkbox"
                  checked={usable && selectedCodes.has(option.code)}
                  disabled={!usable}
                  onChange={(event) => onToggle(option.code, event.target.checked)}
                />
                <span>{config.label}</span>
              </label>
              {!usable && (
                <span className={styles.itemUnavailable}>
                  Registro incompleto para uso automático nesta análise.
                </span>
              )}
            </li>
          );
        })}
        <li>
          <label
            className={[styles.checkboxOption, !bmiUsable && styles.checkboxOptionDisabled]
              .filter(Boolean)
              .join(" ")}
          >
            <input
              id="clinical-data-bmi"
              type="checkbox"
              checked={bmiUsable && selectedCodes.has(BMI_CODE)}
              disabled={!bmiUsable}
              onChange={(event) => onToggle(BMI_CODE, event.target.checked)}
            />
            <span>Índice de massa corporal (IMC)</span>
          </label>
          {!bmiUsable && (
            <span className={styles.itemUnavailable}>
              Requer altura cadastrada e ao menos um peso registrado.
            </span>
          )}
        </li>
      </ul>

      {availableOptions
        .filter((option) => selectedCodes.has(option.code))
        .map((option) => (
          <ObservationTypePanel
            key={option.code}
            config={OBSERVATION_TYPE_CONFIG[option.observationType]}
            observations={groupedByType.get(option.observationType) ?? []}
            defaultOpen
          />
        ))}

      {bmiUsable && selectedCodes.has(BMI_CODE) && (
        <p className={styles.bmiSummary}>
          IMC calculado a partir da altura cadastrada e do peso mais recente: {bmiDisplayValue}
        </p>
      )}
    </div>
  );
}
