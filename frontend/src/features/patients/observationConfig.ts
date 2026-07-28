/**
 * Configuracao por tipo de observacao clinica usada no cadastro/exibicao
 * de observacoes do paciente.
 *
 * `idealRange` reflete a faixa considerada normal em repouso para um
 * adulto (referencia de triagem, nao um alvo individualizado) e alimenta
 * a banda de referencia do grafico de serie temporal de cada painel. Para
 * pressao arterial, sistolica e diastolica tem faixas normais proprias.
 * Nao existe faixa "ideal" de serie temporal para TIPOS nao numericos
 * (ex.: nivel de consciencia) - esses ficam fora do grafico.
 */
import { ObservationType } from "@/types/enums.generated";
import type { ClinicalObservation } from "@/types/patient";

export type NumericFieldKey = "value" | "systolic" | "diastolic";

export interface ChartSeriesConfig {
  /** Chave dentro de `observation.value` (ex.: "value", "systolic"). */
  valueKey: NumericFieldKey;
  label: string;
  color: string;
  idealMin: number;
  idealMax: number;
  /** Peso nao tem uma faixa "ideal" universal (depende da altura - o
   * indicador correto e o IMC, calculado a partir de altura+peso) - a
   * banda de referencia do grafico e omitida para esta serie. */
  hideIdealBand?: boolean;
}

export interface ObservationTypeConfig {
  type: ObservationType;
  label: string;
  unit: string;
  /** Uma entrada por serie numerica plotavel (pressao arterial tem duas). */
  series: ChartSeriesConfig[];
  hasChart: boolean;
}

export const OBSERVATION_TYPE_CONFIG: Record<ObservationType, ObservationTypeConfig> = {
  [ObservationType.SPO2]: {
    type: ObservationType.SPO2,
    label: "Saturação (SpO₂)",
    unit: "%",
    hasChart: true,
    series: [
      { valueKey: "value", label: "SpO2", color: "#1a8a4c", idealMin: 96, idealMax: 100 },
    ],
  },
  [ObservationType.HEART_RATE]: {
    type: ObservationType.HEART_RATE,
    label: "Frequência cardíaca",
    unit: "bpm",
    hasChart: true,
    series: [
      { valueKey: "value", label: "FC", color: "#c62828", idealMin: 60, idealMax: 100 },
    ],
  },
  [ObservationType.RESPIRATORY_RATE]: {
    type: ObservationType.RESPIRATORY_RATE,
    label: "Frequência respiratória",
    unit: "irpm",
    hasChart: true,
    series: [
      { valueKey: "value", label: "FR", color: "#3b82f6", idealMin: 12, idealMax: 20 },
    ],
  },
  [ObservationType.TEMPERATURE]: {
    type: ObservationType.TEMPERATURE,
    label: "Temperatura corporal",
    unit: "celsius",
    hasChart: true,
    series: [
      { valueKey: "value", label: "Temperatura", color: "#f9a825", idealMin: 36.1, idealMax: 37.5 },
    ],
  },
  [ObservationType.BLOOD_PRESSURE]: {
    type: ObservationType.BLOOD_PRESSURE,
    label: "Pressão arterial",
    unit: "mmHg",
    hasChart: true,
    series: [
      {
        valueKey: "systolic",
        label: "Sistolica",
        color: "#8b5cf6",
        idealMin: 111,
        idealMax: 119,
      },
      {
        valueKey: "diastolic",
        label: "Diastolica",
        color: "#3b82f6",
        idealMin: 60,
        idealMax: 79,
      },
    ],
  },
  [ObservationType.GLYCEMIA]: {
    type: ObservationType.GLYCEMIA,
    label: "Glicemia capilar",
    unit: "mg/dL",
    hasChart: true,
    series: [
      { valueKey: "value", label: "Glicemia", color: "#ef6c00", idealMin: 70, idealMax: 99 },
    ],
  },
  [ObservationType.PAIN]: {
    type: ObservationType.PAIN,
    label: "Dor",
    unit: "score_0_10",
    hasChart: true,
    series: [{ valueKey: "value", label: "Dor", color: "#6a1b9a", idealMin: 0, idealMax: 0 }],
  },
  [ObservationType.HEIGHT]: {
    type: ObservationType.HEIGHT,
    label: "Altura",
    unit: "cm",
    hasChart: false,
    series: [],
  },
  [ObservationType.WEIGHT]: {
    type: ObservationType.WEIGHT,
    label: "Peso",
    unit: "kg",
    hasChart: true,
    series: [
      {
        valueKey: "value",
        label: "Peso",
        color: "#0f5132",
        idealMin: 0,
        idealMax: 0,
        hideIdealBand: true,
      },
    ],
  },
  [ObservationType.CONSCIOUSNESS]: {
    type: ObservationType.CONSCIOUSNESS,
    label: "Nível de consciência",
    unit: "",
    hasChart: false,
    series: [],
  },
  [ObservationType.URINE_OUTPUT]: {
    type: ObservationType.URINE_OUTPUT,
    label: "Débito urinário (diurese)",
    unit: "mL/h",
    hasChart: true,
    series: [
      { valueKey: "value", label: "Diurese", color: "#0891b2", idealMin: 50, idealMax: 200 },
    ],
  },
  [ObservationType.SEIZURE]: {
    type: ObservationType.SEIZURE,
    label: "Convulsao",
    unit: "",
    hasChart: false,
    series: [],
  },
};

/** Tipos disponiveis no formulario de registro (modal). ALTURA nao entra
 * aqui: e um dado do cadastro do paciente (campo `height_cm`, praticamente
 * fixo em um adulto), nao uma observacao clinica repetida no tempo -
 * PESO sim, pois varia e junto com a altura permite calcular o IMC.
 * CONSCIENCIA exige um select de nivel em vez de campo numerico e fica
 * fora deste incremento. DOR e CONVULSAO entraram junto com o contexto
 * ampliado/tipo evento (ver `ObservationForm.tsx`); DEBITO URINARIO
 * (diurese) e numerico simples, mesmo padrao de SpO2/FC. */
