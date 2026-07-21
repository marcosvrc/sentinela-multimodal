import { EmptyState } from "@/components/feedback/EmptyState";
import { LinkButton } from "@/components/ui/LinkButton";

export function NotFoundPage() {
  return (
    <EmptyState
      title="Pagina nao encontrada"
      description="O recurso solicitado nao existe ou foi movido."
      action={<LinkButton to="/patients">Voltar para pacientes</LinkButton>}
    />
  );
}
