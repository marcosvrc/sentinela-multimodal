import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { ClinicalRuleSetsPage } from "@/features/admin/ClinicalRuleSetsPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const EMPTY_PAGE = { items: [], page: 1, page_size: 20, total_items: 0, total_pages: 0 };

const RULE_SET_SUMMARY = {
  id: "rs-1",
  code: "spo2",
  version: "0.1.0",
  population: "adult",
  status: "draft",
  effective_from: "2026-01-01",
  effective_to: null,
  created_at: "2026-01-01T00:00:00Z",
};

const RULE_SET_DETAIL = {
  ...RULE_SET_SUMMARY,
  required_inputs: ["spo2_percent", "oxygen_in_use"],
  exclusions: ["insuficiencia respiratoria hipercapnica confirmada"],
  content_hash: "abc123",
  approvals: [
    {
      id: "approval-1",
      approver: "dev-admin-clinico",
      decision: "published",
      justification: "Publicacao inicial",
      decided_at: "2026-01-02T00:00:00Z",
    },
  ],
  rules: [
    {
      id: "rule-1",
      rule_key: "normal",
      when: "spo2_percent >= 96",
      risk_level: 1,
      classification_label: "Normal",
      notes: null,
      position: 0,
    },
  ],
  actions: [{ id: "action-1", risk_level: 1, description: "Rotina." }],
};

