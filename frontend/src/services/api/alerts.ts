/**
 * Chamadas tipadas da API de alertas de anomalia.
 * Ver backend/app/api/routes/alerts.py.
 */
import { apiFetch } from "./client";
import type { PageResponse } from "@/types/api";
import type {
  AlertSeverityCounts,
  ClinicalAlert,
  EscalateAlertInput,
  ResolveAlertInput,
} from "@/types/alerts";

export function listPatientAlerts(
  devSubject: string,
  patientId: string,
  params: { page?: number; pageSize?: number; status?: string; severity?: string } = {},
): Promise<PageResponse<ClinicalAlert>> {
  return apiFetch<PageResponse<ClinicalAlert>>(`/patients/${patientId}/alerts`, {
    devSubject,
    searchParams: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      status: params.status,
      severity: params.severity,
    },
  });
}

export function getPatientAlertsSummary(
  devSubject: string,
  patientId: string,
): Promise<AlertSeverityCounts> {
  return apiFetch<AlertSeverityCounts>(`/patients/${patientId}/alerts/summary`, { devSubject });
}

export function acknowledgeAlert(devSubject: string, alertId: string): Promise<ClinicalAlert> {
  return apiFetch<ClinicalAlert>(`/alerts/${alertId}/acknowledge`, {
    devSubject,
    method: "POST",
  });
}

export function escalateAlert(
  devSubject: string,
  alertId: string,
  data: EscalateAlertInput,
): Promise<ClinicalAlert> {
  return apiFetch<ClinicalAlert>(`/alerts/${alertId}/escalate`, {
    devSubject,
    method: "POST",
    body: data,
  });
}

export function resolveAlert(
  devSubject: string,
  alertId: string,
  data: ResolveAlertInput,
): Promise<ClinicalAlert> {
  return apiFetch<ClinicalAlert>(`/alerts/${alertId}/resolve`, {
    devSubject,
    method: "POST",
    body: data,
  });
}
