/**
 * Mapeamento `ObservationType` (observacoes clinicas ja registradas do
 * paciente, `app.observations`) -> `code`/entradas do motor de regras
 * (`ClinicalRuleSet.code`/`required_inputs`, `backend/clinical_rules/
 * seeds/*.yaml`) usado para montar `Analysis.structured_clinical_inputs`
 * na etapa 2 do fluxo de nova analise ("escolher quais observacoes
 * clinicas considerar na analise" - a Opcao A discutida: usa o valor MAIS
 * RECENTE ja registrado do paciente, nunca um valor novo digitado aqui).
 *
 * Cada entrada sabe extrair os `inputs` do motor de regras a partir do
 * `value`/`context` de uma `ClinicalObservation` (formato salvo por
 * `ObservationForm.tsx` / `app.observations.validation`) - se algum campo
 * obrigatorio da regra nao estiver presente na observacao (ex.: contexto
 * de glicemia incompleto), a observacao correspondente nao pode ser
 * selecionada (extractInputs retorna `null`).
 */
import { ObservationType } from "@/types/enums.generated";
import type { ClinicalObservation } from "@/types/patient";
import { classifyBmi, computeBmi } from "@/features/patients/observationConfig";

export interface ClinicalDataOption {
  observationType: ObservationType;
  /** `ClinicalRuleSet.code` correspondente (chave em `structured_clinical_inputs`). */
  code: string;
  /** Extrai os `inputs` do motor de regras a partir da observacao mais
   * recente desse tipo - `null` se faltar algum dado obrigatorio. */
  extractInputs: (observation: ClinicalObservation) => Record<string, unknown> | null;
}

/** `ClinicalRuleSet.code` do IMC - tratado separadamente de
 * `CLINICAL_DATA_OPTIONS` (ver `extractBmiInputs` abaixo). */
export const BMI_CODE = "bmi";

/**
 * IMC (`bmi`) e um caso especial: nao vem de uma UNICA observacao (como os demais itens de
 * `CLINICAL_DATA_OPTIONS`), e sim calculado a partir de dois dados que
 * hoje vivem em lugares diferentes - `Patient.height_cm` (cadastro do
 * paciente, praticamente fixo) e a observacao `WEIGHT` mais recente
 * (serie temporal, ver `app.observations`). O motor de regras (`bmi.
 * yaml`) e o rotulo (`clinicalDataLabels.ts`) ja existiam; faltava esta
 * ponte no fluxo de Nova Analise (`AnalysisNewPage`/
 * `PatientClinicalDataSelector`). Reaproveita `computeBmi` (mesmo calculo
 * ja usado na ficha do paciente) em vez de duplicar a formula aqui.
 *
 * Retorna `null` quando falta altura cadastrada ou nao ha nenhum peso
 * registrado ainda - nunca inventa um valor parcial.
 */
export function extractBmiInputs(
  heightCm: number | null,
  latestWeightKg: number | null,
): Record<string, unknown> | null {
  const bmi = computeBmi(heightCm, latestWeightKg);
  if (bmi === null) return null;
  return { bmi_kg_m2: Math.round(bmi * 10) / 10 };
}

/** Rotulo/valor formatado do IMC para exibicao na linha de checkbox e no
 * resumo do consolidado - mesmo texto usado na ficha do paciente
 * (`classifyBmi`), para nao ter dois formatos diferentes do mesmo dado. */
export function formatBmiValue(heightCm: number | null, latestWeightKg: number | null): string | null {
  const bmi = computeBmi(heightCm, latestWeightKg);
  if (bmi === null) return null;
  return `${bmi.toFixed(1)} kg/m² · ${classifyBmi(bmi)}`;
}

