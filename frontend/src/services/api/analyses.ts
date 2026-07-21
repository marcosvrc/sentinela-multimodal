/**
 * Chamadas tipadas de analise/midia/orquestracao/relatorio.
 * Ver backend/app/api/routes/{media,orchestrator,reports}.py.
 */
import { apiFetch } from "./client";
import type { PageResponse } from "@/types/api";
import type {
  Analysis,
  AnalysisClinicalSupportSummary,
  AnalysisCreateInput,
  AnalysisModalityState,
  AnalysisProfessional,
  AnalysisStats,
  MediaAsset,
  MediaUploadRequestInput,
  MediaUploadResponse,
  Report,
} from "@/types/analysis";

export function createAnalysis(devSubject: string, data: AnalysisCreateInput): Promise<Analysis> {
  return apiFetch<Analysis>("/analyses", { devSubject, method: "POST", body: data });
}

export function getAnalysis(devSubject: string, analysisId: string): Promise<Analysis> {
  return apiFetch<Analysis>(`/analyses/${analysisId}`, { devSubject });
}

export function listAnalyses(
  devSubject: string,
  params: {
    patientId?: string;
    createdBy?: string;
    createdFrom?: string;
    createdTo?: string;
    patientName?: string;
    patientMedicalRecordNumber?: string;
    page?: number;
    pageSize?: number;
  } = {},
): Promise<PageResponse<Analysis>> {
  return apiFetch<PageResponse<Analysis>>("/analyses", {
    devSubject,
    searchParams: {
      patient_id: params.patientId,
      created_by: params.createdBy || undefined,
      created_from: params.createdFrom || undefined,
      created_to: params.createdTo || undefined,
      patient_name: params.patientName || undefined,
      patient_medical_record_number: params.patientMedicalRecordNumber || undefined,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
    },
  });
}

export function listAnalysisProfessionals(devSubject: string): Promise<AnalysisProfessional[]> {
  return apiFetch<AnalysisProfessional[]>("/analyses/professionals", { devSubject });
}

/** Estatisticas agregadas de todas as analises da instituicao com
 * consolidacao de risco ja gravada (percentual de analises conclusivas) -
 * alimenta o "big number" de acuracia na tela de revisao da analise. */
export function getAnalysisStats(devSubject: string): Promise<AnalysisStats> {
  return apiFetch<AnalysisStats>("/analyses/stats", { devSubject });
}

export function requestMediaUpload(
  devSubject: string,
  analysisId: string,
  data: MediaUploadRequestInput,
): Promise<MediaUploadResponse> {
  return apiFetch<MediaUploadResponse>(`/analyses/${analysisId}/media`, {
    devSubject,
    method: "POST",
    body: data,
  });
}

export function confirmMediaUpload(
  devSubject: string,
  analysisId: string,
  mediaId: string,
  checksumSha256: string,
): Promise<MediaAsset> {
  return apiFetch<MediaAsset>(`/analyses/${analysisId}/media/${mediaId}/confirm`, {
    devSubject,
    method: "POST",
    body: { checksum_sha256: checksumSha256 },
  });
}

export function listMediaAssets(devSubject: string, analysisId: string): Promise<MediaAsset[]> {
  return apiFetch<MediaAsset[]>(`/analyses/${analysisId}/media`, { devSubject });
}

export function submitAnalysis(devSubject: string, analysisId: string): Promise<Analysis> {
  return apiFetch<Analysis>(`/analyses/${analysisId}/submit`, { devSubject, method: "POST" });
}

export function cancelAnalysis(devSubject: string, analysisId: string): Promise<Analysis> {
  return apiFetch<Analysis>(`/analyses/${analysisId}/cancel`, { devSubject, method: "POST" });
}

export function retryAnalysis(devSubject: string, analysisId: string): Promise<Analysis> {
  return apiFetch<Analysis>(`/analyses/${analysisId}/retry`, { devSubject, method: "POST" });
}

export function listModalityStates(
  devSubject: string,
  analysisId: string,
): Promise<AnalysisModalityState[]> {
  return apiFetch<AnalysisModalityState[]>(`/analyses/${analysisId}/modalities`, { devSubject });
}

export function getReport(devSubject: string, analysisId: string): Promise<Report> {
  return apiFetch<Report>(`/analyses/${analysisId}/report`, { devSubject });
}

export function confirmReport(devSubject: string, analysisId: string): Promise<Report> {
  return apiFetch<Report>(`/analyses/${analysisId}/report/confirm`, {
    devSubject,
    method: "POST",
  });
}

/** Gera o apoio a analise clinica assistido por LLM para esta analise
 * multimodal especifica (botao "Analisar dados clinicos" na tela de
 * revisao) - nunca persiste, cada chamada gera um resumo novo. */
export function generateAnalysisClinicalSupportSummary(
  devSubject: string,
  analysisId: string,
): Promise<AnalysisClinicalSupportSummary> {
  return apiFetch<AnalysisClinicalSupportSummary>(
    `/analyses/${analysisId}/clinical-support-summary`,
    { devSubject, method: "POST" },
  );
}

/** Faz o upload direto ao storage usando a URL/headers devolvidos por `requestMediaUpload`. */
export async function uploadFileToPresignedUrl(
  uploadUrl: string,
  method: string,
  headers: Record<string, string>,
  file: File,
): Promise<void> {
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const absoluteUrl = uploadUrl.startsWith("http") ? uploadUrl : `${API_BASE_URL}${uploadUrl}`;
  const response = await fetch(absoluteUrl, { method, headers, body: file });
  if (!response.ok) {
    throw new Error(`Falha ao enviar arquivo (status ${response.status}).`);
  }
}

export async function computeSha256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await window.crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Baixa o PDF do relatorio como blob (nao usa `<a href>` direto porque a
 * autenticacao de desenvolvimento vai em um header customizado -
 * `X-Dev-Subject` - que o navegador nao anexa a downloads simples).
 */
export async function downloadReportPdf(devSubject: string, analysisId: string): Promise<Blob> {
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const response = await fetch(`${API_BASE_URL}/analyses/${analysisId}/report/pdf`, {
    headers: { "X-Dev-Subject": devSubject },
  });
  if (!response.ok) {
    throw new Error(`Falha ao baixar o PDF (status ${response.status}).`);
  }
  return response.blob();
}
