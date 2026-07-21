import { QueryProvider } from "@/app/providers/QueryProvider";
import { AppRouter } from "@/app/router/AppRouter";
import { ToastProvider } from "@/components/feedback/ToastProvider";

/**
 * O AppShell/Sidebar/Topbar e as rotas de pacientes ja estao implementados.
 * Autenticacao, dashboard, analises, auditoria e administracao entram nas
 * proximas iteracoes.
 *
 * `ToastProvider` fica fora do `AppRouter` (nao dentro de uma rota
 * especifica) para as notificacoes de sucesso/erro sobreviverem a uma
 * navegacao disparada pela propria acao (ex.: criar paciente e navegar
 * para o detalhe) e para ficarem disponiveis em qualquer tela via
 * `useToast()`.
 */
export default function App() {
  return (
    <QueryProvider>
      <ToastProvider>
        <AppRouter />
      </ToastProvider>
    </QueryProvider>
  );
}
