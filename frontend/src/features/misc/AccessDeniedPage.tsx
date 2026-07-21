import styles from "@/components/feedback/States.module.css";
import { LinkButton } from "@/components/ui/LinkButton";

/**
 * Exibida quando o papel do usuario ativo nao tem a permissao exigida pela
 * rota atual (rota `/access-denied`).
 * So chega aqui por conveniencia de navegacao - a chamada real a API,
 * se tentada, seria rejeitada pelo backend com `403 FORBIDDEN_ROLE`
 * independente desta tela existir ou nao.
 */
export function AccessDeniedPage() {
  return (
    <div className={styles.state} role="alert">
      <p className={styles.stateTitle}>Acesso não autorizado</p>
      <p className={styles.stateDescription}>
        Seu papel não tem permissão para acessar esta área do sistema.
      </p>
      <LinkButton to="/">Voltar ao início</LinkButton>
    </div>
  );
}
