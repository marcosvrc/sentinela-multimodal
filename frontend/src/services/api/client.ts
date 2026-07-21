/**
 * Cliente HTTP compartilhado.
 *
 * Converte respostas de erro no formato padrao (ver
 * backend/app/core/errors.py) em `ApiRequestError`, para que as paginas
 * tratem erro de validacao, autenticacao e conflito de forma consistente.
 */
import { ApiRequestError, type ErrorResponse } from "@/types/api";
import type { HealthStatus } from "@/types/health";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /**
   * `external_subject` do usuario de desenvolvimento ativo (ver
   * `useDevSession`). O backend deriva instituicao e papel a partir dele;
   * o frontend nunca envia `institution_id` diretamente
   * (app/core/security.py::get_current_user).
   */
  devSubject?: string | null;
  searchParams?: Record<string, string | number | boolean | undefined>;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, devSubject, searchParams } = options;

  const url = new URL(`${API_BASE_URL}${path}`);
  if (searchParams) {
    for (const [key, value] of Object.entries(searchParams)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (devSubject) headers["X-Dev-Subject"] = devSubject;

  const response = await fetch(url.toString(), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let errorBody: ErrorResponse | null = null;
    try {
      errorBody = await response.json();
    } catch {
      errorBody = null;
    }
    throw new ApiRequestError(response.status, errorBody);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function getHealth() {
  return apiFetch<HealthStatus>("/health");
}
