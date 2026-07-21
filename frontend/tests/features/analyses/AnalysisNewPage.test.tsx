import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { AnalysisNewPage } from "@/features/analyses/AnalysisNewPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const DEV_SUBJECT = "dev-medico";

const PATIENT = {
  id: "p1",
  medical_record_number: "MRN-1",
  full_name: "Maria Teste",
  birth_date: "1990-01-01",
  age: 36,
  registered_sex: "feminino",
  email: "maria@example.com",
  height_cm: 160,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const WEIGHT_OBSERVATION = {
  id: "obs-weight-1",
  patient_id: "p1",
  observation_type: "WEIGHT",
  value: { value: 64 },
  unit: "kg",
  context: {},
  measured_at: "2026-01-05T09:00:00Z",
  origin: "formulario",
  author: "SEED-0002 - Amanda Oliveira Rodrigues",
  method: null,
  reading_quality: "VALID",
  created_at: "2026-01-05T09:00:00Z",
};

const SPO2_OBSERVATION = {
  id: "obs-spo2-1",
  patient_id: "p1",
  observation_type: "SPO2",
  value: { value: 97 },
  unit: "%",
  context: {},
  measured_at: "2026-01-05T10:00:00Z",
  origin: "formulario",
  author: "SEED-0002 - Amanda Oliveira Rodrigues",
  method: null,
  reading_quality: "VALID",
  created_at: "2026-01-05T10:00:00Z",
};

function stubFetch(observations: unknown[] = []) {
  const fetchMock = vi.fn((url: string) => {
    const href = url.toString();
    if (href.includes("/patients?") || href.endsWith("/patients")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ items: [PATIENT], page: 1, page_size: 10, total_items: 1, total_pages: 1 }),
      });
    }
    if (href.includes("/observations")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(observations) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  }) as unknown as typeof fetch;
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** Etapa 1: busca e seleciona o paciente de teste, depois avanca para a
 * etapa 2 (dados clinicos). Repetido no inicio da maioria dos testes. */
async function selectPatientAndGoToClinicalDataStep() {
  const searchInput = await screen.findByLabelText(/^paciente/i);
  fireEvent.change(searchInput, { target: { value: "maria" } });

  const resultButton = await screen.findByRole("option", { name: /maria teste/i });
  fireEvent.click(resultButton);

  const advanceButton = await screen.findByRole("button", { name: /avançar/i });
  fireEvent.click(advanceButton);
}

/** Etapas 1 e 2 (dados clinicos, sem marcar nenhum), avancando para a
 * etapa 3 (modalidades). */
async function goToModalitiesStep() {
  await selectPatientAndGoToClinicalDataStep();
  const advanceButton = await screen.findByRole("button", { name: /avançar/i });
  fireEvent.click(advanceButton);
}

