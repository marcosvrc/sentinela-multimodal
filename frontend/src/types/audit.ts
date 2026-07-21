/** Espelha backend/app/api/schemas/audit.py. */
import type { AuditCategory, AuditResult } from "./enums.generated";

export interface AuditEvent {
  id: string;
  sequence: number;
  occurred_at: string;
  actor: string;
  actor_role: string | null;
  unit: string | null;
  category: AuditCategory;
  action: string;
  resource_type: string;
  resource_id: string | null;
  result: AuditResult;
  justification: string | null;
  request_id: string | null;
  analysis_id: string | null;
  workflow_id: string | null;
  job_id: string | null;
  /** Detalhe completo da acao (payload especifico de cada `action`),
   * exibido via popup dedicado - a tabela de auditoria e append-only,
   * nunca editada. */
  event_metadata: Record<string, unknown>;
  event_hash: string;
  prev_hash: string | null;
}
