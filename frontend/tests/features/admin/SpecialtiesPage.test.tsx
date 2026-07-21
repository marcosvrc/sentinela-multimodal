import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { SpecialtiesPage } from "@/features/admin/SpecialtiesPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const EMPTY_PAGE = { items: [], page: 1, page_size: 20, total_items: 0, total_pages: 0 };

describe("SpecialtiesPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", "dev-admin");
  });

  it("mostra estado vazio quando nao ha especialidades cadastradas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) })) as unknown as typeof fetch,
    );

    renderWithProviders(<SpecialtiesPage />);

    expect(await screen.findByText(/nenhuma especialidade cadastrada/i)).toBeInTheDocument();
  });

  it("lista especialidades existentes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [{ id: "sp-1", name: "Cardiologia", active: true, created_at: "2026-01-01T00:00:00Z" }],
              page: 1,
              page_size: 20,
              total_items: 1,
              total_pages: 1,
            }),
        }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<SpecialtiesPage />);

    expect(await screen.findByText("Cardiologia")).toBeInTheDocument();
  });

  it("envia os filtros de nome e status como query params", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<SpecialtiesPage />);

    const nameInput = await screen.findByLabelText(/nome da especialidade/i);
    fireEvent.change(nameInput, { target: { value: "Cardio" } });

    const statusSelect = screen.getByLabelText(/^status$/i);
    fireEvent.change(statusSelect, { target: { value: "active" } });

    await waitFor(() => {
      const calledWithFilters = fetchMock.mock.calls.some(
        (call) => String(call[0]).includes("search=Cardio") && String(call[0]).includes("active=true"),
      );
      expect(calledWithFilters).toBe(true);
    });
  });
});
