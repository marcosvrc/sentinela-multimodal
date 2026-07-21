/**
 * Chamadas tipadas da API de pacientes/observacoes.
 * Ver backend/app/api/routes/patients.py.
 */
import { apiFetch } from "./client";
import type { PageResponse } from "@/types/api";
import type {
  ClinicalObservation,
  ClinicalSupportSummary,
  ObservationCreateInput,
  Patient,
  PatientCreateInput,
  PatientUpdateInput,
} from "@/types/patient";

export function listPatients(
  devSubject: string,
  params: {
    page?: number;
    pageSize?: number;
    search?: string;
    active?: boolean;
    hasAnalyses?: boolean;
  } = {},
): Promise<PageResponse<Patient>> {
  return apiFetch<PageResponse<Patient>>("/patients", {
    devSubject,
    searchParams: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      search: params.search || undefined,
      active: params.active,
      has_analyses: params.hasAnalyses,
    },
  });
}

export function getPatient(devSubject: string, patientId: string): Promise<Patient> {
  return apiFetch<Patient>(`/patients/${patientId}`, { devSubject });
}

export function createPatient(devSubject: string, data: PatientCreateInput): Promise<Patient> {
  return apiFetch<Patient>("/patients", { devSubject, method: "POST", body: data });
}

export function updatePatient(
  devSubject: string,
  patientId: string,
  data: PatientUpdateInput,
): Promise<Patient> {
  return apiFetch<Patient>(`/patients/${patientId}`, { devSubject, method: "PATCH", body: data });
}

export function listObservations(
  devSubject: string,
  patientId: string,
): Promise<ClinicalObservation[]> {
  return apiFetch<ClinicalObservation[]>(`/patients/${patientId}/observations`, {
    devSubject,
  });
}

export function createObservation(
  devSubject: string,
  patientId: string,
  data: ObservationCreateInput,
): Promise<ClinicalObservation> {
  return apiFetch<ClinicalObservation>(`/patients/${patientId}/observations`, {
    devSubject,
    method: "POST",
    body: data,
  });
}

/** Gera o apoio a analise clinica assistido por LLM (botao "Analisar
 * dados clinicos") - nunca persiste, cada chamada gera um resumo novo. */
export function generateClinicalSupportSummary(
  devSubject: string,
  patientId: string,
): Promise<ClinicalSupportSummary> {
  return apiFetch<ClinicalSupportSummary>(`/patients/${patientId}/clinical-support-summary`, {
    devSubject,
    method: "POST",
  });
}
