import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { ClinicalSupportPanel } from "@/features/patients/ClinicalSupportPanel";
import { renderWithProviders } from "../../utils/renderWithProviders";

const SUMMARY_RESPONSE = {
  summary_text: "Paciente com 68 anos (masculino). Dados clinicos disponiveis: SPO2.",
  probable_causes: "Alertas de anomalia registrados: SPO2 (HIGH, status OPEN).",
  suggested_next_steps: "Revisar a serie temporal completa de cada sinal.",
  uncertainty_note:
    "Este e um apoio a analise clinica gerado automaticamente - nao substitui a avaliacao do profissional responsavel.",
  provider: "local",
  model: "local-template",
  prompt_version: "local-clinical-support-template-v1",
  generated_at: "2026-01-01T12:00:00Z",
  observations_considered: 1,
  alerts_considered: 1,
};

describe("ClinicalSupportPanel", () => {
  it("nao chama a API antes do clique no botao", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderWithProviders(<ClinicalSupportPanel devSubject="dev-medico" patientId="patient-1" />);

    expect(screen.getByRole("button", { name: /analisar dados clinicos/i })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("ao clicar no botao, exibe o sumario com visao clinica, causas provaveis, direcionamento e aviso", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(SUMMARY_RESPONSE) }),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderWithProviders(<ClinicalSupportPanel devSubject="dev-medico" patientId="patient-1" />);

    fireEvent.click(screen.getByRole("button", { name: /analisar dados clinicos/i }));

    expect(await screen.findByText(SUMMARY_RESPONSE.summary_text)).toBeInTheDocument();
    expect(screen.getByText(SUMMARY_RESPONSE.probable_causes)).toBeInTheDocument();
    expect(screen.getByText(SUMMARY_RESPONSE.suggested_next_steps)).toBeInTheDocument();
    expect(screen.getByText(SUMMARY_RESPONSE.uncertainty_note)).toBeInTheDocument();

    const call = fetchMock.mock.calls[0];
    expect(String(call[0])).toContain("/patients/patient-1/clinical-support-summary");
    expect((call[1] as { method?: string }).method).toBe("POST");
  });

  it("mostra estado de erro com opcao de tentar novamente quando a chamada falha", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 502,
          json: () =>
            Promise.resolve({
              code: "CLINICAL_SUPPORT_SUMMARY_UNAVAILABLE",
              message: "Nao foi possivel gerar o apoio a analise clinica agora.",
              field_errors: {},
              request_id: null,
            }),
        }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<ClinicalSupportPanel devSubject="dev-medico" patientId="patient-1" />);

    fireEvent.click(screen.getByRole("button", { name: /analisar dados clinicos/i }));

    expect(await screen.findByRole("button", { name: /tentar novamente/i })).toBeInTheDocument();
  });
});
