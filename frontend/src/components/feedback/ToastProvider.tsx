import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, X, XCircle } from "lucide-react";
import styles from "./Toast.module.css";

type ToastVariant = "success" | "error";

interface ToastItem {
  id: number;
  variant: ToastVariant;
  message: string;
}

interface ToastContextValue {
  /** Exibe uma notificacao de sucesso (ex.: "Paciente criado com sucesso."). */
  showSuccess: (message: string) => void;
  /** Exibe uma notificacao de erro (ex.: "Nao foi possivel salvar o paciente."). */
  showError: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const AUTO_DISMISS_MS = 6000;

/**
 * Notificacao global de sucesso/erro (toast), usada por toda tela com
 * fluxo de salvar/editar/excluir - ate esta implementacao, o feedback de
 * conclusao de uma acao era so implicito (modal fechava, tabela
 * atualizava) e o de erro era inconsistente entre telas (mensagem generica
 * fixa em algumas, texto bruto do backend em outras, ausente em outras
 * ainda). Este provider centraliza os dois casos com um padrao visual e
 * textual unico em portugues.
 *
 * Empilha varias notificacoes (ex.: duas acoes rapidas em sequencia) e
 * remove cada uma automaticamente apos `AUTO_DISMISS_MS`, ou ao clicar no
 * X. Usa `aria-live` (via `role="status"`/`role="alert"` no proprio
 * toast) para leitores de tela anunciarem o resultado sem precisar de foco
 * manual.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback(
    (variant: ToastVariant, message: string) => {
      const id = nextId.current++;
      setToasts((current) => [...current, { id, variant, message }]);
      window.setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    },
    [dismiss],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      showSuccess: (message: string) => show("success", message),
      showError: (message: string) => show("error", message),
    }),
    [show],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div className={styles.viewport}>
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={`${styles.toast} ${toast.variant === "success" ? styles.success : styles.error}`}
              role={toast.variant === "success" ? "status" : "alert"}
            >
              <span className={styles.icon}>
                {toast.variant === "success" ? (
                  <CheckCircle2 size={20} strokeWidth={2} aria-hidden="true" />
                ) : (
                  <XCircle size={20} strokeWidth={2} aria-hidden="true" />
                )}
              </span>
              <span className={styles.message}>{toast.message}</span>
              <button
                type="button"
                className={styles.closeButton}
                onClick={() => dismiss(toast.id)}
                aria-label="Fechar notificação"
              >
                <X size={16} strokeWidth={2} aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

/**
 * Hook de acesso ao toast global - `showSuccess`/`showError` a partir de
 * qualquer tela dentro de `ToastProvider` (montado uma unica vez em
 * `App.tsx`). Lanca erro se usado fora do provider para nunca falhar
 * silenciosamente (mesma disciplina de `useDevSession`/`useCurrentUser`).
 */
export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast precisa ser usado dentro de um ToastProvider.");
  }
  return context;
}
