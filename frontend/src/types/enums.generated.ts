// ARQUIVO GERADO AUTOMATICAMENTE - NAO EDITAR.
// Fonte: backend/app/core/enums.py
// Gerar novamente com: make codegen

export enum AlertSeverity {
  MODERATE = "MODERATE",
  HIGH = "HIGH",
  CRITICAL = "CRITICAL",
}

export enum AlertStatus {
  OPEN = "OPEN",
  ACKNOWLEDGED = "ACKNOWLEDGED",
  ESCALATED = "ESCALATED",
  RESOLVED = "RESOLVED",
}

export enum AnalysisAction {
  CANCEL = "CANCEL",
  RETRY_AUDIO = "RETRY_AUDIO",
  RETRY_VIDEO = "RETRY_VIDEO",
  RETRY_IMAGE = "RETRY_IMAGE",
  RETRY_TEXT = "RETRY_TEXT",
  CONFIRM_REPORT = "CONFIRM_REPORT",
  DOWNLOAD_PDF = "DOWNLOAD_PDF",
}

export enum AnalysisStatus {
  CREATED = "CREATED",
  UPLOADING = "UPLOADING",
  QUEUED = "QUEUED",
  PROCESSING = "PROCESSING",
  PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED",
  WAITING_REVIEW = "WAITING_REVIEW",
  COMPLETED = "COMPLETED",
  FAILED_RETRYABLE = "FAILED_RETRYABLE",
  FAILED_FINAL = "FAILED_FINAL",
  CANCELLED = "CANCELLED",
}

export enum AuditCategory {
  AUTHENTICATION = "AUTHENTICATION",
  AUTHORIZATION = "AUTHORIZATION",
  DATA = "DATA",
  FILES = "FILES",
  ADMINISTRATION = "ADMINISTRATION",
  ANALYSIS = "ANALYSIS",
  AI = "AI",
  REVIEW = "REVIEW",
  AUDIT = "AUDIT",
}

export enum AuditResult {
  SUCCESS = "SUCCESS",
  DENIED = "DENIED",
  ERROR = "ERROR",
}

export enum ClinicalRuleSetStatus {
  DRAFT = "draft",
  PUBLISHED = "published",
  RETIRED = "retired",
}

export enum EmployeeProfessionalType {
  MEDICO = "MEDICO",
  ENFERMEIRO = "ENFERMEIRO",
}

export enum FindingNature {
  ORIGINAL_DATA = "ORIGINAL_DATA",
  DETERMINISTIC_CLASSIFICATION = "DETERMINISTIC_CLASSIFICATION",
  MODEL_OBSERVATION = "MODEL_OBSERVATION",
  ASSISTED_HYPOTHESIS = "ASSISTED_HYPOTHESIS",
  REGISTERED_DIAGNOSIS = "REGISTERED_DIAGNOSIS",
  PROFESSIONAL_DECISION = "PROFESSIONAL_DECISION",
}

export enum LlmCallStatus {
  SUCCESS = "SUCCESS",
  FAILED = "FAILED",
  SKIPPED = "SKIPPED",
}

export enum LlmProvider {
  LOCAL = "LOCAL",
  OPENAI = "OPENAI",
  GEMINI = "GEMINI",
}

export enum MediaUploadState {
  AWAITING_UPLOAD = "AWAITING_UPLOAD",
  QUARANTINED = "QUARANTINED",
  APPROVED = "APPROVED",
  REJECTED = "REJECTED",
  EXPIRED = "EXPIRED",
}

export enum ModalityAttentionLevel {
  NONE = "NONE",
  OBSERVATION = "OBSERVATION",
  ATTENTION = "ATTENTION",
}

export enum ModalityQualityState {
  ADEQUATE = "ADEQUATE",
  MODERATE = "MODERATE",
  INSUFFICIENT = "INSUFFICIENT",
  INVALID = "INVALID",
}

export enum ModalityStatus {
  PENDING = "PENDING",
  PROCESSING = "PROCESSING",
  COMPLETED = "COMPLETED",
  FAILED_RETRYABLE = "FAILED_RETRYABLE",
  FAILED_FINAL = "FAILED_FINAL",
}

export enum ModalityType {
  AUDIO = "AUDIO",
  VIDEO = "VIDEO",
  IMAGE = "IMAGE",
  TEXT = "TEXT",
}

