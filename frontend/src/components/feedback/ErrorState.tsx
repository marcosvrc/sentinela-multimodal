import { AlertTriangle, RefreshCw } from "lucide-react";
import styles from "./States.module.css";
import { Button } from "@/components/ui/Button";

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = "Nao foi possivel carregar os dados",
  description,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className={styles.state} role="alert">
      <AlertTriangle
        className={styles.stateIcon}
        style={{ color: "var(--risk-high)" }}
        size={28}
        strokeWidth={1.5}
        aria-hidden="true"
      />
      <p className={styles.stateTitle}>{title}</p>
      {description && <p className={styles.stateDescription}>{description}</p>}
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw size={16} strokeWidth={2} aria-hidden="true" />
          Tentar novamente
        </Button>
      )}
    </div>
  );
}
