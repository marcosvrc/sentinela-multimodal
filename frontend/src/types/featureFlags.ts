/**
 * Tela de feature flags (`/admin/feature-flags`, acesso restrito a
 * administrador). Espelha backend/app/api/schemas/feature_flags.py.
 */
import type { LlmProvider } from "./enums.generated";

export interface ModelOption {
  value: string;
  label: string;
}

export interface FeatureFlags {
  llm_provider_enabled: boolean;
  llm_provider: LlmProvider;
  llm_openai_model: string;
  llm_gemini_model: string;
  modality_audio_enabled: boolean;
  modality_video_enabled: boolean;
  modality_image_enabled: boolean;
  vision_detection_enabled: boolean;
  vision_pose_enabled: boolean;
  /** Azure AI Vision (Image Analysis) - enriquecimento OPCIONAL da
   * categorizacao heuristica de imagem (ADR 0016), nunca substitui. */
  image_recognition_enabled: boolean;
  /** Azure AI Language (analise de sentimento) - roda sobre o texto
   * adicional e a transcricao de audio, sempre CONTEXTUAL: nunca alcanca
   * o motor de regras nem o prompt de consolidacao de risco. */
  sentiment_analysis_enabled: boolean;
  /** Apoio a analise clinica (IA) automatico apos o processamento -
   * substitui o botao manual "Analisar dados clinicos" na tela de
   * revisao quando ligado. So dispara quando ha conteudo clinicamente
   * relevante identificado na analise (ver backend `app.clinical_
   * support.service.should_run_automatic_clinical_support`). */
  auto_clinical_support_enabled: boolean;
  /** Aceitar uploads DICOM e armazenar no Azure Health Data Services
   * DICOM Service. */
  dicom_service_enabled: boolean;
  updated_at: string;
  updated_by: string | null;
  openai_model_options: ModelOption[];
  gemini_model_options: ModelOption[];
  /** Gemini esta registrado na tela para planejamento, mas ainda nao tem
   * adaptador real implementado - ver app.integrations.llm.gemini_adapter. */
  gemini_implemented: boolean;
}

export interface FeatureFlagsUpdateInput {
  llm_provider_enabled?: boolean;
  llm_provider?: LlmProvider;
  llm_openai_model?: string;
  llm_gemini_model?: string;
  modality_audio_enabled?: boolean;
  modality_video_enabled?: boolean;
  modality_image_enabled?: boolean;
  vision_detection_enabled?: boolean;
  vision_pose_enabled?: boolean;
  image_recognition_enabled?: boolean;
  sentiment_analysis_enabled?: boolean;
  auto_clinical_support_enabled?: boolean;
  dicom_service_enabled?: boolean;
}
