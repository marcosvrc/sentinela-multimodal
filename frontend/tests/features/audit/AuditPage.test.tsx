import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { AuditPage } from "@/features/audit/AuditPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const DEV_SUBJECT = "dev-auditor";

describe("AuditPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("mostra estado vazio quando nao ha eventos", async () => {
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

    renderWithProviders(<AuditPage />);

    expect(await screen.findByText(/nenhum evento encontrado/i)).toBeInTheDocument();
  });

  it("lista eventos de auditoria retornados pela API", async () => {
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
                  id: "e1",
                  sequence: 1,
                  occurred_at: "2026-07-11T10:00:00Z",
                  actor: "dev-medico",
                  actor_role: "MEDICO",
                  unit: null,
                  category: "ANALYSIS",
                  action: "ANALYSIS_CREATE",
                  resource_type: "analysis",
                  resource_id: "a1",
                  result: "SUCCESS",
                  justification: null,
                  request_id: null,
                  analysis_id: "a1",
                  workflow_id: null,
                  job_id: null,
                  event_metadata: { modalities: ["TEXT"] },
                  event_hash: "hash-1",
                  prev_hash: null,
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

    renderWithProviders(<AuditPage />);

    expect(await screen.findByText("ANALYSIS_CREATE")).toBeInTheDocument();
  });

  it("abre o popup de detalhes com o JSON completo do evento ao clicar no icone", async () => {
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
                  id: "e1",
                  sequence: 42,
                  occurred_at: "2026-07-11T10:00:00Z",
                  actor: "dev-medico",
                  actor_role: "MEDICO",
                  unit: null,
                  category: "ANALYSIS",
                  action: "ANALYSIS_CREATE",
                  resource_type: "analysis",
                  resource_id: "a1",
                  result: "SUCCESS",
                  justification: null,
                  request_id: null,
                  analysis_id: "a1",
                  workflow_id: null,
                  job_id: null,
                  event_metadata: { modalities: ["TEXT", "IMAGE"], patient_id: "p1" },
                  event_hash: "abc123hash",
                  prev_hash: "prevhash999",
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

    renderWithProviders(<AuditPage />);

    const detailsButton = await screen.findByRole("button", {
      name: /ver detalhes completos em json do evento 42/i,
    });
    fireEvent.click(detailsButton);

    expect(await screen.findByText(/detalhes do evento #42/i)).toBeInTheDocument();
    expect(screen.getByText(/abc123hash/)).toBeInTheDocument();
    expect(screen.getByText(/prevhash999/)).toBeInTheDocument();
    expect(screen.getByText(/"patient_id": "p1"/)).toBeInTheDocument();
  });

  it("pede configuracao do usuario quando nenhum esta selecionado", async () => {
    renderWithProviders(<AuditPage />);
    await waitFor(() =>
      expect(screen.getByText(/configure o usuario de desenvolvimento/i)).toBeInTheDocument(),
    );
  });
});
