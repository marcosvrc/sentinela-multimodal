import styles from "./StatusBadge.module.css";
import { modalityAttentionLevelLabel } from "@/app/enumLabels";
import { ModalityAttentionLevel } from "@/types/enums.generated";

// Paleta de "tag" (fundo tintado + texto na mesma familia de cor) - a
// mesma usada por StatusBadge, DELIBERADAMENTE distinta da paleta de
// RiskBadge (preenchimento solido, reservada para severidade clinica
// real calculada pelo motor de regras). Este indicador nunca deve ser
// confundido visualmente com um nivel de risco.
const NEUTRAL = { bg: "var(--tag-neutral-bg)", text: "var(--tag-neutral-text)" };
const WARNING = { bg: "var(--tag-warning-bg)", text: "var(--tag-warning-text)" };
const DANGER = { bg: "var(--tag-danger-bg)", text: "var(--tag-danger-text)" };

const TONE_BY_LEVEL: Record<string, { bg: string; text: string }> = {
  [ModalityAttentionLevel.NONE]: NEUTRAL,
  [ModalityAttentionLevel.OBSERVATION]: WARNING,
  [ModalityAttentionLevel.ATTENTION]: DANGER,
};

interface ModalityAttentionBadgeProps {
  level: string;
}

/**
 * Indicador visual do "Nivel de atencao por modalidade" (ver
 * `ReportContent.modality_attention`) - NUNCA um nivel de risco clinico.
 * Usa a mesma paleta "tag" do `StatusBadge` (nunca a paleta solida do
 * `RiskBadge`) para reforçar visualmente que este e um indicador de
 * apoio a leitura, distinto do risco calculado pelo motor de regras.
 */
export function ModalityAttentionBadge({ level }: ModalityAttentionBadgeProps) {
  const tone = TONE_BY_LEVEL[level] ?? NEUTRAL;
  return (
    <span className={styles.badge} style={{ background: tone.bg, color: tone.text }}>
      <span className={styles.dot} aria-hidden="true" />
      {modalityAttentionLevelLabel(level)}
    </span>
  );
}
