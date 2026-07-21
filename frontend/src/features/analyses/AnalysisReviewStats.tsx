import styles from "./AnalysisReviewStats.module.css";
import type { AnalysisStats, ReportContent } from "@/types/analysis";

const RISK_COLOR_BY_LEVEL: Record<number, string> = {
  1: "var(--risk-low)",
  2: "var(--risk-mild)",
  3: "var(--risk-moderate)",
  4: "var(--risk-high)",
  5: "var(--risk-very-high)",
  6: "var(--risk-critical)",
};

interface AnalysisReviewStatsProps {
  content: ReportContent;
  /** Estatisticas agregadas de todas as analises da instituicao
   * (`GET /analyses/stats`) - `undefined` enquanto ainda carregando, o
   * card correspondente mostra "-" nesse caso (nunca um numero
   * inventado). */
  stats: AnalysisStats | undefined;
}

/**
 * "Big numbers" no topo da tela de revisao da analise: visao rapida do
 * resultado desta analise especifica (nivel de risco, quantas
 * modalidades entraram,
 * se dados clinicos estruturados foram considerados, se o motor de
 * regras chegou a uma classificacao) mais um indicador AGREGADO (quantas
 * analises da instituicao, no total, o motor de regras conseguiu
 * classificar) para dar contexto de quao frequentemente o sistema chega
 * a um resultado conclusivo.
 */
export function AnalysisReviewStats({ content, stats }: AnalysisReviewStatsProps) {
  const isConclusive = content.calculated_risk.outcome === "MATCHED";
  const riskLevel = content.calculated_risk.risk_level;
  const riskColor = riskLevel !== null ? RISK_COLOR_BY_LEVEL[riskLevel] : "var(--risk-inconclusive)";

  const modalityCount = new Set(content.modality_evidence.map((item) => item.modality_type)).size;

  const hasClinicalData = Object.keys(content.identification.structured_clinical_inputs).length > 0;

  return (
    <div className={styles.cardsGrid}>
      <div className={styles.card} style={{ color: riskColor }}>
        <span className={styles.cardLabel}>Nível de risco</span>
        <span className={styles.cardNumber}>{riskLevel ?? "-"}</span>
        <span className={styles.cardHint}>
          {content.calculated_risk.classification_label ?? "Sem classificação"}
        </span>
      </div>

      <div className={styles.card}>
        <span className={styles.cardLabel}>Modalidade utilizada</span>
        <span className={styles.cardNumber}>{modalityCount}</span>
      </div>

      <div className={styles.card} style={{ color: hasClinicalData ? "var(--risk-low)" : undefined }}>
        <span className={styles.cardLabel}>Dados clínicos</span>
        <span className={styles.cardNumber}>{hasClinicalData ? "Sim" : "Não"}</span>
      </div>

      <div className={styles.card} style={{ color: isConclusive ? "var(--risk-low)" : "var(--risk-inconclusive)" }}>
        <span className={styles.cardLabel}>Resultado</span>
        <span className={styles.cardNumber}>{isConclusive ? "Conclusivo" : "Inconclusivo"}</span>
      </div>

      <div className={styles.card}>
        <span className={styles.cardLabel}>Análises conclusivas</span>
        <span className={styles.cardNumber}>
          {stats ? `${stats.conclusive_rate_percent}%` : "-"}
        </span>
        <span className={styles.cardHint}>
          {stats
            ? `${stats.conclusive_count} de ${stats.total_analyses_consolidated} análises`
            : "Carregando..."}
        </span>
      </div>
    </div>
  );
}
