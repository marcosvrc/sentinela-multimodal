/**
 * Papel/identidade do usuario de sessao ativo, resolvido pelo backend
 * (`GET /me` - nunca inferido no cliente). Usado pela navegacao e pelo
 * guard de rotas para decidir o que exibir/permitir.
 */
import { useQuery } from "@tanstack/react-query";
import { useDevSession } from "./useDevSession";
import { getCurrentUser } from "@/services/api/me";

export function useCurrentUser() {
  const { subject } = useDevSession();

  const query = useQuery({
    queryKey: ["me", subject],
    queryFn: () => getCurrentUser(subject as string),
    enabled: Boolean(subject),
    staleTime: 60_000,
  });

  return {
    subject,
    user: query.data ?? null,
    role: query.data?.role,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
