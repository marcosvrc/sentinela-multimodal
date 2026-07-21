import styles from "./RiskBadge.module.css";

/**
 * Tabela canonica de risco. A cor nunca e o unico meio de comunicacao:
 * nivel numerico, rotulo e texto sempre acompanham.
 */
const RISK_COLOR_BY_LEVEL: Record<number, string> = {
  1: "var(--risk-low)",
  2: "var(--risk-mild)",
  3: "var(--risk-moderate)",
  4: "var(--risk-high)",
  5: "var(--risk-very-high)",
  6: "var(--risk-critical)",
};

interface RiskBadgeProps {
  outcome: string;
  riskLevel: number | null;
  classificationLabel: string | null;
}

export function RiskBadge({ outcome, riskLevel, classificationLabel }: RiskBadgeProps) {
  if (outcome !== "MATCHED" || riskLevel === null) {
    return (
      <span
        className={styles.badge}
        style={{ background: "var(--risk-inconclusive)" }}
        role="status"
      >
        Inconclusivo
      </span>
    );
  }

  return (
    <span
      className={styles.badge}
      style={{ background: RISK_COLOR_BY_LEVEL[riskLevel] ?? "var(--risk-inconclusive)" }}
      role="status"
    >
      Nivel {riskLevel} · {classificationLabel ?? "Sem classificacao"}
    </span>
  );
}
