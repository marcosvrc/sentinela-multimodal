/**
 * Tipos de analise, midia, orquestracao, consolidacao de risco e relatorio.
 * Espelha backend/app/api/schemas/{media,orchestrator,reports}.py.
 */
import type {
  AnalysisStatus,
  MediaUploadState,
  ModalityAttentionLevel,
  ModalityQualityState,
  ModalityType,
} from "./enums.generated";

export interface Analysis {
  id: string;
  patient_id: string;
  status: AnalysisStatus;
  additional_text: string | null;
  structured_clinical_inputs: Record<string, Record<string, unknown>>;
  created_by: string;
  /** Nome completo do profissional, resolvido pelo backend a partir de `created_by`. */
  created_by_full_name: string | null;
  /** Nome e prontuario do paciente vinculado, resolvidos pelo backend a
   * partir de `patient_id` - usados na coluna/filtro de paciente do
   * historico de analises. */
  patient_full_name: string | null;
  patient_medical_record_number: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Item do filtro "Medico" do historico de analises e do campo pesquisavel
 * de funcionario no registro de observacao clinica.
 * `registration_number` (matricula) fica `null` quando o usuario nao tem
 * um funcionario administrativo vinculado.
 */
export interface AnalysisProfessional {
  external_subject: string;
  full_name: string;
  registration_number: string | null;
}

export interface AnalysisCreateInput {
  patient_id: string;
  additional_text?: string;
  structured_clinical_inputs?: Record<string, Record<string, unknown>>;
}

/** Estatisticas agregadas de todas as analises da instituicao com
 * consolidacao de risco ja gravada - "big number" de percentual de
 * analises conclusivas (`MATCHED`) na tela de revisao da analise. Nao e
 * uma metrica de acuracia clinica validada contra um "gabarito", e a
 * proporcao de analises com resultado conclusivo sobre o total. */
export interface AnalysisStats {
  total_analyses_consolidated: number;
  conclusive_count: number;
  conclusive_rate_percent: number;
}

export interface MediaUploadRequestInput {
  modality_type: ModalityType;
  filename: string;
  mime_type: string;
  size_bytes: number;
}

export interface MediaUploadResponse {
  media_id: string;
  upload_url: string;
  upload_method: string;
  upload_headers: Record<string, string>;
  expires_at: string;
}

export interface MediaAsset {
  id: string;
  analysis_id: string;
  modality_type: ModalityType;
  upload_state: MediaUploadState;
  original_filename: string;
  declared_mime_type: string;
  declared_size_bytes: number;
  detected_mime_type: string | null;
  actual_size_bytes: number | null;
  checksum_sha256: string | null;
  rejection_reason: string | null;
  created_at: string;
  confirmed_at: string | null;
}

export interface AnalysisModalityState {
  id: string;
  modality_type: ModalityType;
  /** Midia especifica que originou este estado - uma analise pode ter
   * mais de uma midia da mesma modalidade, cada uma com seu proprio
   * estado de processamento independente. `null` apenas para o estado
   * sintetico TEXT (nao vem de upload). */
  media_asset_id: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ReportRiskConsolidation {
  outcome: string;
  risk_level: number | null;
  classification_label: string | null;
  inconclusive_reason: string | null;
  inconclusive_detail: string | null;
}

/**
 * Observacao derivada de um processador de modalidade: mencoes de termo
 * clinico com negacao/temporalidade/certeza/experienciador, extraidas por
 * `app.clinical_nlp.text_analysis`.
 * `details` varia por modalidade/processador - por isso permanece um
 * dicionario aberto, mas os campos abaixo sao os produzidos hoje pelo
 * processador de texto.
 */
export interface ReportModelObservation {
  modality_type: string;
  summary: string;
  observed_at: string;
  details: {
    term?: string;
    negation?: "AFFIRMED" | "NEGATED";
    certainty?: "CONFIRMED" | "SUSPECTED" | "POSSIBLE" | "CONDITIONAL";
    temporality?: "CURRENT" | "PAST" | "FUTURE";
    experiencer?: "PATIENT" | "FAMILY_MEMBER" | "OTHER";
    extraction_method?: string;
    [key: string]: unknown;
  };
}

export interface ReportContent {
  identification: {
    analysis_id: string;
    institution_id: string;
    patient: {
      patient_id: string;
      medical_record_number: string;
      full_name: string;
      birth_date: string;
    };
    created_by: string;
    created_at: string;
    additional_text: string | null;
    structured_clinical_inputs: Record<string, Record<string, unknown>>;
  };
  report_state: string;
  ai_summary: {
    text: string | null;
    uncertainty_note: string | null;
    status: string;
  };
  /** Ultimo resultado do botao "Analisar dados clinicos" (apoio a analise
   * clinica assistido por LLM, sob demanda) - distinto de `ai_summary`
   * acima (automatico, sempre gerado na consolidacao de risco). `null` se
   * o profissional nunca clicou no botao antes da confirmacao do
   * relatorio - agora PERSISTIDO em `Report.clinical_support_summary`
   * para aparecer tambem no PDF exportado. */
  clinical_support_summary: {
    summary_text: string;
    probable_causes: string;
    suggested_next_steps: string;
    uncertainty_note: string;
    provider: string;
    model: string;
    prompt_version: string;
    generated_at: string;
    findings_considered: number;
  } | null;
  calculated_risk: ReportRiskConsolidation;
  deterministic_findings: Array<{
    code: string;
    outcome: string;
    risk_level: number | null;
    classification_label: string | null;
    inconclusive_reason: string | null;
  }>;
  model_observations: ReportModelObservation[];
  assisted_hypotheses: ReportModelObservation[];
  /**
   * "Nivel de atencao por modalidade" - indicador puramente VISUAL de
   * apoio a leitura, derivado dos mesmos achados de `model_observations`/
   * `assisted_hypotheses` acima, agregados por modalidade. NUNCA e um
   * calculo de risco clinico (risco e exclusivo de `calculated_risk`,
   * calculado pelo motor de regras deterministico) - ver
   * `ModalityAttentionLevel` em `backend/app/core/enums.py`. So lista
   * modalidades com pelo menos um achado nesta analise.
   */
  modality_attention: Array<{
    modality_type: string;
    level: ModalityAttentionLevel;
    relevant_findings_count: number;
    summaries: string[];
  }>;
  /**
   * Evidencia por modalidade e qualidade tecnica UNIFICADAS em uma unica
   * lista (uma linha por achado, com todas as colunas juntas) - antes
   * eram duas secoes separadas repetindo a mesma `modality_type` para
   * cada achado. Renderizada como tabela paginada de 5 em 5
   * (`AnalysisReviewPage`).
   */
  modality_evidence: Array<{
    modality_type: string;
    summary: string;
    observed_at: string;
    // Ausentes em relatorios gerados ANTES da unificacao desta tabela
    // (Report.content e um snapshot JSONB persistido, nunca recalculado
    // retroativamente) - sempre tratar como possivelmente indefinido.
    quality_state?: ModalityQualityState;
    quality_factors?: string[];
  }>;
  /**
   * Tabela consolidada "Resumo por modalidade": uma linha por modalidade
   * com qualidade agregada, relevancia clinica, resumo textual e se a
   * modalidade entra no resumo final correlacionado
   * (`clinical_correlation_summary` abaixo). Substitui a necessidade de
   * cruzar `modality_attention` com `modality_evidence` para responder as
   * mesmas perguntas. Ausente em relatorios gerados antes desta secao -
   * sempre tratar como possivelmente indefinido.
   */
  modality_summary?: Array<{
    modality_type: string;
    quality_state: ModalityQualityState | null;
    clinically_relevant: boolean;
    summary: string;
    used_in_final_analysis: boolean;
  }>;
  /**
   * Resumo final DETERMINISTICO (sem LLM, sempre disponivel) que
   * correlaciona apenas as modalidades marcadas em `modality_summary`
   * como `used_in_final_analysis=true`. Distinto de `ai_summary`
   * (automatico, sem filtro de relevancia) e de `clinical_support_summary`
   * (sob demanda, via LLM). Ausente em relatorios gerados antes desta
   * secao.
   */
  clinical_correlation_summary?: {
    included_modality_types: string[];
    excluded_modality_types: string[];
    text: string;
  };
  inconsistencies: string[];
  protocol_conduct: string | null;
  professional_review: {
    state: string;
    confirmed_by: string | null;
    confirmed_at: string | null;
  };
  provenance: {
    rule_codes_evaluated: string[];
    llm_provider: string | null;
    llm_model: string | null;
    llm_prompt_version: string | null;
    llm_input_hash: string | null;
    llm_output_hash: string | null;
  };
}

export interface Report {
  id: string;
  analysis_id: string;
  state: string;
  content: ReportContent;
  pdf_sha256: string | null;
  pdf_generated_at: string | null;
  confirmed_by: string | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Apoio a analise clinica assistido por LLM para UMA analise multimodal
 * especifica (botao "Analisar dados clinicos" da tela de revisao da
 * analise). Espelha backend/app/api/schemas/clinical_support.py::
 * AnalysisClinicalSupportSummaryRead - mesmo contrato de
 * `ClinicalSupportSummary` (types/patient.ts), mas o escopo de dados e
 * uma analise (achados por modalidade + risco calculado) em vez do
 * historico completo do paciente. Gerado sob demanda a cada clique, mas
 * o ULTIMO resultado agora e persistido em `Report.clinical_support_
 * summary` (ver `ReportContent.clinical_support_summary`), para
 * sobreviver a reabertura da tela e integrar o PDF exportado.
 */
export interface AnalysisClinicalSupportSummary {
  summary_text: string;
  probable_causes: string;
  suggested_next_steps: string;
  uncertainty_note: string;
  provider: string;
  model: string;
  prompt_version: string;
  generated_at: string;
  findings_considered: number;
}
