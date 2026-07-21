/**
 * Tipos dos contratos HTTP compartilhados.
 * Espelha backend/app/api/schemas/common.py. Ainda escrito a mao; candidato
 * a geracao automatica a partir de docs/contracts/openapi.json numa
 * iteracao futura (ver docs/contracts/README.md).
 */

export interface ErrorResponse {
  code: string;
  message: string;
  field_errors: Record<string, string>;
  request_id: string | null;
}

export interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

/** Erro tipado lancado pelo cliente HTTP quando a API responde com falha. */
export class ApiRequestError extends Error {
  readonly status: number;
  readonly body: ErrorResponse | null;

  constructor(status: number, body: ErrorResponse | null) {
    super(body?.message ?? `Falha na requisicao (status ${status})`);
    this.name = "ApiRequestError";
    this.status = status;
    this.body = body;
  }

  get code(): string | null {
    return this.body?.code ?? null;
  }

  get fieldErrors(): Record<string, string> {
    return this.body?.field_errors ?? {};
  }
}
