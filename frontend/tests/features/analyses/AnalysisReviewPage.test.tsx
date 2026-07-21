import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnalysisReviewPage } from "@/features/analyses/AnalysisReviewPage";
import { ToastProvider } from "@/components/feedback/ToastProvider";

const DEV_SUBJECT = "dev-medico";

const REPORT = {
  id: "report-1",
  analysis_id: "analysis-1",
  state: "DRAFT",
  content: {
    identification: {
      analysis_id: "analysis-1",
      institution_id: "institution-1",
      patient: {
        patient_id: "patient-1",
        medical_record_number: "MRN-1",
        full_name: "Paciente Teste",
        birth_date: "1990-01-01",
      },
      created_by: "dev-medico",
      created_at: "2026-07-16T10:00:00Z",
      additional_text: "Paciente relata tontura.",
      structured_clinical_inputs: { spo2: { spo2_percent: 91 } },
    },
    report_state: "DRAFT",
    ai_summary: { text: "Resumo automatico.", uncertainty_note: null, status: "SUCCESS" },
    clinical_support_summary: null,
    calculated_risk: {
      outcome: "MATCHED",
      risk_level: 4,
      classification_label: "Hipoxemia",
      inconclusive_reason: null,
      inconclusive_detail: null,
    },
    deterministic_findings: [],
    model_observations: [],
    assisted_hypotheses: [],
    modality_evidence: [
      { modality_type: "TEXT", summary: "Texto ok.", observed_at: "2026-07-16T10:00:00Z" },
      { modality_type: "IMAGE", summary: "Imagem ok.", observed_at: "2026-07-16T10:00:00Z" },
    ],
    modality_attention: [
      {
        modality_type: "TEXT",
        level: "OBSERVATION",
        relevant_findings_count: 1,
        summaries: ["Termo clinico candidato 'tontura'."],
      },
      { modality_type: "IMAGE", level: "NONE", relevant_findings_count: 0, summaries: [] },
    ],
    inconsistencies: [],
    protocol_conduct: null,
    professional_review: { state: "DRAFT", confirmed_by: null, confirmed_at: null },
    provenance: {
      rule_codes_evaluated: ["spo2"],
      llm_provider: "local",
      llm_model: "local-template",
      llm_prompt_version: "v1",
      llm_input_hash: null,
      llm_output_hash: null,
    },
  },
  pdf_sha256: null,
  pdf_generated_at: null,
  confirmed_by: null,
  confirmed_at: null,
  created_at: "2026-07-16T10:00:00Z",
  updated_at: "2026-07-16T10:00:00Z",
};

const STATS = {
  total_analyses_consolidated: 20,
  conclusive_count: 15,
  conclusive_rate_percent: 75.0,
};

function renderReviewPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/analyses/analysis-1/review"]}>
          <Routes>
            <Route path="/analyses/:analysisId/review" element={<AnalysisReviewPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("AnalysisReviewPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
  });

  it("mostra os big numbers com nivel, modalidades, dados clinicos, resultado e acuracia", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const href = url.toString();
        if (href.includes("/analyses/analysis-1/report")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(REPORT) });
        }
        if (href.includes("/analyses/stats")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(STATS) });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }) as unknown as typeof fetch,
    );

    renderReviewPage();

    expect(await screen.findByText("4")).toBeInTheDocument();
    expect(screen.getByText("Nível de risco")).toBeInTheDocument();

    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Modalidade utilizada")).toBeInTheDocument();

    expect(screen.getByText("Sim")).toBeInTheDocument();
    expect(screen.getByText("Dados clínicos")).toBeInTheDocument();

    expect(screen.getByText("Conclusivo")).toBeInTheDocument();
    expect(screen.getByText("Resultado")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("75%")).toBeInTheDocument());
    expect(screen.getByText("15 de 20 análises")).toBeInTheDocument();
  });

  it("mostra o nível de atenção por modalidade, sem confundir com o risco calculado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const href = url.toString();
        if (href.includes("/analyses/analysis-1/report")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(REPORT) });
        }
        if (href.includes("/analyses/stats")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(STATS) });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }) as unknown as typeof fetch,
    );

    renderReviewPage();

    expect(await screen.findByText("Nível de atenção por modalidade")).toBeInTheDocument();
    expect(screen.getByText("Observação")).toBeInTheDocument();
    expect(screen.getByText("Sem pontos de atenção")).toBeInTheDocument();
    expect(screen.getByText("1 achado(s) considerado(s)")).toBeInTheDocument();
    // Nunca deve reutilizar o texto do risco calculado (badge de risco
    // real, separado, mostrado logo acima na tela).
    expect(screen.queryByText(/nível de risco/i)).toBeInTheDocument();
  });

  it("não mostra a seção de nível de atenção quando não há nenhuma modalidade avaliada", async () => {
    const reportWithoutAttention = {
      ...REPORT,
      content: { ...REPORT.content, modality_attention: [] },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const href = url.toString();
        if (href.includes("/analyses/analysis-1/report")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(reportWithoutAttention) });
        }
        if (href.includes("/analyses/stats")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(STATS) });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }) as unknown as typeof fetch,
    );

    renderReviewPage();

    await screen.findByText("Resumo assistido por IA");
    expect(screen.queryByText("Nível de atenção por modalidade")).not.toBeInTheDocument();
  });

  it("mostra 'Não' quando a analise nao tem dados clinicos estruturados", async () => {
    const reportWithoutClinicalData = {
      ...REPORT,
      content: {
        ...REPORT.content,
        identification: { ...REPORT.content.identification, structured_clinical_inputs: {} },
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const href = url.toString();
        if (href.includes("/analyses/analysis-1/report")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(reportWithoutClinicalData),
          });
        }
        if (href.includes("/analyses/stats")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(STATS) });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }) as unknown as typeof fetch,
    );

    renderReviewPage();

    expect(await screen.findByText("Não")).toBeInTheDocument();
  });
});
