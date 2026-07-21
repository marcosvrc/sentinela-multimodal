import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "@/app/layouts/AppShell";

function mockFetchForRole(role: string) {
  return vi.fn((url: string) => {
    if (url.toString().includes("/me")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "user-1",
            institution_id: "inst-1",
            external_subject: "dev-x",
            full_name: "Usuario Teste",
            role,
          }),
      });
    }
    if (url.toString().includes("/health")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ status: "ok", service: "API", version: "0.1.0", environment: "test" }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  }) as unknown as typeof fetch;
}

function renderShell() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/patients"]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/patients" element={<div>Conteudo</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppShell - navegacao filtrada por papel", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", "dev-x");
  });

  it("medico ve Pacientes/Historico mas nao Auditoria nem Administracao", async () => {
    vi.stubGlobal("fetch", mockFetchForRole("MEDICO"));
    renderShell();

    await waitFor(() => expect(screen.getByRole("link", { name: /pacientes/i })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /historico/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /auditoria/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /administracao/i })).not.toBeInTheDocument();
  });

  it("auditor ve Auditoria mas nao Pacientes nem Administracao", async () => {
    vi.stubGlobal("fetch", mockFetchForRole("AUDITOR"));
    renderShell();

    await waitFor(() => expect(screen.getByRole("link", { name: /auditoria/i })).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: /pacientes/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /administracao/i })).not.toBeInTheDocument();
  });

  it("administrador tecnico ve Administracao e Auditoria mas nao Pacientes", async () => {
    vi.stubGlobal("fetch", mockFetchForRole("ADMINISTRADOR_TECNICO"));
    renderShell();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /administracao/i })).toBeInTheDocument(),
    );
    // Administrador tecnico tambem acessa auditoria no backend
    // (app/api/routes/audit.py::_require_audit_access), entao o item
    // aparece - so nao ha acesso a pacientes/analises (papeis clinicos).
    expect(screen.getByRole("link", { name: /auditoria/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /pacientes/i })).not.toBeInTheDocument();
  });
});
