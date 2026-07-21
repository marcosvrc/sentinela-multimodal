/**
 * Rotulos em portugues (pt-BR) para os identificadores tecnicos dos
 * conjuntos de regras clinicas.
 *
 * Diferente de `app/enumLabels.ts` (enums formais do backend, com
 * codegen), estes valores vem de texto livre no YAML de seed
 * (`backend/clinical_rules/seeds/*.yaml`: campos `code`, `population`,
 * `required_inputs`, `exclusions`) - nao ha fonte unica gerada
 * automaticamente, entao o mapa e mantido manualmente aqui e deve ser
 * atualizado ao adicionar um novo arquivo de seed.
 *
 * A traducao e so de exibicao: os valores brutos (ingles/snake_case)
 * continuam sendo o que o backend armazena e usa para casar expressoes
 * `when` - nunca alterar o dado, so o rotulo mostrado na tela.
 */

/** `ClinicalRuleSet.code` -> nome do sinal/avaliacao em portugues. */
export const RULE_SET_CODE_LABELS: Record<string, string> = {
  blood_pressure: "Pressão arterial",
  bmi: "Índice de massa corporal (IMC)",
  consciousness_acvpu: "Nível de consciência (ACVPU)",
  gait: "Padrão de marcha",
  glycemia_fasting: "Glicemia em jejum",
  heart_rate: "Frequência cardíaca",
  movement_activity: "Movimentação do paciente",
  pain: "Dor",
  posture: "Postura corporal",
  respiratory_rate: "Frequência respiratória",
  seizure: "Convulsão",
  speech_alteration: "Alteração de fala",
  spo2: "Saturação de oxigênio (SpO₂)",
  surgery_adverse_events: "Eventos adversos cirúrgicos",
  surgery_flow: "Fluxo procedimental cirúrgico",
  surgery_team: "Equipe cirúrgica",
  surgery_tools: "Ferramentas cirúrgicas",
  temperature: "Temperatura corporal",
  urine_output: "Débito urinário (diurese)",
};

export function ruleSetCodeLabel(code: string): string {
  return RULE_SET_CODE_LABELS[code] ?? code;
}

/** `ClinicalRuleSet.population` -> descricao em portugues. */
export const POPULATION_LABELS: Record<string, string> = {
  adult: "Adulto",
};

export function populationLabel(population: string): string {
  return POPULATION_LABELS[population] ?? population;
}

/** `ClinicalRuleSet.required_inputs` (nomes de campo usados nas
 * expressoes `when`) -> rotulo legivel em portugues. */
export const REQUIRED_INPUT_LABELS: Record<string, string> = {
  systolic_mmhg: "Pressão sistólica (mmHg)",
  diastolic_mmhg: "Pressão diastólica (mmHg)",
  bmi_kg_m2: "IMC (kg/m²)",
  acvpu_level: "Nível de consciência (ACVPU)",
  gait_finding: "Padrão de marcha",
  glucose_mg_dl: "Glicemia (mg/dL)",
  moment: "Momento da medição",
  patient_type: "Tipo de paciente",
  insulin_use: "Uso de insulina",
  heart_rate_bpm: "Frequência cardíaca (bpm)",
  movement_finding: "Padrão de movimento",
  pain_score: "Escala de dor (0-10)",
  posture_finding: "Postura corporal",
  respiratory_rate_irpm: "Frequência respiratória (irpm)",
  speech_finding: "Alteração de fala",
  spo2_percent: "Saturação de oxigênio (SpO₂, %)",
  oxygen_in_use: "Uso de oxigênio suplementar",
  oxygen_scale: "Escala de SpO₂ utilizada",
  temperature_celsius: "Temperatura corporal (°C)",
  measurement_site: "Local da medição",
  measurement_method: "Método/equipamento de medição",
  adverse_event: "Evento adverso",
  flow_finding: "Fluxo procedimental",
  team_finding: "Comportamento da equipe",
  tool_finding: "Uso de ferramentas cirúrgicas",
  urine_output_ml_h: "Débito urinário (mL/h)",
  seizure_occurred: "Ocorrência de convulsão",
  location: "Localização da dor",
  sudden_onset: "Início súbito",
  alarm_symptoms_present: "Sintomas de alarme associados",
};

export function requiredInputLabel(field: string): string {
  return REQUIRED_INPUT_LABELS[field] ?? field;
}

/** Palavras soltas usadas em `exclusions` (a maioria dos itens ja e uma
 * frase completa em portugues no YAML e nao precisa de mapa - so estas
 * abreviacoes/sem acentuacao se beneficiam de um rotulo dedicado). Texto
 * fora do mapa e exibido com a primeira letra em maiusculo. */
const EXCLUSION_WORD_LABELS: Record<string, string> = {
  pediatria: "Pediatria",
  pediatrico: "Pediátrico",
  gestacao: "Gestação",
  gestante: "Gestante",
};

export function exclusionLabel(text: string): string {
  const mapped = EXCLUSION_WORD_LABELS[text];
  if (mapped) return mapped;
  return text.length > 0 ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}
