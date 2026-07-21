import type { ReactNode } from "react";
import styles from "./Section.module.css";

interface SectionProps {
  title?: string;
  description?: string;
  action?: ReactNode;
  /**
   * "card" (padrao): moldura, sombra e fundo proprio - usada para blocos
   * de nivel de pagina (filtros, tabelas, resumo) que precisam se destacar
   * do restante do layout.
   * "plain": apenas um rotulo discreto com divisor abaixo, sem moldura -
   * usada para sub-agrupar campos dentro de formularios/modais que ja tem
   * sua propria moldura (ex.: "Identificacao" vs "Acesso ao sistema" no
   * cadastro de funcionario).
   */
  variant?: "card" | "plain";
  children: ReactNode;
}

/**
 * Agrupador visual generico para campos e tabelas correlatos, usado para
 * organizar a hierarquia de telas. Centraliza o padrao visual de "cartao
 * com titulo" usado em filtros, tabelas e resumos, para nao repetir a
 * mesma moldura/sombra inline em cada tela.
 */
export function Section({ title, description, action, variant = "card", children }: SectionProps) {
  const isPlain = variant === "plain";

  return (
    <section className={isPlain ? styles.plain : styles.card}>
      {(title || description || action) && (
        <div className={isPlain ? styles.plainHeader : styles.cardHeader}>
          <div>
            {title && <h2 className={isPlain ? styles.plainTitle : styles.cardTitle}>{title}</h2>}
            {description && <p className={styles.description}>{description}</p>}
          </div>
          {action && <div className={styles.action}>{action}</div>}
        </div>
      )}
      {children}
    </section>
  );
}
