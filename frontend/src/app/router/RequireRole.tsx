import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { hasPermission, type NavPermissionKey } from "@/app/permissions";
import { Skeleton } from "@/components/feedback/Skeleton";

interface RequireRoleProps {
  permission: NavPermissionKey;
  children: ReactNode;
}

/**
 * Guarda de rota no cliente: todas as rotas protegidas verificam
 * autenticacao e autorizacao no carregamento. Redireciona para
 * `/access-denied` quando o papel do usuario ativo nao tem a permissao
 * exigida.
 *
 * Isto e conveniencia de navegacao, nao a autorizacao real: toda rota HTTP
 * chamada pela tela continua protegida por `require_role` no backend
 * (app/core/security.py), que rejeita com 403 independente do que esta
 * guarda decidir aqui.
 */
export function RequireRole({ permission, children }: RequireRoleProps) {
  const { subject, role, isLoading } = useCurrentUser();

  // Sem usuario de sessao selecionado: deixa a tela renderizar normalmente
  // (ela propria mostra o pedido para configurar a sessao de dev, ver
  // DevSessionBanner) em vez de redirecionar - nao ha papel ainda para
  // avaliar.
  if (!subject) return <>{children}</>;

  if (isLoading) return <Skeleton rows={4} />;

  if (!hasPermission(role, permission)) {
    return <Navigate to="/access-denied" replace />;
  }

  return <>{children}</>;
}
