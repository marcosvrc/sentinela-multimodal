/**
 * Tipos de alerta de anomalia.
 * Espelha backend/app/api/schemas/alerts.py.
 */
import type { AlertSeverity, AlertStatus } from "./enums.generated";

export interface ClinicalAlert {
  id: string;
  patient_id: string;
  observation_id: string | null;
  signal_key: string;
  severity: AlertSeverity;
  status: AlertStatus;
  detector_source: string;
  confidence: number | null;
  evidence: Record<string, unknown>;
  expected_action: string;
  detected_at: string;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  escalated_to: string | null;
  escalated_at: string | null;
  escalation_reason: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_notes: string | null;
  created_at: string;
}

export interface EscalateAlertInput {
  escalated_to: string;
  reason: string;
}

export interface ResolveAlertInput {
  notes: string;
}

/** Contagem de alertas por severidade (todos os status), usada nos "big
 * numbers" do painel de alertas antes de escolher uma severidade para
 * ver o detalhe paginado. */
export interface AlertSeverityCounts {
  critical: number;
  high: number;
  moderate: number;
}
