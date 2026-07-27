import { useState } from "react";
import type { ReactNode } from "react";
import { Info } from "lucide-react";
import { Modal } from "./Modal";

interface InfoButtonProps {
  /** Título do popup de informação. */
  title: string;
  /** Conteúdo explicativo exibido dentro do popup. */
  children: ReactNode;
  /** Tamanho do modal: "sm" para textos curtos, "md" (padrão) para
   * explicações com tabelas de referência. */
  size?: "sm" | "md" | "lg";
}

/**
 * Ícone de informação (ⓘ) que, ao ser clicado, abre um popup modal com
 * uma explicação contextual da seção. Reutilizável em qualquer lugar da
 * aplicação onde seja necessário oferecer ajuda inline sem poluir a
 * interface principal.
 */
export function InfoButton({ title, children, size = "md" }: InfoButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`Informações sobre: ${title}`}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: 4,
          borderRadius: 4,
          display: "inline-flex",
          alignItems: "center",
          color: "var(--color-text-muted)",
          transition: "color 0.15s",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--color-primary-900)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--color-text-muted)"; }}
      >
        <Info size={16} strokeWidth={2} aria-hidden="true" />
      </button>
      <Modal open={open} title={title} onClose={() => setOpen(false)} size={size}>
        {children}
      </Modal>
    </>
  );
}
