import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { EmployeesPage } from "@/features/admin/EmployeesPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const EMPTY_PAGE = { items: [], page: 1, page_size: 20, total_items: 0, total_pages: 0 };

function stubFetchForRoleFlow() {
  return vi.fn((url: string) => {
    const href = url.toString();
    if (href.includes("/employees/available-roles")) {
      const professionalType = new URL(href).searchParams.get("professional_type");
      const roles =
        professionalType === "ENFERMEIRO"
          ? ["ENFERMEIRO"]
          : ["MEDICO", "ADMINISTRADOR_TECNICO", "ADMINISTRADOR_CLINICO", "AUDITOR"];
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ professional_type: professionalType, roles }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) });
  }) as unknown as typeof fetch;
}

describe("EmployeesPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", "dev-admin");
  });

  it("mostra estado vazio quando nao ha funcionarios cadastrados", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) })) as unknown as typeof fetch,
    );

    renderWithProviders(<EmployeesPage />);

    expect(await screen.findByText(/nenhum funcionário cadastrado/i)).toBeInTheDocument();
  });

  it("usa o titulo Funcionário (sem o parenteses medico)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) })) as unknown as typeof fetch,
    );

    renderWithProviders(<EmployeesPage />);

    expect(await screen.findByRole("heading", { name: "Funcionário" })).toBeInTheDocument();
  });

  it("filtra por nome, matricula e status via campos dedicados", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<EmployeesPage />);

    const nameInput = await screen.findByLabelText(/^nome$/i);
    fireEvent.change(nameInput, { target: { value: "Ana" } });

    await waitFor(() => {
      const calledWithSearch = fetchMock.mock.calls.some((call) =>
        String(call[0]).includes("search=Ana"),
      );
      expect(calledWithSearch).toBe(true);
    });

    expect(screen.getByLabelText(/matricula/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^status$/i)).toBeInTheDocument();
  });

  it("restringe as opcoes de papel de acesso ao escolher o tipo profissional Enfermeiro", async () => {
    vi.stubGlobal("fetch", stubFetchForRoleFlow());

    renderWithProviders(<EmployeesPage />);

    const newEmployeeButton = await screen.findByRole("button", { name: /novo funcionário/i });
    fireEvent.click(newEmployeeButton);

    const professionalTypeSelect = await screen.findByLabelText(/tipo profissional/i);
    fireEvent.change(professionalTypeSelect, { target: { value: "ENFERMEIRO" } });

    await waitFor(() => {
      const roleSelect = screen.getByLabelText(/papel de acesso/i) as HTMLSelectElement;
      const optionValues = Array.from(roleSelect.options).map((option) => option.value);
      expect(optionValues).toEqual(["ENFERMEIRO"]);
    });
  });

  it("permite papel administrativo quando o tipo profissional e Medico", async () => {
    vi.stubGlobal("fetch", stubFetchForRoleFlow());

    renderWithProviders(<EmployeesPage />);

    const newEmployeeButton = await screen.findByRole("button", { name: /novo funcionário/i });
    fireEvent.click(newEmployeeButton);

    await waitFor(() => {
      const roleSelect = screen.getByLabelText(/papel de acesso/i) as HTMLSelectElement;
      const optionValues = Array.from(roleSelect.options).map((option) => option.value);
      expect(optionValues).toContain("ADMINISTRADOR_CLINICO");
      expect(optionValues).toContain("AUDITOR");
    });
  });
});
