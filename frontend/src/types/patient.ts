/**
 * Tipos de paciente e observacao clinica.
 * Espelha backend/app/api/schemas/patients.py e observations.py.
 */
import type { ObservationReadingQuality, ObservationType } from "./enums.generated";

export interface Patient {
  id: string;
  medical_record_number: string;
  full_name: string;
  birth_date: string; // YYYY-MM-DD
  age: number;
  registered_sex: string;
  email: string | null;
  /** Altura em cm, capturada uma vez no cadastro (nao e serie temporal
   * como o peso - ver `ObservationType.WEIGHT`). `null` para pacientes
   * cadastrados antes deste campo existir, ate ser preenchida via edicao. */
  height_cm: number | null;
  /** "Exclusao" e sempre desativacao (nunca apaga o registro). */
  active: boolean;
  /** Se o paciente tem ao menos uma analise ja registrada (qualquer
   * estado) - decide se o icone de atalho para o historico de analises
   * aparece na listagem de pacientes. */
  has_analyses: boolean;
  created_at: string;
  updated_at: string;
}

export interface PatientCreateInput {
  medical_record_number: string;
  full_name: string;
  birth_date: string;
  registered_sex: string;
  email?: string;
  height_cm?: number;
}

/** Corpo de PATCH /patients/{id}: todo campo enviado e atualizado (patch
 * parcial) - a tela de edicao envia o registro completo apos carregar os
 * dados atuais; a acao de excluir/reativar envia so `active`. */
export interface PatientUpdateInput {
  medical_record_number?: string;
  full_name?: string;
  birth_date?: string;
  registered_sex?: string;
  email?: string | null;
  height_cm?: number | null;
  active?: boolean;
}

export interface ClinicalObservation {
  id: string;
  patient_id: string;
  observation_type: ObservationType;
  value: Record<string, unknown>;
  unit: string | null;
  context: Record<string, unknown>;
  measured_at: string;
  origin: string;
  author: string;
  method: string | null;
  reading_quality: ObservationReadingQuality;
  created_at: string;
}

export interface ObservationCreateInput {
  observation_type: ObservationType;
  value: Record<string, unknown>;
  unit?: string;
  context?: Record<string, unknown>;
  measured_at: string;
  origin: string;
  author: string;
  method?: string;
  reading_quality?: ObservationReadingQuality;
}

/**
 * Apoio a analise clinica assistido por LLM (botao "Analisar dados
 * clinicos" abaixo do painel de alertas de anomalia). Espelha
 * backend/app/api/schemas/clinical_support.py - nunca e persistido, cada
 * chamada gera um resumo novo a partir do estado atual dos dados do
 * paciente. Nao e diagnostico nem substitui a analise do profissional
 * responsavel.
 */
export interface ClinicalSupportSummary {
  summary_text: string;
  probable_causes: string;
  suggested_next_steps: string;
  uncertainty_note: string;
  provider: string;
  model: string;
  prompt_version: string;
  generated_at: string;
  observations_considered: number;
  alerts_considered: number;
}
