import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { AnalysesListPage } from "@/features/analyses/AnalysesListPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const DEV_SUBJECT = "dev-medico";

function stubFetch(analysesResponse: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.toString().includes("/analyses/professionals")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve([{ external_subject: "dev-medico", full_name: "Dra. Ana Medico" }]),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(analysesResponse) });
    }) as unknown as typeof fetch,
  );
}

describe("AnalysesListPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("mostra estado vazio quando nao ha analises", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    stubFetch({ items: [], page: 1, page_size: 10, total_items: 0, total_pages: 0 });

    renderWithProviders(<AnalysesListPage />);

    expect(await screen.findByText(/nenhuma analise registrada/i)).toBeInTheDocument();
  });

  it("nao mostra mais o botao Nova analise (removido do historico)", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    stubFetch({ items: [], page: 1, page_size: 10, total_items: 0, total_pages: 0 });

    renderWithProviders(<AnalysesListPage />);

    await screen.findByText(/nenhuma analise registrada/i);
    expect(screen.queryByRole("link", { name: /nova analise/i })).not.toBeInTheDocument();
  });

  it("lista analises com o estado exibido de forma legivel e o nome do medico", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    stubFetch({
      items: [
        {
          id: "11111111-2222-3333-4444-555555555555",
          patient_id: "p1",
          status: "WAITING_REVIEW",
          additional_text: null,
          structured_clinical_inputs: {},
          created_by: "dev-medico",
          created_by_full_name: "Dra. Ana Medico",
          patient_full_name: "Maria Teste",
          patient_medical_record_number: "MRN-1",
          created_at: "2026-07-11T10:00:00Z",
          updated_at: "2026-07-11T10:00:00Z",
        },
      ],
      page: 1,
      page_size: 10,
      total_items: 1,
      total_pages: 1,
    });

    renderWithProviders(<AnalysesListPage />);

    expect(await screen.findByText(/aguardando revisao/i)).toBeInTheDocument();
    // Aparece tanto na tabela quanto como opcao do filtro "Medico".
    expect(screen.getAllByText("Dra. Ana Medico").length).toBeGreaterThanOrEqual(1);
  });

  it("mostra nome e prontuario do paciente vinculados a cada analise", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    stubFetch({
      items: [
        {
          id: "11111111-2222-3333-4444-555555555555",
          patient_id: "p1",
          status: "WAITING_REVIEW",
          additional_text: null,
          structured_clinical_inputs: {},
          created_by: "dev-medico",
          created_by_full_name: "Dra. Ana Medico",
          patient_full_name: "Maria Teste",
          patient_medical_record_number: "MRN-1",
          created_at: "2026-07-11T10:00:00Z",
          updated_at: "2026-07-11T10:00:00Z",
        },
      ],
      page: 1,
      page_size: 10,
      total_items: 1,
      total_pages: 1,
    });

    renderWithProviders(<AnalysesListPage />);

    const patientLink = await screen.findByRole("link", { name: "Maria Teste" });
    expect(patientLink).toHaveAttribute("href", "/patients/p1");
    expect(screen.getByText("MRN-1")).toBeInTheDocument();
  });

  it("envia os filtros de nome do paciente e prontuario como query params", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    const fetchMock = vi.fn((url: string) => {
      if (url.toString().includes("/analyses/professionals")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ items: [], page: 1, page_size: 10, total_items: 0, total_pages: 0 }),
      });
    }) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<AnalysesListPage />);

    const nameInput = await screen.findByLabelText(/nome do paciente/i);
    fireEvent.change(nameInput, { target: { value: "Maria" } });
    const mrnInput = screen.getByLabelText(/^prontuario$/i);
    fireEvent.change(mrnInput, { target: { value: "MRN-1" } });

    await waitFor(() => {
      const called = fetchMock.mock.calls.some(
        (call) =>
          String(call[0]).includes("patient_name=Maria") &&
          String(call[0]).includes("patient_medical_record_number=MRN-1"),
      );
      expect(called).toBe(true);
    });
  });

  it("filtra pelo patientId recebido na URL (vindo do icone de analise do paciente)", async () => {
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    const fetchMock = vi.fn((url: string) => {
      if (url.toString().includes("/analyses/professionals")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ items: [], page: 1, page_size: 10, total_items: 0, total_pages: 0 }),
      });
    }) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<AnalysesListPage />, ["/analyses?patientId=p1"]);

    await waitFor(() => {
      const called = fetchMock.mock.calls.some((call) =>
        String(call[0]).includes("patient_id=p1"),
      );
      expect(called).toBe(true);
    });
  });

  it("pede configuracao do usuario quando nenhum esta selecionado", async () => {
    renderWithProviders(<AnalysesListPage />);
    await waitFor(() =>
      expect(screen.getByText(/configure o usuario de desenvolvimento/i)).toBeInTheDocument(),
    );
  });
});
