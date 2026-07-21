import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import styles from "./Modal.module.css";

interface ModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Rotulo acessivel adicional, quando o titulo visivel nao for suficiente. */
  describedById?: string;
  /**
   * Largura do dialogo: "sm" para confirmacoes curtas, "md" (padrao) para
   * formularios de cadastro/edicao, "lg" para conteudo mais denso (tabelas,
   * varias secoes) como o detalhe de um conjunto de regras clinicas.
   */
  size?: "sm" | "md" | "lg";
}

const MAX_WIDTH_BY_SIZE: Record<"sm" | "md" | "lg", number> = {
  sm: 480,
  md: 640,
  lg: 960,
};

/**
 * Sobreposicao modal basica: fecha com `Esc`, clique fora do conteudo e
 * botao de fechar; prende o foco dentro do conteudo enquanto aberto;
 * devolve o foco ao elemento que abriu o modal ao fechar. Base de
 * `ConfirmDialog` e dos formularios de cadastro/edicao das telas de
 * administracao.
 */
export function Modal({
  open,
  title,
  onClose,
  children,
  describedById,
  size = "md",
}: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerElementRef = useRef<HTMLElement | null>(null);

  // Guarda a versao mais recente de `onClose` sem entrar na dependencia do
  // efeito abaixo. `onClose` normalmente e uma arrow function inline
  // (`onClose={() => setFormOpen(false)}`), recriada a cada render do
  // formulario pai - inclusive a cada tecla digitada em um campo dentro do
  // modal. Se o efeito dependesse de `onClose`, ele rodaria de novo a cada
  // digitacao e chamaria `dialogRef.current?.focus()`, roubando o foco do
  // campo de texto para o container do dialogo. O efeito de foco/teclado
  // deve rodar apenas quando o modal abre ou fecha (`open`), nunca por
  // mudanca de identidade de `onClose`.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    triggerElementRef.current = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      triggerElementRef.current?.focus();
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div className={styles.overlay} onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <div
        ref={dialogRef}
        className={styles.dialog}
        style={{ maxWidth: MAX_WIDTH_BY_SIZE[size] }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        aria-describedby={describedById}
        tabIndex={-1}
      >
        <div className={styles.header}>
          <h2 id="modal-title" className={styles.title}>
            {title}
          </h2>
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label="Fechar"
          >
            <X size={20} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </div>,
    document.body,
  );
}
