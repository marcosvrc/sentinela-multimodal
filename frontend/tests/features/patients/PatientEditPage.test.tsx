import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { PatientEditPage } from "@/features/patients/PatientEditPage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const DEV_SUBJECT = "dev-medico";

const PATIENT = {
  id: "patient-1",
  medical_record_number: "MRN-1",
  full_name: "Maria Teste",
  birth_date: "1990-01-01",
  age: 36,
  registered_sex: "feminino",
  email: "maria@example.com",
  height_cm: 165,
  active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("PatientEditPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
  });

  it("carrega os dados atuais do paciente e preenche o formulario", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({ ok: true, json: () => Promise.resolve(PATIENT) }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(
      <Routes>
        <Route path="/patients/:patientId/edit" element={<PatientEditPage />} />
      </Routes>,
      ["/patients/patient-1/edit"],
    );

    await waitFor(() =>
      expect(screen.getByLabelText(/identificador institucional/i)).toHaveValue("MRN-1"),
    );
    expect(screen.getByLabelText(/^nome/i)).toHaveValue("Maria Teste");
    expect(screen.getByLabelText(/data de nascimento/i)).toHaveValue("1990-01-01");
    expect(screen.getByLabelText(/sexo registrado/i)).toHaveValue("feminino");
    expect(screen.getByLabelText(/email/i)).toHaveValue("maria@example.com");
    expect(screen.getByLabelText(/altura em cm/i)).toHaveValue(165);
  });

  it("envia PATCH com os campos editados", async () => {
    let capturedBody: Record<string, unknown> | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, options?: { method?: string; body?: string }) => {
        if (options?.method === "PATCH") {
          capturedBody = JSON.parse(options.body ?? "{}");
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ ...PATIENT, full_name: "Maria Editada" }),
          });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve(PATIENT) });
      }) as unknown as typeof fetch,
    );

    renderWithProviders(
      <Routes>
        <Route path="/patients/:patientId/edit" element={<PatientEditPage />} />
      </Routes>,
      ["/patients/patient-1/edit"],
    );

    await waitFor(() => expect(screen.getByLabelText(/^nome/i)).toHaveValue("Maria Teste"));
    fireEvent.change(screen.getByLabelText(/^nome/i), { target: { value: "Maria Editada" } });
    fireEvent.click(screen.getByRole("button", { name: /salvar alteracoes/i }));

    await waitFor(() => expect(capturedBody).not.toBeNull());
    expect(capturedBody).toMatchObject({
      full_name: "Maria Editada",
      medical_record_number: "MRN-1",
      height_cm: 165,
    });
  });
});