export const CREATABLE_OBSERVATION_TYPES: ObservationType[] = [
  ObservationType.SPO2,
  ObservationType.HEART_RATE,
  ObservationType.RESPIRATORY_RATE,
  ObservationType.TEMPERATURE,
  ObservationType.BLOOD_PRESSURE,
  ObservationType.GLYCEMIA,
  ObservationType.WEIGHT,
  ObservationType.URINE_OUTPUT,
  ObservationType.PAIN,
  ObservationType.SEIZURE,
];

export const GLYCEMIA_MOMENT_OPTIONS = [
  { value: "jejum", label: "Jejum" },
  { value: "antes_refeicao", label: "Antes da refeicao" },
  { value: "apos_refeicao", label: "Apos a refeicao" },
  { value: "aleatoria", label: "Aleatoria" },
];

export const GLYCEMIA_PATIENT_TYPE_OPTIONS = [
  { value: "diabetico", label: "Diabetico" },
  { value: "nao_diabetico", label: "Nao diabetico" },
];

/** Contexto ampliado de dor - localizacao/inicio subito/sintomas de
 * alarme podem elevar o risco independentemente do escore numerico, ver
 * `app.observations.validation._validate_pain_context` e
 * `backend/clinical_rules/seeds/pain.yaml` v0.2.0). */
export const PAIN_LOCATION_OPTIONS = [
  { value: "toracica", label: "Torácica" },
  { value: "abdominal", label: "Abdominal" },
  { value: "cabeca", label: "Cabeça" },
  { value: "dorso", label: "Dorso" },
  { value: "membro", label: "Membro" },
  { value: "outra", label: "Outra" },
  { value: "nao_informado", label: "Não informado" },
];

/** Rotulo padrao "matricula - nome" usado no campo pesquisavel de
 * funcionario e gravado como `author` da observacao (para aparecer no
 * mesmo formato nas tabelas). Sem matricula vinculada, cai para so o
 * nome. */
export function formatEmployeeLabel(employee: {
  full_name: string;
  registration_number: string | null;
}): string {
  return employee.registration_number
    ? `${employee.registration_number} - ${employee.full_name}`
    : employee.full_name;
}

/** Agrupa observacoes clinicas por tipo, preservando a ordem cronologica
 * (decrescente) que a API ja devolve dentro de cada grupo. Usado para
 * renderizar um `ObservationTypePanel` por tipo, tanto na tela de detalhe
 * do paciente quanto no resumo somente-leitura da tela de Nova Analise. */
export function groupObservationsByType(
  observations: ClinicalObservation[],
): Map<ObservationType, ClinicalObservation[]> {
  const grouped = new Map<ObservationType, ClinicalObservation[]>();
  for (const observation of observations) {
    const type = observation.observation_type;
    const bucket = grouped.get(type);
    if (bucket) bucket.push(observation);
    else grouped.set(type, [observation]);
  }
  return grouped;
}

/** IMC = peso (kg) / altura (m)^2. Retorna `null` quando falta altura ou
 * nao ha nenhum registro de peso ainda - nunca inventa um valor parcial. */
export function computeBmi(heightCm: number | null, latestWeightKg: number | null): number | null {
  if (heightCm === null || latestWeightKg === null || heightCm <= 0) return null;
  const heightM = heightCm / 100;
  return latestWeightKg / (heightM * heightM);
}

/** Classificacao de IMC (tabela da OMS para adultos) - referencia de
 * triagem, nao diagnostico isolado; nao se aplica a criancas ou
 * gestantes. */
export function classifyBmi(bmi: number): string {
  if (bmi < 16.0) return "Baixo peso grave";
  if (bmi < 17.0) return "Baixo peso moderado";
  if (bmi < 18.5) return "Baixo peso leve";
  if (bmi < 25.0) return "Peso normal (Eutrofia)";
  if (bmi < 30.0) return "Sobrepeso";
  if (bmi < 35.0) return "Obesidade Grau I";
  if (bmi < 40.0) return "Obesidade Grau II";
  return "Obesidade Grau III";
}

/** Peso (kg) da observacao WEIGHT mais recente, ou `null` sem nenhum
 * registro. A listagem chega do backend ja em ordem decrescente por
 * `measured_at`, entao o primeiro item do grupo e o mais recente. */
export function latestWeightKg(observations: ClinicalObservation[] | undefined): number | null {
  if (!observations || observations.length === 0) return null;
  const raw = observations[0].value.value;
  return typeof raw === "number" ? raw : null;
}

export function formatObservationValue(
  config: ObservationTypeConfig,
  value: Record<string, unknown>,
): string {
  // SEIZURE (`{occurred: boolean}`) e um evento, nao um numero/serie -
  // mesmo caso especial de CONSCIOUSNESS (`{level: string}`, tratado pelo
  // fallback `JSON.stringify` abaixo, ja que nao tem formulario de
  // criacao proprio hoje).
  if (config.type === ObservationType.SEIZURE) {
    return value.occurred === true ? "Convulsão ocorreu" : "Sem convulsão";
  }
  if (config.series.length === 2) {
    const [first, second] = config.series;
    return `${value[first.valueKey] ?? "-"}/${value[second.valueKey] ?? "-"} ${config.unit}`.trim();
  }
  if (config.series.length === 1) {
    const key = config.series[0].valueKey;
    return `${value[key] ?? "-"} ${config.unit}`.trim();
  }
  return JSON.stringify(value);
}
