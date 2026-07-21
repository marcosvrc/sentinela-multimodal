/**
 * Tela de feature flags (`/admin/feature-flags`, acesso restrito a
 * administrador). Espelha backend/app/api/schemas/feature_flags.py.
 */
import type {
  ImageRecognitionProvider,
  LlmProvider,
  SentimentAnalysisProvider,
} from "./enums.generated";

export interface ModelOption {
  value: string;
  label: string;
}

export interface FeatureFlags {
  llm_provider_enabled: boolean;
  llm_provider: LlmProvider;
  llm_openai_model: string;
  /** Amazon Bedrock (Converse API, Structured Outputs) - alternativa ao
   * OpenAI dentro do mesmo Protocol de LLM, usando credenciais IAM do
   * processo em vez de chave de API externa. */
  llm_bedrock_model: string;
  llm_gemini_model: string;
  modality_audio_enabled: boolean;
  modality_video_enabled: boolean;
  modality_image_enabled: boolean;
  vision_detection_enabled: boolean;
  vision_pose_enabled: boolean;
  /** Rekognition Image (AWS) ou Image Analysis (Azure AI Vision) -
   * enriquecimento OPCIONAL da categorizacao heuristica de imagem
   * (ADR 0016), nunca substitui. Provedor escolhido por
   * `image_recognition_provider`. */
  image_recognition_enabled: boolean;
  image_recognition_provider: ImageRecognitionProvider;
  /** Amazon Rekognition Video - fonte COMPLEMENTAR ao worker OpenPose/
   * YOLOv8 (ADR 0016: Rekognition nao faz estimativa de pose). Sem
   * equivalente Azure implementado ainda. */
  vision_rekognition_video_enabled: boolean;
  /** Amazon Comprehend ou Azure AI Language (analise de sentimento) -
   * roda sobre o texto adicional e a transcricao de audio, sempre
   * CONTEXTUAL: nunca alcanca o motor de regras nem o prompt de
   * consolidacao de risco. Provedor escolhido por
   * `sentiment_analysis_provider`. */
  sentiment_analysis_enabled: boolean;
  sentiment_analysis_provider: SentimentAnalysisProvider;
  /** Apoio a analise clinica (IA) automatico apos o processamento -
   * substitui o botao manual "Analisar dados clinicos" na tela de
   * revisao quando ligado. So dispara quando ha conteudo clinicamente
   * relevante identificado na analise (ver backend `app.clinical_
   * support.service.should_run_automatic_clinical_support`). */
  auto_clinical_support_enabled: boolean;
  updated_at: string;
  updated_by: string | null;
  openai_model_options: ModelOption[];
  bedrock_model_options: ModelOption[];
  gemini_model_options: ModelOption[];
  /** Gemini esta registrado na tela para planejamento, mas ainda nao tem
   * adaptador real implementado - ver app.integrations.llm.gemini_adapter. */
  gemini_implemented: boolean;
}

export interface FeatureFlagsUpdateInput {
  llm_provider_enabled?: boolean;
  llm_provider?: LlmProvider;
  llm_openai_model?: string;
  llm_bedrock_model?: string;
  llm_gemini_model?: string;
  modality_audio_enabled?: boolean;
  modality_video_enabled?: boolean;
  modality_image_enabled?: boolean;
  vision_detection_enabled?: boolean;
  vision_pose_enabled?: boolean;
  image_recognition_enabled?: boolean;
  image_recognition_provider?: ImageRecognitionProvider;
  vision_rekognition_video_enabled?: boolean;
  sentiment_analysis_enabled?: boolean;
  sentiment_analysis_provider?: SentimentAnalysisProvider;
  auto_clinical_support_enabled?: boolean;
}
