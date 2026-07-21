import { ApiRequestError } from "@/types/api";

/**
 * Extrai uma mensagem de erro amigavel em portugues para exibir no toast
 * global (`useToast().showError`). `ApiRequestError.message` ja vem do
 * backend em portugues (ver `ErrorResponse.message`,
 * `app.core.errors.ApiError`) - usado como esta. Para qualquer outro erro
 * (rede indisponivel, erro inesperado do cliente), usa `fallback` para
 * nunca expor uma mensagem tecnica em ingles (ex.: "Failed to fetch") na
 * tela.
 */
export function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    return error.message;
  }
  return fallback;
}
