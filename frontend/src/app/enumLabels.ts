/**
 * Rotulos em portugues (pt-BR) para os valores de enum que o backend
 * devolve em ingles (fonte unica de verdade: backend/app/core/enums.py,
 * exportado por `make codegen`). Alguns enums (ex.: `UserRole`,
 * `EmployeeProfessionalType`) ja usam palavras em portugues como valor e
 * nao precisam de rotulo aqui; os demais (estados internos do sistema,
 * como `ModalityType`, `ObservationReadingQuality`, `AlertSeverity` etc.)
 * usam identificadores em ingles que nunca devem aparecer crus na tela -
 * sempre passar pelo mapa correspondente antes de renderizar.
 *
 * Centralizado aqui (em vez de duplicado por tela) para evitar o mesmo
 * enum ganhar traducoes diferentes em lugares diferentes.
 */
import {
  AlertSeverity,
  AlertStatus,
  AuditCategory,
  AuditResult,
  ModalityQualityState,
  ModalityType,
  ObservationReadingQuality,
  RuleEvaluationInconclusiveReason,
  RuleEvaluationOutcome,
  UserRole,
} from "@/types/enums.generated";

export const ROLE_LABELS: Record<string, string> = {
  [UserRole.MEDICO]: "Médico",
  [UserRole.ENFERMEIRO]: "Enfermeiro",
  [UserRole.ADMINISTRADOR_TECNICO]: "Administrador técnico",
  [UserRole.ADMINISTRADOR_CLINICO]: "Administrador clínico",
  [UserRole.AUDITOR]: "Auditor",
};

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role;
}

export const MODALITY_LABELS: Record<string, string> = {
  [ModalityType.IMAGE]: "Imagem",
  [ModalityType.AUDIO]: "Áudio",
  [ModalityType.VIDEO]: "Vídeo",
  [ModalityType.TEXT]: "Texto",
};

export function modalityLabel(modalityType: string): string {
  return MODALITY_LABELS[modalityType] ?? modalityType;
}

export const READING_QUALITY_LABELS: Record<string, string> = {
  [ObservationReadingQuality.VALID]: "Válida",
  [ObservationReadingQuality.DOUBTFUL]: "Duvidosa",
  [ObservationReadingQuality.INVALID]: "Inválida",
};

export function readingQualityLabel(quality: string): string {
  return READING_QUALITY_LABELS[quality] ?? quality;
}

export const ALERT_SEVERITY_LABELS: Record<string, string> = {
  [AlertSeverity.MODERATE]: "Moderada",
  [AlertSeverity.HIGH]: "Alta",
  [AlertSeverity.CRITICAL]: "Crítica",
};

export function alertSeverityLabel(severity: string): string {
  return ALERT_SEVERITY_LABELS[severity] ?? severity;
}

export const ALERT_STATUS_LABELS: Record<string, string> = {
  [AlertStatus.OPEN]: "Aberto",
  [AlertStatus.ACKNOWLEDGED]: "Reconhecido",
  [AlertStatus.ESCALATED]: "Escalado",
  [AlertStatus.RESOLVED]: "Encerrado",
};

export function alertStatusLabel(status: string): string {
  return ALERT_STATUS_LABELS[status] ?? status;
}

export const RULE_EVALUATION_OUTCOME_LABELS: Record<string, string> = {
  [RuleEvaluationOutcome.MATCHED]: "Classificado",
  [RuleEvaluationOutcome.INCONCLUSIVE]: "Inconclusivo",
};

export function ruleEvaluationOutcomeLabel(outcome: string): string {
  return RULE_EVALUATION_OUTCOME_LABELS[outcome] ?? outcome;
}

export const RULE_EVALUATION_INCONCLUSIVE_REASON_LABELS: Record<string, string> = {
  [RuleEvaluationInconclusiveReason.NO_RULE_SET_AVAILABLE]: "Nenhum conjunto de regras disponível",
  [RuleEvaluationInconclusiveReason.MISSING_REQUIRED_INPUT]: "Dado obrigatório ausente",
  [RuleEvaluationInconclusiveReason.INVALID_INPUT]: "Dado inválido",
  [RuleEvaluationInconclusiveReason.NO_RULE_MATCHED]: "Nenhuma regra correspondente",
};

export function ruleEvaluationInconclusiveReasonLabel(reason: string): string {
  return RULE_EVALUATION_INCONCLUSIVE_REASON_LABELS[reason] ?? reason;
}

export const MODALITY_QUALITY_STATE_LABELS: Record<string, string> = {
  [ModalityQualityState.ADEQUATE]: "Adequada",
  [ModalityQualityState.MODERATE]: "Moderada",
  [ModalityQualityState.INSUFFICIENT]: "Insuficiente",
  [ModalityQualityState.INVALID]: "Inválida",
};

export function modalityQualityStateLabel(state: string): string {
  return MODALITY_QUALITY_STATE_LABELS[state] ?? state;
}

export const AUDIT_CATEGORY_LABELS: Record<string, string> = {
  [AuditCategory.AUTHENTICATION]: "Autenticação",
  [AuditCategory.AUTHORIZATION]: "Autorização",
  [AuditCategory.DATA]: "Dados",
  [AuditCategory.FILES]: "Arquivos",
  [AuditCategory.ADMINISTRATION]: "Administração",
  [AuditCategory.ANALYSIS]: "Análise",
  [AuditCategory.AI]: "IA",
  [AuditCategory.REVIEW]: "Revisão",
  [AuditCategory.AUDIT]: "Auditoria",
};

export function auditCategoryLabel(category: string): string {
  return AUDIT_CATEGORY_LABELS[category] ?? category;
}

export const AUDIT_RESULT_LABELS: Record<string, string> = {
  [AuditResult.SUCCESS]: "Sucesso",
  [AuditResult.DENIED]: "Negado",
  [AuditResult.ERROR]: "Erro",
};

export function auditResultLabel(result: string): string {
  return AUDIT_RESULT_LABELS[result] ?? result;
}
