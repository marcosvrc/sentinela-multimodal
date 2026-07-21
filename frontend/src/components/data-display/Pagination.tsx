import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import styles from "./Pagination.module.css";

interface PaginationProps {
  page: number;
  totalPages: number;
  totalItems: number;
  onPageChange: (page: number) => void;
}

/**
 * Navegacao entre paginas de uma `DataTable`, refletindo `page`/`total_pages`
 * de `PageResponse`. As listas de administracao sempre pediam a pagina 1;
 * este componente permite navegar entre todas.
 */
export function Pagination({ page, totalPages, totalItems, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null;

  return (
    <nav className={styles.wrapper} aria-label="Paginacao">
      <span className={styles.summary}>
        Pagina {page} de {totalPages} ({totalItems} {totalItems === 1 ? "registro" : "registros"})
      </span>
      <div className={styles.controls}>
        <Button
          type="button"
          variant="secondary"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          <ChevronLeft size={16} strokeWidth={2} aria-hidden="true" />
          Anterior
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
        >
          Proxima
          <ChevronRight size={16} strokeWidth={2} aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
