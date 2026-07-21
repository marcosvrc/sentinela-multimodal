import styles from "./StatusBadge.module.css";

// Tom "tag" (fundo tintado + texto na mesma familia de cor), distinto do
// preenchimento solido do RiskBadge - ver nota em styles/tokens.css sobre
// reservar alto-contraste para severidade clinica de fato.
const NEUTRAL = { bg: "var(--tag-neutral-bg)", text: "var(--tag-neutral-text)" };
const SUCCESS = { bg: "var(--tag-success-bg)", text: "var(--tag-success-text)" };
const WARNING = { bg: "var(--tag-warning-bg)", text: "var(--tag-warning-text)" };
const DANGER = { bg: "var(--tag-danger-bg)", text: "var(--tag-danger-text)" };

const TONE_BY_STATUS: Record<string, { bg: string; text: string }> = {
  CREATED: NEUTRAL,
  UPLOADING: NEUTRAL,
  QUEUED: NEUTRAL,
  PROCESSING: WARNING,
  PARTIALLY_COMPLETED: WARNING,
  WAITING_REVIEW: WARNING,
  COMPLETED: SUCCESS,
  FAILED_RETRYABLE: DANGER,
  FAILED_FINAL: DANGER,
  CANCELLED: NEUTRAL,
  PENDING: NEUTRAL,
  SUCCESS: SUCCESS,
  DENIED: DANGER,
  ERROR: DANGER,
  ATIVA: SUCCESS,
  ATIVO: SUCCESS,
  INATIVA: NEUTRAL,
  INATIVO: NEUTRAL,
  DESATIVADO: NEUTRAL,
  draft: NEUTRAL,
  published: SUCCESS,
  retired: NEUTRAL,
  rollback: WARNING,
  retired_by_new_publication: NEUTRAL,
  retired_by_rollback: NEUTRAL,
};

const LABEL_BY_STATUS: Record<string, string> = {
  CREATED: "Criada",
  UPLOADING: "Enviando midias",
  QUEUED: "Na fila",
  PROCESSING: "Processando",
  PARTIALLY_COMPLETED: "Parcialmente concluida",
  WAITING_REVIEW: "Aguardando revisao",
  COMPLETED: "Concluida",
  FAILED_RETRYABLE: "Falhou (pode repetir)",
  FAILED_FINAL: "Falhou (definitivo)",
  CANCELLED: "Cancelada",
  draft: "Rascunho",
  published: "Publicado",
  retired: "Revogado",
  rollback: "Rollback",
  retired_by_new_publication: "Substituído por nova versão",
  retired_by_rollback: "Revogado por rollback",
};

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const tone = TONE_BY_STATUS[status] ?? NEUTRAL;
  return (
    <span className={styles.badge} style={{ background: tone.bg, color: tone.text }}>
      <span className={styles.dot} aria-hidden="true" />
      {LABEL_BY_STATUS[status] ?? status}
    </span>
  );
}
