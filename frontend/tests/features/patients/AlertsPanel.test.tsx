import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { AlertsPanel } from "@/features/patients/AlertsPanel";
import { renderWithProviders } from "../../utils/renderWithProviders";

const EMPTY_SUMMARY = { critical: 0, high: 0, moderate: 0 };
const EMPTY_PAGE = { items: [], page: 1, page_size: 20, total_items: 0, total_pages: 0 };

const CRITICAL_ALERT = {
  id: "alert-1",
  patient_id: "patient-1",
  observation_id: "obs-1",
  signal_key: "HEART_RATE",
  severity: "CRITICAL",
  status: "OPEN",
  detector_source: "anomaly_detection.self_baseline_v1",
  confidence: 0.9,
  evidence: {},
  expected_action: "Acionar a equipe assistencial imediatamente.",
  detected_at: "2026-01-01T12:00:00Z",
  acknowledged_by: null,
  acknowledged_at: null,
  escalated_to: null,
  escalated_at: null,
  escalation_reason: null,
  resolved_by: null,
  resolved_at: null,
  resolution_notes: null,
  created_at: "2026-01-01T12:00:00Z",
};

function mockFetch(handlers: { summary?: object; alerts?: object }) {
  return vi.fn((url: string) => {
    if (url.includes("/alerts/summary")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(handlers.summary ?? EMPTY_SUMMARY),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(handlers.alerts ?? EMPTY_PAGE),
    });
  }) as unknown as typeof fetch;
}

describe("AlertsPanel", () => {
  it("mostra estado vazio quando nao ha alertas em nenhuma criticidade", async () => {
    vi.stubGlobal("fetch", mockFetch({}));

    renderWithProviders(<AlertsPanel devSubject="dev-medico" patientId="patient-1" />);

    expect(await screen.findByText(/nenhum alerta de anomalia/i)).toBeInTheDocument();
  });

  it("mostra os big numbers por criticidade a partir do resumo", async () => {
    vi.stubGlobal("fetch", mockFetch({ summary: { critical: 1, high: 2, moderate: 0 } }));

    renderWithProviders(<AlertsPanel devSubject="dev-medico" patientId="patient-1" />);

    expect(await screen.findByText("Crítica")).toBeInTheDocument();
    expect(screen.getByText("Alta")).toBeInTheDocument();
    expect(screen.getByText("Moderada")).toBeInTheDocument();
    // "1" (critica) e "2" (alta) aparecem como big numbers.
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2").length).toBeGreaterThan(0);
  });

  it("ao clicar em 'Ver detalhes' de uma criticidade, mostra a tabela paginada filtrada", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        summary: { critical: 1, high: 0, moderate: 0 },
        alerts: { items: [CRITICAL_ALERT], page: 1, page_size: 5, total_items: 1, total_pages: 1 },
      }),
    );

    renderWithProviders(<AlertsPanel devSubject="dev-medico" patientId="patient-1" />);

    const criticalCard = await screen.findByRole("button", { name: /crítica/i });
    fireEvent.click(criticalCard);

    expect(await screen.findByText("HEART_RATE")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reconhecer/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /escalar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /encerrar/i })).toBeInTheDocument();
  });

  it("em printMode, exibe uma tabela unica com todos os alertas, sem paginacao e sem coluna de acoes", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({
        summary: { critical: 1, high: 0, moderate: 0 },
        alerts: { items: [CRITICAL_ALERT], page: 1, page_size: 200, total_items: 1, total_pages: 1 },
      }),
    );

    renderWithProviders(<AlertsPanel devSubject="dev-medico" patientId="patient-1" printMode />);

    expect(await screen.findByText("Todos os alertas registrados")).toBeInTheDocument();
    expect(await screen.findByText("HEART_RATE")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reconhecer/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /escalar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /encerrar/i })).not.toBeInTheDocument();
  });
});
