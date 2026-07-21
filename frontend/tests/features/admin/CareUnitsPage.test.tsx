import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { CareUnitsPage } from "@/features/admin/CareUnitsPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const EMPTY_PAGE = { items: [], page: 1, page_size: 20, total_items: 0, total_pages: 0 };

describe("CareUnitsPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", "dev-admin");
  });

  it("mostra estado vazio quando nao ha unidades cadastradas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) })) as unknown as typeof fetch,
    );

    renderWithProviders(<CareUnitsPage />);

    expect(await screen.findByText(/nenhuma unidade assistencial cadastrada/i)).toBeInTheDocument();
  });

  it("lista unidades assistenciais existentes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [{ id: "cu-1", name: "UTI Adulto", active: true }],
              page: 1,
              page_size: 50,
              total_items: 1,
              total_pages: 1,
            }),
        }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<CareUnitsPage />);

    expect(await screen.findByText("UTI Adulto")).toBeInTheDocument();
  });

  it("envia os filtros de nome e status como query params", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<CareUnitsPage />);

    const nameInput = await screen.findByLabelText(/nome da unidade/i);
    fireEvent.change(nameInput, { target: { value: "UTI" } });

    const statusSelect = screen.getByLabelText(/^status$/i);
    fireEvent.change(statusSelect, { target: { value: "inactive" } });

    await waitFor(() => {
      const calledWithFilters = fetchMock.mock.calls.some(
        (call) => String(call[0]).includes("search=UTI") && String(call[0]).includes("active=false"),
      );
      expect(calledWithFilters).toBe(true);
    });
  });
});
