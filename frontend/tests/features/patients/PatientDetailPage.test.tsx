import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { PatientDetailPage } from "@/features/patients/PatientDetailPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const exportElementToPdfMock = vi.fn().mockResolvedValue(undefined);
vi.mock("@/features/patients/patientReportPdf", () => ({
  exportElementToPdf: (...args: unknown[]) => exportElementToPdfMock(...args),
}));

const DEV_SUBJECT = "dev-medico";

const PATIENT = {
  id: "patient-1",
  medical_record_number: "MRN-1",
  full_name: "Paciente Teste",
  birth_date: "1990-01-01",
  age: 36,
  registered_sex: "feminino",
  email: null,
  height_cm: 175,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const OBSERVATIONS = [
  {
    id: "obs-1",
    patient_id: "patient-1",
    observation_type: "SPO2",
    value: { value: 97 },
    unit: "%",
    context: {},
    measured_at: "2026-01-02T10:00:00Z",
    origin: "formulario",
    author: "matricula-1",
    method: null,
    reading_quality: "VALID",
    created_at: "2026-01-02T10:00:00Z",
  },
  {
    id: "obs-2",
    patient_id: "patient-1",
    observation_type: "SPO2",
    value: { value: 95 },
    unit: "%",
    context: {},
    measured_at: "2026-01-02T12:00:00Z",
    origin: "formulario",
    author: "matricula-1",
    method: null,
    reading_quality: "VALID",
    created_at: "2026-01-02T12:00:00Z",
  },
  {
    id: "obs-3",
    patient_id: "patient-1",
    observation_type: "BLOOD_PRESSURE",
    value: { systolic: 120, diastolic: 80 },
    unit: "mmHg",
    context: {},
    measured_at: "2026-01-02T11:00:00Z",
    origin: "formulario",
    author: "matricula-1",
    method: null,
    reading_quality: "VALID",
    created_at: "2026-01-02T11:00:00Z",
  },
  {
    id: "obs-4",
    patient_id: "patient-1",
    observation_type: "WEIGHT",
    value: { value: 70 },
    unit: "kg",
    context: {},
    measured_at: "2026-01-03T09:00:00Z",
    origin: "formulario",
    author: "matricula-1",
    method: null,
    reading_quality: "VALID",
    created_at: "2026-01-03T09:00:00Z",
  },
];

const EMPTY_ALERTS_PAGE = { items: [], page: 1, page_size: 20, total_items: 0, total_pages: 0 };

const PROFESSIONALS = [
  {
    external_subject: "seed-employee-seed-0002",
    full_name: "Amanda Oliveira Rodrigues",
    registration_number: "SEED-0002",
  },
  {
    external_subject: "seed-employee-seed-0014",
    full_name: "Jose Ferreira Dias",
    registration_number: "SEED-0014",
  },
];

function makeSpo2Observations(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    id: `obs-spo2-${index}`,
    patient_id: "patient-1",
    observation_type: "SPO2",
    value: { value: 96 + (index % 3) },
    unit: "%",
    context: {},
    measured_at: `2026-01-0${(index % 9) + 1}T10:00:00Z`,
    origin: "formulario",
    author: "SEED-0002 - Amanda Oliveira Rodrigues",
    method: null,
    reading_quality: "VALID",
    created_at: `2026-01-0${(index % 9) + 1}T10:00:00Z`,
  }));
}

function stubFetchByUrl() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL) => {
      const url = String(input);
      if (url.includes("/observations")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(OBSERVATIONS) });
      }
      if (url.includes("/alerts")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_ALERTS_PAGE) });
      }
      if (url.includes("/analyses/professionals")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(PROFESSIONALS) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(PATIENT) });
    }) as unknown as typeof fetch,
  );
}

