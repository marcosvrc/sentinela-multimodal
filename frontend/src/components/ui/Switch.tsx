import styles from "./Switch.module.css";

interface SwitchProps {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  hint?: string;
  disabled?: boolean;
}

/**
 * Interruptor liga/desliga (tela de feature flags - `/admin/feature-
 * flags`). Diferente de um checkbox generico, o rotulo e sempre visivel
 * ao lado (nunca so um icone), para que "ligado"/"desligado" nunca
 * dependa so da cor.
 */
export function Switch({ id, label, checked, onChange, hint, disabled }: SwitchProps) {
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.row}>
        <span className={styles.labelText}>
          {label}
          {hint && <span className={styles.hint}>{hint}</span>}
        </span>
        <span className={styles.switchTrack}>
          <input
            id={id}
            type="checkbox"
            role="switch"
            aria-checked={checked}
            checked={checked}
            disabled={disabled}
            onChange={(event) => onChange(event.target.checked)}
            className={styles.input}
          />
          <span className={styles.track} data-checked={checked} aria-hidden="true">
            <span className={styles.thumb} />
          </span>
        </span>
      </label>
    </div>
  );
}