describe("ClinicalRuleSetsPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", "dev-admin");
  });

  it("mostra estado vazio quando nao ha conjuntos de regras", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(EMPTY_PAGE) })) as unknown as typeof fetch,
    );

    renderWithProviders(<ClinicalRuleSetsPage />);

    expect(await screen.findByText(/nenhum conjunto de regras carregado/i)).toBeInTheDocument();
  });

  it("lista conjuntos de regras e mostra acoes de ver detalhes e publicar para status draft", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [RULE_SET_SUMMARY],
              page: 1,
              page_size: 20,
              total_items: 1,
              total_pages: 1,
            }),
        }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<ClinicalRuleSetsPage />);

    expect(await screen.findByText("Saturação de oxigênio (SpO₂)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ver detalhes/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /publicar/i })).toBeInTheDocument();
  });

  it("abre o modal de detalhes com entradas obrigatorias, exclusoes e historico de aprovacoes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/clinical-rule-sets/rs-1")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(RULE_SET_DETAIL) });
        }
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [RULE_SET_SUMMARY],
              page: 1,
              page_size: 20,
              total_items: 1,
              total_pages: 1,
            }),
        });
      }) as unknown as typeof fetch,
    );

    renderWithProviders(<ClinicalRuleSetsPage />);

    const detailButton = await screen.findByRole("button", { name: /ver detalhes/i });
    fireEvent.click(detailButton);

    expect(await screen.findByText("Saturação de oxigênio (SpO₂, %)")).toBeInTheDocument();
    expect(screen.getByText(/insuficiencia respiratoria hipercapnica confirmada/i)).toBeInTheDocument();
    expect(screen.getByText("abc123")).toBeInTheDocument();
    expect(screen.getByText("dev-admin-clinico")).toBeInTheDocument();
  });

  it("mostra as regras e condutas do conjunto, com botao de editar quando em draft", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/clinical-rule-sets/rs-1")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(RULE_SET_DETAIL) });
        }
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [RULE_SET_SUMMARY],
              page: 1,
              page_size: 20,
              total_items: 1,
              total_pages: 1,
            }),
        });
      }) as unknown as typeof fetch,
    );

    renderWithProviders(<ClinicalRuleSetsPage />);

    const detailButton = await screen.findByRole("button", { name: /ver detalhes/i });
    fireEvent.click(detailButton);

    expect(await screen.findByText("spo2_percent >= 96")).toBeInTheDocument();
    expect(screen.getByText("Rotina.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /editar/i }).length).toBeGreaterThan(0);
  });

  it("publica um conjunto selecionando um medico cadastrado como aprovador", async () => {
    const EMPLOYEES_PAGE = {
      items: [
        {
          id: "employee-1",
          full_name: "Dra. Ana Souza",
          registration_number: "CRM-12345",
          professional_type: "MEDICO",
          active: true,
        },
      ],
      page: 1,
      page_size: 100,
      total_items: 1,
      total_pages: 1,
    };

    const fetchMock = vi.fn((url: string, init?: { method?: string; body?: string }) => {
      if (url.includes("/admin/employees")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(EMPLOYEES_PAGE) });
      }
      if (url.includes("/publish") && init?.method === "POST") {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(RULE_SET_DETAIL) });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            items: [RULE_SET_SUMMARY],
            page: 1,
            page_size: 20,
            total_items: 1,
            total_pages: 1,
          }),
      });
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderWithProviders(<ClinicalRuleSetsPage />);

    const publishButton = await screen.findByRole("button", { name: /publicar/i });
    fireEvent.click(publishButton);

    // Campo de aprovador e um combobox pesquisavel (nunca texto livre
    // digitado sem restricao) - digitar filtra a lista de medicos ativos
    // cadastrados e so um clique na opcao confirma a selecao.
    const approverInput = await screen.findByRole("combobox", { name: /aprovador/i });
    fireEvent.focus(approverInput);
    fireEvent.change(approverInput, { target: { value: "Ana" } });
    const approverOption = await screen.findByRole("option", { name: /Dra\. Ana Souza/i });
    fireEvent.mouseDown(approverOption);

    const justificationInput = screen.getByLabelText(/justificativa/i);
    fireEvent.change(justificationInput, { target: { value: "Revisado e aprovado." } });

    const confirmButton = screen.getByRole("button", { name: /^confirmar$/i });
    fireEvent.click(confirmButton);

    await vi.waitFor(() => {
      const publishCall = fetchMock.mock.calls.find(
        (call) => typeof call[0] === "string" && call[0].includes("/publish"),
      );
      expect(publishCall).toBeTruthy();
    });
    const publishCall = fetchMock.mock.calls.find(
      (call) => typeof call[0] === "string" && call[0].includes("/publish"),
    );
    const body = JSON.parse((publishCall![1] as { body: string }).body);
    expect(body.approver_employee_id).toBe("employee-1");
    expect(body.justification).toBe("Revisado e aprovado.");
  });

  it("mostra o botao de rollback apenas na linha publicada, nunca em draft ou retired isolado", async () => {
    const PUBLISHED_SUMMARY = { ...RULE_SET_SUMMARY, id: "rs-published", status: "published" };
    const RETIRED_SUMMARY = { ...RULE_SET_SUMMARY, id: "rs-retired", status: "retired" };

    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [RULE_SET_SUMMARY, PUBLISHED_SUMMARY, RETIRED_SUMMARY],
              page: 1,
              page_size: 20,
              total_items: 3,
              total_pages: 1,
            }),
        }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<ClinicalRuleSetsPage />);

    await screen.findAllByText("Saturação de oxigênio (SpO₂)");
    // Uma unica linha (a publicada) deve ter o botao de rollback - draft
    // tem "Publicar", retired isolado nao tem nenhuma acao de transicao.
    expect(screen.getAllByRole("button", { name: /reverter \(rollback\)/i })).toHaveLength(1);
    expect(screen.getByRole("button", { name: /^publicar$/i })).toBeInTheDocument();
  });

  it("abre o seletor de rollback a partir da versao publicada e confirma a restauracao de uma versao anterior", async () => {
    const PUBLISHED_SUMMARY = { ...RULE_SET_SUMMARY, id: "rs-published", status: "published" };
    const RETIRED_SUMMARY = {
      ...RULE_SET_SUMMARY,
      id: "rs-retired-old",
      status: "retired",
      version: "0.0.9",
    };
    const EMPLOYEES_PAGE = {
      items: [
        {
          id: "employee-1",
          full_name: "Dra. Ana Souza",
          registration_number: "CRM-12345",
          professional_type: "MEDICO",
          active: true,
        },
      ],
      page: 1,
      page_size: 100,
      total_items: 1,
      total_pages: 1,
    };

    const fetchMock = vi.fn((url: string, init?: { method?: string; body?: string }) => {
      if (url.includes("/admin/employees")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(EMPLOYEES_PAGE) });
      }
      if (url.includes("/rollback") && init?.method === "POST") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ...RULE_SET_DETAIL, id: "rs-retired-old", status: "published" }),
        });
      }
      if (url.includes("status=retired")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [RETIRED_SUMMARY],
              page: 1,
              page_size: 100,
              total_items: 1,
              total_pages: 1,
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            items: [PUBLISHED_SUMMARY],
            page: 1,
            page_size: 20,
            total_items: 1,
            total_pages: 1,
          }),
      });
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderWithProviders(<ClinicalRuleSetsPage />);

    const rollbackButton = await screen.findByRole("button", { name: /reverter \(rollback\)/i });
    fireEvent.click(rollbackButton);

    await screen.findByText(/selecione a versão anteriormente publicada/i);
    const restoreButton = await screen.findByRole("button", { name: /restaurar esta versão/i });
    fireEvent.click(restoreButton);

    const approverInput = await screen.findByRole("combobox", { name: /aprovador/i });
    fireEvent.focus(approverInput);
    fireEvent.change(approverInput, { target: { value: "Ana" } });
    const approverOption = await screen.findByRole("option", { name: /Dra\. Ana Souza/i });
    fireEvent.mouseDown(approverOption);

    const justificationInput = screen.getByLabelText(/justificativa/i);
    fireEvent.change(justificationInput, {
      target: { value: "Nova versao apresentou problema; revertendo." },
    });

    const confirmButton = screen.getByRole("button", { name: /^confirmar$/i });
    fireEvent.click(confirmButton);

    await vi.waitFor(() => {
      const rollbackCall = fetchMock.mock.calls.find(
        (call) => typeof call[0] === "string" && call[0].includes("/rollback"),
      );
      expect(rollbackCall).toBeTruthy();
    });
    const rollbackCall = fetchMock.mock.calls.find(
      (call) => typeof call[0] === "string" && call[0].includes("/rollback"),
    );
    expect(rollbackCall![0]).toContain("rs-retired-old");
    const body = JSON.parse((rollbackCall![1] as { body: string }).body);
    expect(body.approver_employee_id).toBe("employee-1");
    expect(body.justification).toBe("Nova versao apresentou problema; revertendo.");
  });

  it("edita uma regra existente e envia PATCH com os novos valores", async () => {
    const fetchMock = vi.fn((url: string, init?: { method?: string; body?: string }) => {
      if (url.includes("/rules/rule-1") && init?.method === "PATCH") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              ...RULE_SET_DETAIL,
              content_hash: "new-hash",
              rules: [
                {
                  ...RULE_SET_DETAIL.rules[0],
                  when: "spo2_percent >= 97",
                  classification_label: "Normal ajustado",
                },
              ],
            }),
        });
      }
      if (url.includes("/clinical-rule-sets/rs-1")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(RULE_SET_DETAIL) });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            items: [RULE_SET_SUMMARY],
            page: 1,
            page_size: 20,
            total_items: 1,
            total_pages: 1,
          }),
      });
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderWithProviders(<ClinicalRuleSetsPage />);

    const detailButton = await screen.findByRole("button", { name: /ver detalhes/i });
    fireEvent.click(detailButton);

    await screen.findByText("spo2_percent >= 96");
    const editButtons = screen.getAllByRole("button", { name: /editar/i });
    fireEvent.click(editButtons[0]);

    const whenInput = await screen.findByLabelText(/condição \(when\)/i);
    fireEvent.change(whenInput, { target: { value: "spo2_percent >= 97" } });

    const saveButton = screen.getByRole("button", { name: /^salvar$/i });
    fireEvent.click(saveButton);

    await screen.findByText("spo2_percent >= 97");
    const patchCall = fetchMock.mock.calls.find(
      (call) => typeof call[0] === "string" && call[0].includes("/rules/rule-1"),
    );
    expect(patchCall).toBeTruthy();
    const body = JSON.parse((patchCall![1] as { body: string }).body);
    expect(body.when).toBe("spo2_percent >= 97");
  });
});