describe("PatientDetailPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
    exportElementToPdfMock.mockClear();
  });

  it("agrupa observacoes por tipo em paineis expansiveis, ocultos por padrao", async () => {
    stubFetchByUrl();

    renderWithProviders(
      <Routes>
        <Route path="/patients/:patientId" element={<PatientDetailPage />} />
      </Routes>,
      ["/patients/patient-1"],
    );

    const spo2Toggle = await screen.findByRole("button", { name: /saturacao \(spo2\)/i });
    const bpToggle = screen.getByRole("button", { name: /pressao arterial/i });

    expect(spo2Toggle).toHaveAttribute("aria-expanded", "false");
    expect(bpToggle).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(spo2Toggle);
    expect(spo2Toggle).toHaveAttribute("aria-expanded", "true");

    const panelContent = spo2Toggle.parentElement as HTMLElement;
    expect(within(panelContent).getByText(/2 registros/i)).toBeInTheDocument();
  });

  it("abre um modal com campos dependentes ao registrar uma nova observacao de glicemia", async () => {
    stubFetchByUrl();

    renderWithProviders(
      <Routes>
        <Route path="/patients/:patientId" element={<PatientDetailPage />} />
      </Routes>,
      ["/patients/patient-1"],
    );

    fireEvent.click(await screen.findByRole("button", { name: /registrar observacao/i }));

    const dialog = await screen.findByRole("dialog", { name: /registrar observacao clinica/i });
    fireEvent.change(within(dialog).getByLabelText(/tipo de observacao/i), {
      target: { value: "GLYCEMIA" },
    });

    expect(within(dialog).getByLabelText(/valor \(mg\/dl\)/i)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/momento da medicao/i)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/tipo de paciente/i)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/uso de insulina/i)).toBeInTheDocument();
  });

  it("permite pesquisar e selecionar o funcionario (autor) por nome", async () => {
    stubFetchByUrl();

    renderWithProviders(
      <Routes>
        <Route path="/patients/:patientId" element={<PatientDetailPage />} />
      </Routes>,
      ["/patients/patient-1"],
    );

    fireEvent.click(await screen.findByRole("button", { name: /registrar observacao/i }));
    const dialog = await screen.findByRole("dialog", { name: /registrar observacao clinica/i });

    const employeeField = within(dialog).getByLabelText(/funcionario/i);
    fireEvent.focus(employeeField);
    fireEvent.change(employeeField, { target: { value: "jose" } });

    const option = await within(dialog).findByRole("option", { name: /jose ferreira dias/i });
    expect(within(dialog).queryByText(/amanda oliveira rodrigues/i)).not.toBeInTheDocument();

    fireEvent.mouseDown(option);

    expect(within(dialog).getByText("SEED-0014 - Jose Ferreira Dias")).toBeInTheDocument();
  });

  it("pagina a tabela de cada tipo de observacao de 5 em 5 registros", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL) => {
        const url = String(input);
        if (url.includes("/observations")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(makeSpo2Observations(7)) });
        }
        if (url.includes("/alerts")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_ALERTS_PAGE) });
        }
        if (url.includes("/analyses/professionals")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(PROFESSIONALS) });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve(PATIENT) });
      }) as unknown as typeof fetch,
    );

    renderWithProviders(
      <Routes>
        <Route path="/patients/:patientId" element={<PatientDetailPage />} />
      </Routes>,
      ["/patients/patient-1"],
    );

    const spo2Toggle = await screen.findByRole("button", { name: /saturacao \(spo2\)/i });
    fireEvent.click(spo2Toggle);

    const panelContent = spo2Toggle.parentElement as HTMLElement;
    expect(within(panelContent).getAllByText(/7 registros/i).length).toBeGreaterThan(0);
    expect(within(panelContent).getByText(/pagina 1 de 2/i)).toBeInTheDocument();

    const rowsPage1 = within(panelContent).getAllByText(/SEED-0002 - Amanda Oliveira Rodrigues/i);
    expect(rowsPage1).toHaveLength(5);

    fireEvent.click(within(panelContent).getByRole("button", { name: /proxima/i }));

    expect(within(panelContent).getByText(/pagina 2 de 2/i)).toBeInTheDocument();
    expect(within(panelContent).getAllByText(/SEED-0002 - Amanda Oliveira Rodrigues/i)).toHaveLength(2);
  });

  it("calcula e exibe o IMC a partir da altura do paciente e do peso mais recente", async () => {
    stubFetchByUrl();

    renderWithProviders(
      <Routes>
        <Route path="/patients/:patientId" element={<PatientDetailPage />} />
      </Routes>,
      ["/patients/patient-1"],
    );

    // altura 175cm, peso mais recente 70kg -> IMC = 70 / 1.75^2 = 22.86 -> "22.9"
    expect(await screen.findByText(/175 cm/i)).toBeInTheDocument();
    expect(screen.getByText(/imc: 22\.9 · peso normal/i)).toBeInTheDocument();

    expect(await screen.findByRole("button", { name: /peso/i })).toBeInTheDocument();
  });

  it("permite registrar uma observacao de peso pelo modal", async () => {
    stubFetchByUrl();

    renderWithProviders(
      <Routes>
        <Route path="/patients/:patientId" element={<PatientDetailPage />} />
      </Routes>,
      ["/patients/patient-1"],
    );

    fireEvent.click(await screen.findByRole("button", { name: /registrar observacao/i }));
    const dialog = await screen.findByRole("dialog", { name: /registrar observacao clinica/i });

    fireEvent.change(within(dialog).getByLabelText(/tipo de observacao/i), {
      target: { value: "WEIGHT" },
    });

    expect(within(dialog).getByLabelText(/valor \(kg\)/i)).toBeInTheDocument();
  });

  it("ao clicar em 'Gerar PDF', chama a exportacao com os dados do paciente", async () => {
    stubFetchByUrl();

    renderWithProviders(
      <Routes>
        <Route path="/patients/:patientId" element={<PatientDetailPage />} />
      </Routes>,
      ["/patients/patient-1"],
    );

    const exportButton = await screen.findByRole("button", { name: /gerar pdf/i });
    await act(async () => {
      fireEvent.click(exportButton);
      await vi.waitFor(() => {
        expect(exportElementToPdfMock).toHaveBeenCalledTimes(1);
      });
    });
    const [, meta] = exportElementToPdfMock.mock.calls[0];
    expect(meta).toEqual({
      patientName: "Paciente Teste",
      medicalRecordNumber: "MRN-1",
      ageLabel: "36 anos",
      registeredSex: "feminino",
      heightLabel: "175 cm",
      bmiLabel: "22.9 · Peso normal (Eutrofia)",
    });
  });

  it("durante a geracao do PDF, expande todos os paineis e remove a paginacao das tabelas de observacao", async () => {
    let resolveExport: () => void = () => {};
    exportElementToPdfMock.mockImplementationOnce(
      () => new Promise<void>((resolve) => (resolveExport = resolve)),
    );

    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL) => {
        const url = String(input);
        if (url.includes("/observations")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(makeSpo2Observations(7)) });
        }
        if (url.includes("/alerts")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_ALERTS_PAGE) });
        }
        if (url.includes("/analyses/professionals")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(PROFESSIONALS) });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve(PATIENT) });
      }) as unknown as typeof fetch,
    );

    renderWithProviders(
      <Routes>
        <Route path="/patients/:patientId" element={<PatientDetailPage />} />
      </Routes>,
      ["/patients/patient-1"],
    );

    const spo2Toggle = await screen.findByRole("button", { name: /saturacao \(spo2\)/i });
    expect(spo2Toggle).toHaveAttribute("aria-expanded", "false");

    const exportButton = screen.getByRole("button", { name: /gerar pdf/i });
    fireEvent.click(exportButton);

    await vi.waitFor(() => {
      expect(spo2Toggle).toHaveAttribute("aria-expanded", "true");
    });
    const panelContent = spo2Toggle.parentElement as HTMLElement;
    // Sem paginacao durante a exportacao (`showAllRows`): todos os 7
    // registros aparecem em uma unica tabela, sem controle de "Pagina X de Y".
    expect(within(panelContent).queryByText(/pagina \d+ de \d+/i)).not.toBeInTheDocument();

    await act(async () => {
      resolveExport();
      await vi.waitFor(() => {
        expect(exportElementToPdfMock).toHaveBeenCalledTimes(1);
      });
    });
  });
});
