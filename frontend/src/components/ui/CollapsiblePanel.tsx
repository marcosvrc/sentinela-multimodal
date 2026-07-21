import { useState } from "react";
import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import styles from "./CollapsiblePanel.module.css";

interface CollapsiblePanelProps {
  title: string;
  countLabel?: string;
  defaultOpen?: boolean;
  /**
   * Quando `true`, forca a renderizacao do conteudo (tabela/grafico)
   * independente do estado de expansao escolhido pelo usuario - usado
   * pela geracao de PDF da tela de paciente (`PatientDetailPage`), que
   * precisa que todos os paineis fechados apareçam no documento exportado
   * sem alterar permanentemente a preferencia de expansao do usuario.
   */
  forceOpen?: boolean;
  children: ReactNode;
}

/**
 * Painel expansivel generico (fecha por padrao). Usado para agrupar
 * conteudo denso por categoria - ex.: um painel por tipo de observacao
 * clinica na tela de paciente, cada um com tabela + grafico ocultos até
 * o usuario expandir.
 */
export function CollapsiblePanel({
  title,
  countLabel,
  defaultOpen = false,
  forceOpen = false,
  children,
}: CollapsiblePanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  const isExpanded = open || forceOpen;
  const contentId = `panel-content-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

  return (
    <div className={styles.panel}>
      <button
        type="button"
        className={styles.toggle}
        aria-expanded={isExpanded}
        aria-controls={contentId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className={styles.titleGroup}>
          <span className={styles.title}>{title}</span>
          {countLabel && <span className={styles.count}>{countLabel}</span>}
        </span>
        <ChevronDown
          aria-hidden="true"
          size={18}
          strokeWidth={2}
          className={[styles.chevron, isExpanded && styles.chevronOpen].filter(Boolean).join(" ")}
        />
      </button>
      {isExpanded && (
        <div id={contentId} className={styles.content}>
          {children}
        </div>
      )}
    </div>
  );
}
