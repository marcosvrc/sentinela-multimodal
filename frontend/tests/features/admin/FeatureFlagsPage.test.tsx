import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { FeatureFlagsPage } from "@/features/admin/FeatureFlagsPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const SAMPLE_FLAGS = {
  llm_provider_enabled: false,
  llm_provider: "OPENAI",
  llm_openai_model: "gpt-4o-mini",
  llm_gemini_model: "gemini-1.5-flash",
  modality_audio_enabled: true,
  modality_video_enabled: true,
  modality_image_enabled: true,
  vision_detection_enabled: false,
  vision_pose_enabled: false,
  image_recognition_enabled: false,
  sentiment_analysis_enabled: false,
  auto_clinical_support_enabled: false,
  dicom_service_enabled: false,
  updated_at: "2026-07-16T00:00:00Z",
  updated_by: null,
  openai_model_options: [
    { value: "gpt-4o-mini", label: "GPT-4o mini (recomendado - custo baixo)" },
    { value: "gpt-4o", label: "GPT-4o" },
  ],
  gemini_model_options: [
    { value: "gemini-1.5-flash", label: "Gemini 1.5 Flash" },
    { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
  ],
  gemini_implemented: false,
};

describe("FeatureFlagsPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", "dev-admin-tecnico");
  });

  it("carrega e exibe o estado atual das flags", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve(SAMPLE_FLAGS) }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<FeatureFlagsPage />);

    expect(await screen.findByText("Feature flags")).toBeInTheDocument();
    const llmSwitch = screen.getByLabelText(/usar llm real/i);
    expect(llmSwitch).not.toBeChecked();
  });

  it("ao trocar o provedor para Gemini, mostra o aviso de integração não implementada", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve(SAMPLE_FLAGS) }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<FeatureFlagsPage />);

    await screen.findByText("Feature flags");
    const providerSelect = document.getElementById("llm-provider") as HTMLSelectElement;
    fireEvent.change(providerSelect, { target: { value: "GEMINI" } });

    expect(await screen.findByText(/ainda não foi implementada/i)).toBeInTheDocument();
  });

  it("permite ligar a análise de sentimento (Azure AI Language) e envia no PATCH", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(SAMPLE_FLAGS) }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<FeatureFlagsPage />);

    await screen.findByText("Feature flags");
    const sentimentSwitch = screen.getByLabelText(/analisar sentimento/i);
    expect(sentimentSwitch).not.toBeChecked();
    fireEvent.click(sentimentSwitch);

    fireEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find((call) => {
        const init = call[1] as { method?: string } | undefined;
        return init?.method === "PATCH";
      });
      expect(patchCall).toBeDefined();
      const init = patchCall?.[1] as { body?: string } | undefined;
      const body = JSON.parse(init?.body ?? "{}");
      expect(body.sentiment_analysis_enabled).toBe(true);
    });
  });

  it("permite ligar o reconhecimento de imagem (Azure AI Vision) e envia no PATCH", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(SAMPLE_FLAGS) }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<FeatureFlagsPage />);

    await screen.findByText("Feature flags");
    const imageRecognitionSwitch = screen.getByLabelText(/rótulos de imagem/i);
    expect(imageRecognitionSwitch).not.toBeChecked();
    fireEvent.click(imageRecognitionSwitch);

    fireEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find((call) => {
        const init = call[1] as { method?: string } | undefined;
        return init?.method === "PATCH";
      });
      expect(patchCall).toBeDefined();
      const init = patchCall?.[1] as { body?: string } | undefined;
      const body = JSON.parse(init?.body ?? "{}");
      expect(body.image_recognition_enabled).toBe(true);
    });
  });

  it("permite ligar o armazenamento DICOM no Azure Health Data Services e envia no PATCH", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(SAMPLE_FLAGS) }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<FeatureFlagsPage />);

    await screen.findByText("Feature flags");
    const dicomSwitch = screen.getByLabelText(/armazenar imagens dicom/i);
    expect(dicomSwitch).not.toBeChecked();
    fireEvent.click(dicomSwitch);

    fireEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find((call) => {
        const init = call[1] as { method?: string } | undefined;
        return init?.method === "PATCH";
      });
      expect(patchCall).toBeDefined();
      const init = patchCall?.[1] as { body?: string } | undefined;
      const body = JSON.parse(init?.body ?? "{}");
      expect(body.dicom_service_enabled).toBe(true);
    });
  });

  it("permite ligar o apoio à análise clínica (IA) automático e envia no PATCH", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(SAMPLE_FLAGS) }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<FeatureFlagsPage />);

    await screen.findByText("Feature flags");
    const autoSupportSwitch = screen.getByLabelText(/gerar apoio à análise clínica automaticamente/i);
    expect(autoSupportSwitch).not.toBeChecked();
    fireEvent.click(autoSupportSwitch);

    fireEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find((call) => {
        const init = call[1] as { method?: string } | undefined;
        return init?.method === "PATCH";
      });
      expect(patchCall).toBeDefined();
      const init = patchCall?.[1] as { body?: string } | undefined;
      const body = JSON.parse(init?.body ?? "{}");
      expect(body.auto_clinical_support_enabled).toBe(true);
    });
  });

  it("envia PATCH com os campos atuais ao clicar em salvar", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(SAMPLE_FLAGS) }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<FeatureFlagsPage />);

    await screen.findByRole("heading", { name: "Feature flags" });
    const llmSwitch = screen.getByLabelText(/usar llm real/i);
    fireEvent.click(llmSwitch);

    const saveButton = screen.getByRole("button", { name: /salvar alterações/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find((call) => {
        const init = call[1] as { method?: string } | undefined;
        return init?.method === "PATCH";
      });
      expect(patchCall).toBeDefined();
      const init = patchCall?.[1] as { body?: string } | undefined;
      const body = JSON.parse(init?.body ?? "{}");
      expect(body.llm_provider_enabled).toBe(true);
    });
  });
});