export enum ObservationReadingQuality {
  VALID = "VALID",
  DOUBTFUL = "DOUBTFUL",
  INVALID = "INVALID",
}

export enum ObservationType {
  BLOOD_PRESSURE = "BLOOD_PRESSURE",
  HEIGHT = "HEIGHT",
  WEIGHT = "WEIGHT",
  SPO2 = "SPO2",
  GLYCEMIA = "GLYCEMIA",
  TEMPERATURE = "TEMPERATURE",
  HEART_RATE = "HEART_RATE",
  RESPIRATORY_RATE = "RESPIRATORY_RATE",
  PAIN = "PAIN",
  CONSCIOUSNESS = "CONSCIOUSNESS",
  URINE_OUTPUT = "URINE_OUTPUT",
  SEIZURE = "SEIZURE",
}

export enum ReportState {
  DRAFT = "DRAFT",
  CONFIRMED = "CONFIRMED",
}

export enum ReviewDecisionAction {
  ACCEPT = "ACCEPT",
  CORRECT = "CORRECT",
  REJECT = "REJECT",
}

export enum ReviewStatus {
  PENDING = "PENDING",
  ACCEPTED = "ACCEPTED",
  CORRECTED = "CORRECTED",
  REJECTED = "REJECTED",
}

export enum RiskLevelCode {
  LOW = 1,
  MILD = 2,
  MODERATE = 3,
  HIGH = 4,
  VERY_HIGH = 5,
  CRITICAL = 6,
}

export enum RuleEvaluationInconclusiveReason {
  NO_RULE_SET_AVAILABLE = "NO_RULE_SET_AVAILABLE",
  MISSING_REQUIRED_INPUT = "MISSING_REQUIRED_INPUT",
  INVALID_INPUT = "INVALID_INPUT",
  NO_RULE_MATCHED = "NO_RULE_MATCHED",
}

export enum RuleEvaluationOutcome {
  MATCHED = "MATCHED",
  INCONCLUSIVE = "INCONCLUSIVE",
}

export enum SentimentAnalysisStatus {
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
  UNAVAILABLE = "UNAVAILABLE",
}

export enum TranscriptionProvider {
  LOCAL = "LOCAL",
  AZURE_SPEECH = "AZURE_SPEECH",
}

export enum TranscriptionStatus {
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
  UNAVAILABLE = "UNAVAILABLE",
}

export enum UserRole {
  ADMINISTRADOR_TECNICO = "ADMINISTRADOR_TECNICO",
  ADMINISTRADOR_CLINICO = "ADMINISTRADOR_CLINICO",
  MEDICO = "MEDICO",
  ENFERMEIRO = "ENFERMEIRO",
  AUDITOR = "AUDITOR",
}

export enum VisionAnalysisStatus {
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
  UNAVAILABLE = "UNAVAILABLE",
}

export enum VisionProvider {
  LOCAL = "LOCAL",
  OPENPOSE_YOLOV8 = "OPENPOSE_YOLOV8",
}

export const ANALYSIS_STATUS_TRANSITIONS: Record<AnalysisStatus, AnalysisStatus[]> = {
  [AnalysisStatus.CREATED]: [AnalysisStatus.UPLOADING, AnalysisStatus.CANCELLED],
  [AnalysisStatus.UPLOADING]: [AnalysisStatus.QUEUED, AnalysisStatus.CANCELLED],
  [AnalysisStatus.QUEUED]: [AnalysisStatus.PROCESSING, AnalysisStatus.CANCELLED],
  [AnalysisStatus.PROCESSING]: [AnalysisStatus.PARTIALLY_COMPLETED, AnalysisStatus.WAITING_REVIEW, AnalysisStatus.FAILED_RETRYABLE, AnalysisStatus.FAILED_FINAL, AnalysisStatus.CANCELLED],
  [AnalysisStatus.PARTIALLY_COMPLETED]: [AnalysisStatus.WAITING_REVIEW, AnalysisStatus.FAILED_FINAL, AnalysisStatus.CANCELLED],
  [AnalysisStatus.WAITING_REVIEW]: [AnalysisStatus.COMPLETED],
  [AnalysisStatus.COMPLETED]: [],
  [AnalysisStatus.FAILED_RETRYABLE]: [AnalysisStatus.QUEUED, AnalysisStatus.CANCELLED],
  [AnalysisStatus.FAILED_FINAL]: [],
  [AnalysisStatus.CANCELLED]: [],
};
