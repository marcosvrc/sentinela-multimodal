import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import styles from "./States.module.css";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className={styles.state} role="status">
      <Inbox className={styles.stateIcon} size={28} strokeWidth={1.5} aria-hidden="true" />
      <p className={styles.stateTitle}>{title}</p>
      {description && <p className={styles.stateDescription}>{description}</p>}
      {action}
    </div>
  );
}