export const CLINICAL_DATA_OPTIONS: ClinicalDataOption[] = [
  {
    observationType: ObservationType.SPO2,
    code: "spo2",
    extractInputs: (observation) => {
      const value = observation.value.value;
      if (typeof value !== "number") return null;
      // oxygen_in_use/oxygen_scale nao sao capturados hoje pelo formulario
      // de observacao (ObservationForm.tsx) - envia so o campo disponivel;
      // o motor de regras retorna INCONCLUSIVO se precisar dos demais.
      return { spo2_percent: value };
    },
  },
  {
    observationType: ObservationType.HEART_RATE,
    code: "heart_rate",
    extractInputs: (observation) => {
      const value = observation.value.value;
      if (typeof value !== "number") return null;
      return { heart_rate_bpm: value };
    },
  },
  {
    observationType: ObservationType.RESPIRATORY_RATE,
    code: "respiratory_rate",
    extractInputs: (observation) => {
      const value = observation.value.value;
      if (typeof value !== "number") return null;
      return { respiratory_rate_irpm: value };
    },
  },
  {
    observationType: ObservationType.TEMPERATURE,
    code: "temperature",
    extractInputs: (observation) => {
      const value = observation.value.value;
      if (typeof value !== "number") return null;
      // measurement_site/measurement_method tambem nao sao capturados
      // hoje pelo formulario de observacao - mesma ressalva do SpO2.
      return { temperature_celsius: value };
    },
  },
  {
    observationType: ObservationType.BLOOD_PRESSURE,
    code: "blood_pressure",
    extractInputs: (observation) => {
      const { systolic, diastolic } = observation.value;
      if (typeof systolic !== "number" || typeof diastolic !== "number") return null;
      return { systolic_mmhg: systolic, diastolic_mmhg: diastolic };
    },
  },
  {
    observationType: ObservationType.GLYCEMIA,
    code: "glycemia_fasting",
    extractInputs: (observation) => {
      const value = observation.value.value;
      const { moment, patient_type, insulin_use } = observation.context;
      if (typeof value !== "number") return null;
      if (typeof moment !== "string" || typeof patient_type !== "string") return null;
      return {
        glucose_mg_dl: value,
        moment,
        patient_type,
        insulin_use: Boolean(insulin_use),
      };
    },
  },
  {
    observationType: ObservationType.PAIN,
    code: "pain",
    extractInputs: (observation) => {
      const value = observation.value.value;
      if (typeof value !== "number") return null;
      // location/sudden_onset/alarm_symptoms_present sao contexto
      // OBRIGATORIO na regra a partir da v0.2.0 (ver backend/clinical_
      // rules/seeds/pain.yaml) - sem eles o motor fica INCONCLUSIVO;
      // registros antigos (antes deste campo existir no formulario) nao
      // podem ser usados automaticamente nesta analise.
      const { location, sudden_onset, alarm_symptoms_present } = observation.context;
      if (typeof location !== "string") return null;
      if (typeof sudden_onset !== "boolean" || typeof alarm_symptoms_present !== "boolean") {
        return null;
      }
      return {
        pain_score: value,
        location,
        sudden_onset,
        alarm_symptoms_present,
      };
    },
  },
  {
    observationType: ObservationType.CONSCIOUSNESS,
    code: "consciousness_acvpu",
    extractInputs: (observation) => {
      const level = observation.value.level;
      if (typeof level !== "string") return null;
      return { acvpu_level: level };
    },
  },
  {
    observationType: ObservationType.URINE_OUTPUT,
    code: "urine_output",
    extractInputs: (observation) => {
      const value = observation.value.value;
      if (typeof value !== "number") return null;
      return { urine_output_ml_h: value };
    },
  },
  {
    observationType: ObservationType.SEIZURE,
    code: "seizure",
    extractInputs: (observation) => {
      const occurred = observation.value.occurred;
      if (typeof occurred !== "boolean") return null;
      return { seizure_occurred: occurred };
    },
  },
];

/** Observacao mais recente de cada tipo (a listagem chega do backend em
 * ordem decrescente por `measured_at` - ver `groupObservationsByType`). */
export function latestObservationByType(
  observations: ClinicalObservation[],
): Map<ObservationType, ClinicalObservation> {
  const latest = new Map<ObservationType, ClinicalObservation>();
  for (const observation of observations) {
    if (!latest.has(observation.observation_type)) {
      latest.set(observation.observation_type, observation);
    }
  }
  return latest;
}

/** Monta `structured_clinical_inputs` a partir dos `codes` selecionados
 * (checkboxes marcados) e das observacoes mais recentes disponiveis.
 * `heightCm` (cadastro do paciente) e usado somente para o IMC (`BMI_
 * CODE`), que nao vem de nenhuma `ClinicalObservation` isolada - ver
 * `extractBmiInputs`. */
export function buildStructuredClinicalInputs(
  selectedCodes: Set<string>,
  latestByType: Map<ObservationType, ClinicalObservation>,
  heightCm: number | null = null,
): Record<string, Record<string, unknown>> {
  const result: Record<string, Record<string, unknown>> = {};
  for (const option of CLINICAL_DATA_OPTIONS) {
    if (!selectedCodes.has(option.code)) continue;
    const observation = latestByType.get(option.observationType);
    if (!observation) continue;
    const inputs = option.extractInputs(observation);
    if (inputs) result[option.code] = inputs;
  }
  if (selectedCodes.has(BMI_CODE)) {
    const weightObservation = latestByType.get(ObservationType.WEIGHT);
    const weightValue = weightObservation?.value.value;
    const latestWeightKg = typeof weightValue === "number" ? weightValue : null;
    const bmiInputs = extractBmiInputs(heightCm, latestWeightKg);
    if (bmiInputs) result[BMI_CODE] = bmiInputs;
  }
  return result;
}
