import { Check } from "lucide-react";
import styles from "./AnalysisStepper.module.css";

export interface AnalysisStep {
  key: string;
  label: string;
}

interface AnalysisStepperProps {
  steps: AnalysisStep[];
  currentIndex: number;
}

/**
 * Indicador visual das etapas do fluxo em etapas de nova analise.
 * Somente exibe o progresso - a navegacao entre etapas (avancar/voltar) e feita
 * pelos botoes de cada etapa em `AnalysisNewPage`, nunca clicando
 * diretamente em um passo aqui (evita pular etapas com dados obrigatorios
 * ainda nao preenchidos).
 */
export function AnalysisStepper({ steps, currentIndex }: AnalysisStepperProps) {
  return (
    <ol className={styles.stepper}>
      {steps.map((step, index) => {
        const isDone = index < currentIndex;
        const isActive = index === currentIndex;
        return (
          <li key={step.key} className={styles.step}>
            {index > 0 && <span className={styles.connector} aria-hidden="true" />}
            <span
              className={[styles.badge, isActive && styles.badgeActive, isDone && styles.badgeDone]
                .filter(Boolean)
                .join(" ")}
              aria-hidden="true"
            >
              {isDone ? <Check size={16} strokeWidth={2.5} /> : index + 1}
            </span>
            <span className={[styles.label, isActive && styles.labelActive].filter(Boolean).join(" ")}>
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
