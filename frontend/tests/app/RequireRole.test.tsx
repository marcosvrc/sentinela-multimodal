import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RequireRole } from "@/app/router/RequireRole";

function mockFetchForRole(role: string) {
  return vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          id: "user-1",
          institution_id: "inst-1",
          external_subject: "dev-x",
          full_name: "Usuario Teste",
          role,
        }),
    }),
  ) as unknown as typeof fetch;
}

function renderProtected(role: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.stubGlobal("fetch", mockFetchForRole(role));
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/users"]}>
        <Routes>
          <Route
            path="/admin/users"
            element={
              <RequireRole permission="admin">
                <div>Tela de administracao</div>
              </RequireRole>
            }
          />
          <Route path="/access-denied" element={<div>Acesso negado</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RequireRole", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", "dev-x");
  });

  it("renderiza a tela quando o papel tem a permissao exigida", async () => {
    renderProtected("ADMINISTRADOR_TECNICO");
    expect(await screen.findByText("Tela de administracao")).toBeInTheDocument();
  });

  it("redireciona para /access-denied quando o papel nao tem a permissao exigida", async () => {
    renderProtected("MEDICO");
    await waitFor(() => expect(screen.getByText("Acesso negado")).toBeInTheDocument());
    expect(screen.queryByText("Tela de administracao")).not.toBeInTheDocument();
  });
});
