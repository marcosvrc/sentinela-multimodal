import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { UsersPage } from "@/features/admin/UsersPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const EMPTY_PAGE = { items: [], page: 1, page_size: 20, total_items: 0, total_pages: 0 };

describe("UsersPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", "dev-admin");
  });

  it("mostra estado vazio quando nao ha usuarios cadastrados", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) })) as unknown as typeof fetch,
    );

    renderWithProviders(<UsersPage />);

    expect(await screen.findByText(/nenhum usuario cadastrado/i)).toBeInTheDocument();
  });

  it("lista usuarios e mostra acoes de excluir/editar papel/revogar sessoes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [
                {
                  id: "user-1",
                  external_subject: "cognito-sub-123",
                  full_name: "Dra. Ana Souza",
                  role: "MEDICO",
                  active: true,
                  created_at: "2026-01-01T00:00:00Z",
                },
              ],
              page: 1,
              page_size: 20,
              total_items: 1,
              total_pages: 1,
            }),
        }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<UsersPage />);

    expect(await screen.findByText("cognito-sub-123")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /editar papel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /excluir/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /revogar sessoes/i })).toBeInTheDocument();
  });

  it("nao exibe mais coluna de nome nem acao de cadastro (criacao passou para Funcionario)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [
                {
                  id: "user-1",
                  external_subject: "cognito-sub-123",
                  role: "MEDICO",
                  active: true,
                  created_at: "2026-01-01T00:00:00Z",
                },
              ],
              page: 1,
              page_size: 20,
              total_items: 1,
              total_pages: 1,
            }),
        }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<UsersPage />);

    await screen.findByText("cognito-sub-123");
    expect(screen.queryByRole("button", { name: /novo usuario/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/^nome$/i)).not.toBeInTheDocument();
  });

  it("envia os filtros de identificador, papel e status como query params", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<UsersPage />);

    const searchInput = await screen.findByLabelText(/identificador externo/i);
    fireEvent.change(searchInput, { target: { value: "dev-medico" } });

    const roleSelect = screen.getByLabelText(/^papel$/i);
    fireEvent.change(roleSelect, { target: { value: "MEDICO" } });

    const statusSelect = screen.getByLabelText(/^status$/i);
    fireEvent.change(statusSelect, { target: { value: "active" } });

    await waitFor(() => {
      const calledWithFilters = fetchMock.mock.calls.some(
        (call) =>
          String(call[0]).includes("search=dev-medico") &&
          String(call[0]).includes("role=MEDICO") &&
          String(call[0]).includes("active=true"),
      );
      expect(calledWithFilters).toBe(true);
    });
  });
});