describe("AnalysisNewPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
  });

  it("etapa 1: busca paciente por nome/prontuario e exibe resultados", async () => {
    stubFetch();
    renderWithProviders(<AnalysisNewPage />, ["/analyses/new"]);

    const searchInput = await screen.findByLabelText(/^paciente/i);
    fireEvent.change(searchInput, { target: { value: "maria" } });

    expect(await screen.findByText("Maria Teste")).toBeInTheDocument();
  });

  it("etapa 1: ao selecionar o paciente, mostra o painel de dados pessoais e habilita avancar", async () => {
    stubFetch();
    renderWithProviders(<AnalysisNewPage />, ["/analyses/new"]);

    const searchInput = await screen.findByLabelText(/^paciente/i);
    fireEvent.change(searchInput, { target: { value: "maria" } });

    const resultButton = await screen.findByRole("option", { name: /maria teste/i });
    fireEvent.click(resultButton);

    await waitFor(() => expect(screen.getByText(/dados pessoais/i)).toBeInTheDocument());
    expect(screen.getByText("MRN-1")).toBeInTheDocument();
    expect(screen.getByText("36 anos")).toBeInTheDocument();

    const advanceButton = screen.getByRole("button", { name: /avançar/i });
    expect(advanceButton).not.toBeDisabled();
  });

  it("etapa 1: exibe altura e IMC calculado com o peso mais recente", async () => {
    stubFetch([WEIGHT_OBSERVATION]);
    renderWithProviders(<AnalysisNewPage />, ["/analyses/new"]);

    const searchInput = await screen.findByLabelText(/^paciente/i);
    fireEvent.change(searchInput, { target: { value: "maria" } });

    const resultButton = await screen.findByRole("option", { name: /maria teste/i });
    fireEvent.click(resultButton);

    // altura 160cm, peso 64kg -> IMC = 64 / 1.6^2 = 25.0
    expect(await screen.findByText(/160 cm/i)).toBeInTheDocument();
    expect(await screen.findByText(/25\.0 \(/i)).toBeInTheDocument();
  });

  it("etapa 2: mostra o checkbox de IMC quando ha altura cadastrada e peso registrado, e envia bmi_kg_m2 na criacao", async () => {
    const fetchMock = stubFetch([WEIGHT_OBSERVATION]);
    renderWithProviders(<AnalysisNewPage />, ["/analyses/new"]);
    await selectPatientAndGoToClinicalDataStep();

    // altura 160cm, peso 64kg -> IMC = 25.0 (Peso normal)
    const bmiCheckbox = await screen.findByRole("checkbox", { name: /índice de massa corporal/i });
    expect(bmiCheckbox).not.toBeDisabled();
    fireEvent.click(bmiCheckbox);

    expect(await screen.findByText(/25\.0 kg\/m² · Peso normal/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /avançar/i }));
    fireEvent.click(await screen.findByRole("checkbox", { name: /^imagem$/i }));
    fireEvent.click(screen.getByRole("button", { name: /avançar/i }));

    expect(await screen.findByText(/dados clínicos selecionados/i)).toBeInTheDocument();
    expect(screen.getByText(/índice de massa corporal \(imc\): 25\.0 kg\/m² · peso normal/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /realizar análise/i }));

    await waitFor(() => {
      const createCall = fetchMock.mock.calls.find(
        (call) =>
          typeof call[0] === "string" &&
          call[0].endsWith("/analyses") &&
          (call[1] as { method?: string })?.method === "POST",
      );
      expect(createCall).toBeTruthy();
    });
    const createCall = fetchMock.mock.calls.find(
      (call) =>
        typeof call[0] === "string" &&
        call[0].endsWith("/analyses") &&
        (call[1] as { method?: string })?.method === "POST",
    );
    const body = JSON.parse((createCall![1] as { body: string }).body);
    expect(body.structured_clinical_inputs).toEqual({ bmi: { bmi_kg_m2: 25.0 } });
  });

  it("etapa 2: mostra as observacoes registradas em uma linha de checkboxes, sem bloquear avanco", async () => {
    stubFetch([SPO2_OBSERVATION]);
    renderWithProviders(<AnalysisNewPage />, ["/analyses/new"]);
    await selectPatientAndGoToClinicalDataStep();

    expect(await screen.findByRole("checkbox", { name: /saturacao \(spo2\)/i })).toBeInTheDocument();
    // Nenhum painel de historico aberto ate o checkbox correspondente ser marcado.
    expect(screen.queryByText(/medido em/i)).not.toBeInTheDocument();

    // Dados clinicos sao opcionais - o avanco nunca fica bloqueado aqui.
    const advanceButton = screen.getByRole("button", { name: /avançar/i });
    expect(advanceButton).not.toBeDisabled();
  });

  it("etapa 2: marcar um tipo abre o painel expansivel com a tabela de historico", async () => {
    stubFetch([SPO2_OBSERVATION]);
    renderWithProviders(<AnalysisNewPage />, ["/analyses/new"]);
    await selectPatientAndGoToClinicalDataStep();

    const spo2Checkbox = await screen.findByRole("checkbox", { name: /saturacao \(spo2\)/i });
    fireEvent.click(spo2Checkbox);

    expect(await screen.findByText(/97 %/i)).toBeInTheDocument();
  });

  it("etapa 3: nao avanca para o consolidado sem selecionar modalidade nem dado clinico", async () => {
    stubFetch();
    renderWithProviders(<AnalysisNewPage />, ["/analyses/new"]);
    await goToModalitiesStep();

    expect(await screen.findByText(/^modalidade$/i)).toBeInTheDocument();
    const advanceToReview = screen.getByRole("button", { name: /avançar/i });
    expect(advanceToReview).toBeDisabled();
  });

  it("etapa 3: avanca para o consolidado com apenas um dado clinico selecionado, sem modalidade", async () => {
    stubFetch([SPO2_OBSERVATION]);
    renderWithProviders(<AnalysisNewPage />, ["/analyses/new"]);
    await selectPatientAndGoToClinicalDataStep();

    const spo2Checkbox = await screen.findByRole("checkbox", { name: /saturacao \(spo2\)/i });
    fireEvent.click(spo2Checkbox);
    fireEvent.click(screen.getByRole("button", { name: /avançar/i }));

    expect(await screen.findByText(/^modalidade$/i)).toBeInTheDocument();
    const advanceToReview = screen.getByRole("button", { name: /avançar/i });
    expect(advanceToReview).not.toBeDisabled();
  });

  it("etapa 2 -> 4: dados clinicos selecionados aparecem no consolidado e sao enviados na criacao da analise", async () => {
    const fetchMock = stubFetch([SPO2_OBSERVATION]);
    renderWithProviders(<AnalysisNewPage />, ["/analyses/new"]);
    await selectPatientAndGoToClinicalDataStep();

    const spo2Checkbox = await screen.findByRole("checkbox", { name: /saturacao \(spo2\)/i });
    fireEvent.click(spo2Checkbox);
    fireEvent.click(screen.getByRole("button", { name: /avançar/i }));

    // Etapa 3 (modalidades): seleciona Imagem so para poder avancar.
    fireEvent.click(await screen.findByRole("checkbox", { name: /^imagem$/i }));
    fireEvent.click(screen.getByRole("button", { name: /avançar/i }));

    expect(await screen.findByText(/dados clínicos selecionados/i)).toBeInTheDocument();
    expect(screen.getByText(/saturacao \(spo2\): 97 %/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /realizar análise/i }));

    await waitFor(() => {
      const createCall = fetchMock.mock.calls.find(
        (call) =>
          typeof call[0] === "string" &&
          call[0].endsWith("/analyses") &&
          (call[1] as { method?: string })?.method === "POST",
      );
      expect(createCall).toBeTruthy();
    });
    const createCall = fetchMock.mock.calls.find(
      (call) =>
        typeof call[0] === "string" &&
        call[0].endsWith("/analyses") &&
        (call[1] as { method?: string })?.method === "POST",
    );
    const body = JSON.parse((createCall![1] as { body: string }).body);
    expect(body.structured_clinical_inputs).toEqual({ spo2: { spo2_percent: 97 } });
  });

  it("etapa 3: permite selecionar mais de um arquivo para a mesma modalidade e remover individualmente", async () => {
    stubFetch();
    renderWithProviders(<AnalysisNewPage />, ["/analyses/new"]);
    await goToModalitiesStep();

    fireEvent.click(screen.getByRole("checkbox", { name: /^imagem$/i }));

    const imageInput = await screen.findByLabelText(/imagem \(pode selecionar/i);
    expect(imageInput).toHaveAttribute("multiple");

    const fileA = new File(["a"], "foto-a.png", { type: "image/png" });
    const fileB = new File(["b"], "foto-b.png", { type: "image/png" });

    fireEvent.change(imageInput, { target: { files: [fileA, fileB] } });

    expect(await screen.findByText("foto-a.png")).toBeInTheDocument();
    expect(screen.getByText("foto-b.png")).toBeInTheDocument();

    // Selecionar mais um arquivo depois ACUMULA em vez de substituir.
    const fileC = new File(["c"], "foto-c.png", { type: "image/png" });
    fireEvent.change(imageInput, { target: { files: [fileC] } });
    expect(screen.getByText("foto-a.png")).toBeInTheDocument();
    expect(screen.getByText("foto-b.png")).toBeInTheDocument();
    expect(screen.getByText("foto-c.png")).toBeInTheDocument();

    // Remove so o arquivo do meio.
    fireEvent.click(screen.getByRole("button", { name: /remover foto-b.png/i }));
    expect(screen.queryByText("foto-b.png")).not.toBeInTheDocument();
    expect(screen.getByText("foto-a.png")).toBeInTheDocument();
    expect(screen.getByText("foto-c.png")).toBeInTheDocument();
  });
});
