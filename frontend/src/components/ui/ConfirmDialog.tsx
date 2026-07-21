import type { ReactNode } from "react";
import { Modal } from "./Modal";
import { Button } from "./Button";
import styles from "./ConfirmDialog.module.css";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** "danger" para acoes destrutivas/irreversiveis (ex.: desativar registro). */
  variant?: "primary" | "danger";
  pending?: boolean;
  /** Desabilita o botao de confirmar sem exibir o estado "Enviando..." (ex.: campo obrigatorio vazio). */
  confirmDisabled?: boolean;
  errorMessage?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
  /** Ver `Modal.size` - a maioria das confirmacoes cabe confortavelmente
   * no tamanho "sm" (480px); passe "md" quando `children` incluir varios
   * campos de formulario. */
  size?: "sm" | "md" | "lg";
}

/**
 * Dialogo de confirmacao reforcada, usado para desativacao de registros,
 * publicacao/rollback de regra clinica e revogacao de sessao. `children`
 * permite anexar campos extras (ex.: aprovador + justificativa) quando a
 * confirmacao exige mais do que um simples aceite.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  variant = "primary",
  pending = false,
  confirmDisabled = false,
  errorMessage,
  onConfirm,
  onCancel,
  children,
  size = "sm",
}: ConfirmDialogProps) {
  return (
    <Modal open={open} title={title} onClose={onCancel} size={size}>
      <div className={styles.description}>{description}</div>
      {children && <div className={styles.extra}>{children}</div>}
      {errorMessage && (
        <p role="alert" className={styles.error}>
          {errorMessage}
        </p>
      )}
      <div className={styles.actions}>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={pending}>
          {cancelLabel}
        </Button>
        <Button
          type="button"
          variant={variant}
          onClick={onConfirm}
          disabled={pending || confirmDisabled}
        >
          {pending ? "Enviando..." : confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
