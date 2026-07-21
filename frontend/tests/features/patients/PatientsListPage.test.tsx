import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { PatientsListPage } from "@/features/patients/PatientsListPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const DEV_SUBJECT = "dev-medico";

describe("PatientsListPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("mostra estado vazio quando nao ha pacientes", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({ items: [], page: 1, page_size: 20, total_items: 0, total_pages: 0 }),
        }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<PatientsListPage />);

    expect(await screen.findByText(/nenhum paciente cadastrado/i)).toBeInTheDocument();
  });

  it("lista pacientes retornados pela API", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [
                {
                  id: "p1",
                  medical_record_number: "MRN-1",
                  full_name: "Maria Teste",
                  birth_date: "1990-01-01",
                  age: 36,
                  registered_sex: "feminino",
                  email: null,
                  height_cm: null,
                  active: true,
                  has_analyses: false,
                  created_at: "2026-01-01T00:00:00Z",
                  updated_at: "2026-01-01T00:00:00Z",
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

    renderWithProviders(<PatientsListPage />);

    expect(await screen.findByText("Maria Teste")).toBeInTheDocument();
    expect(screen.getByText("MRN-1")).toBeInTheDocument();
  });

  it("exibe o icone de analise apenas quando o paciente tem has_analyses=true", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [
                {
                  id: "p1",
                  medical_record_number: "MRN-1",
                  full_name: "Maria Teste",
                  birth_date: "1990-01-01",
                  age: 36,
                  registered_sex: "feminino",
                  email: null,
                  height_cm: null,
                  active: true,
                  has_analyses: true,
                  created_at: "2026-01-01T00:00:00Z",
                  updated_at: "2026-01-01T00:00:00Z",
                },
                {
                  id: "p2",
                  medical_record_number: "MRN-2",
                  full_name: "Joao Sem Analise",
                  birth_date: "1985-01-01",
                  age: 41,
                  registered_sex: "masculino",
                  email: null,
                  height_cm: null,
                  active: true,
                  has_analyses: false,
                  created_at: "2026-01-01T00:00:00Z",
                  updated_at: "2026-01-01T00:00:00Z",
                },
              ],
              page: 1,
              page_size: 20,
              total_items: 2,
              total_pages: 1,
            }),
        }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<PatientsListPage />);

    const analysisLink = await screen.findByRole("link", {
      name: /ver historico de analises de maria teste/i,
    });
    expect(analysisLink).toHaveAttribute("href", "/analyses?patientId=p1");

    expect(
      screen.queryByRole("link", { name: /ver historico de analises de joao sem analise/i }),
    ).not.toBeInTheDocument();
  });

  it("envia o filtro 'Analise' (com/sem) como query param has_analyses", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ items: [], page: 1, page_size: 5, total_items: 0, total_pages: 0 }),
      }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<PatientsListPage />);

    const filterSelect = await screen.findByLabelText(/^analise$/i);
    fireEvent.change(filterSelect, { target: { value: "yes" } });

    await waitFor(() => {
      const called = fetchMock.mock.calls.some((call) =>
        String(call[0]).includes("has_analyses=true"),
      );
      expect(called).toBe(true);
    });

    fireEvent.change(filterSelect, { target: { value: "no" } });

    await waitFor(() => {
      const called = fetchMock.mock.calls.some((call) =>
        String(call[0]).includes("has_analyses=false"),
      );
      expect(called).toBe(true);
    });
  });

  it("exibe acoes de editar e excluir, e permite desativar um paciente", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    const patient = {
      id: "p1",
      medical_record_number: "MRN-1",
      full_name: "Maria Teste",
      birth_date: "1990-01-01",
      age: 36,
      registered_sex: "feminino",
      email: null,
      height_cm: null,
      active: true,
      has_analyses: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const patchCalls: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, options?: { method?: string; body?: string }) => {
        if (options?.method === "PATCH") {
          patchCalls.push(JSON.parse(options.body ?? "{}"));
          return Promise.resolve({ ok: true, json: () => Promise.resolve({ ...patient, active: false }) });
        }
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({ items: [patient], page: 1, page_size: 20, total_items: 1, total_pages: 1 }),
        });
      }) as unknown as typeof fetch,
    );

    renderWithProviders(<PatientsListPage />);

    expect(await screen.findByRole("link", { name: /editar/i })).toHaveAttribute(
      "href",
      "/patients/p1/edit",
    );

    fireEvent.click(screen.getByRole("button", { name: /excluir/i }));
    const dialog = await screen.findByRole("dialog", { name: /excluir paciente/i });
    fireEvent.click(within(dialog).getByRole("button", { name: /excluir/i }));

    await waitFor(() => expect(patchCalls).toEqual([{ active: false }]));
  });

  it("pede configuracao do usuario quando nenhum esta selecionado", async () => {
    renderWithProviders(<PatientsListPage />);
    await waitFor(() =>
      expect(screen.getByText(/configure o usuario de desenvolvimento/i)).toBeInTheDocument(),
    );
  });

  it("envia o termo de busca (com debounce) como query param search", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ items: [], page: 1, page_size: 10, total_items: 0, total_pages: 0 }),
      }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<PatientsListPage />);

    const searchInput = await screen.findByLabelText(/buscar por nome ou prontuario/i);
    fireEvent.change(searchInput, { target: { value: "maria" } });

    await waitFor(
      () => {
        const calledWithSearch = fetchMock.mock.calls.some((call) =>
          String(call[0]).includes("search=maria"),
        );
        expect(calledWithSearch).toBe(true);
      },
      { timeout: 2000 },
    );
  });
});
