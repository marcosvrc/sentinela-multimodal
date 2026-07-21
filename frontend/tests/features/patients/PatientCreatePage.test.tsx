import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { PatientCreatePage } from "@/features/patients/PatientCreatePage";
import { renderWithProviders } from "../../utils/renderWithProviders";

const DEV_SUBJECT = "dev-medico";

describe("PatientCreatePage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("sentinelhealth.dev_subject", DEV_SUBJECT);
  });

  it("mapeia field_errors da API para os campos do formulario", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 409,
          json: () =>
            Promise.resolve({
              code: "DUPLICATE_MEDICAL_RECORD_NUMBER",
              message: "Ja existe um paciente com este identificador.",
              field_errors: {
                medical_record_number: "Identificador ja cadastrado nesta instituicao.",
              },
              request_id: "req_1",
            }),
        }),
      ) as unknown as typeof fetch,
    );

    renderWithProviders(<PatientCreatePage />);

    fireEvent.change(screen.getByLabelText(/identificador institucional/i), {
      target: { value: "MRN-DUP" },
    });
    fireEvent.change(screen.getByLabelText(/^nome/i), { target: { value: "Paciente Teste" } });
    fireEvent.change(screen.getByLabelText(/data de nascimento/i), {
      target: { value: "1990-01-01" },
    });
    fireEvent.change(screen.getByLabelText(/sexo registrado/i), {
      target: { value: "feminino" },
    });

    fireEvent.click(screen.getByRole("button", { name: /salvar/i }));

    expect(
      await screen.findByText(/identificador ja cadastrado nesta instituicao/i),
    ).toBeInTheDocument();
  });

  it("envia a altura informada como height_cm numerico no cadastro", async () => {
    let capturedBody: Record<string, unknown> | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, options?: { body?: string }) => {
        if (options?.body) capturedBody = JSON.parse(options.body as string);
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: "patient-1",
              medical_record_number: "MRN-2",
              full_name: "Paciente Teste",
              birth_date: "1990-01-01",
              age: 36,
              registered_sex: "feminino",
              email: null,
              height_cm: 170,
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-01T00:00:00Z",
            }),
        });
      }) as unknown as typeof fetch,
    );

    renderWithProviders(<PatientCreatePage />);

    fireEvent.change(screen.getByLabelText(/identificador institucional/i), {
      target: { value: "MRN-2" },
    });
    fireEvent.change(screen.getByLabelText(/^nome/i), { target: { value: "Paciente Teste" } });
    fireEvent.change(screen.getByLabelText(/data de nascimento/i), {
      target: { value: "1990-01-01" },
    });
    fireEvent.change(screen.getByLabelText(/sexo registrado/i), {
      target: { value: "feminino" },
    });
    fireEvent.change(screen.getByLabelText(/altura em cm/i), { target: { value: "170" } });

    fireEvent.click(screen.getByRole("button", { name: /salvar/i }));

    await vi.waitFor(() => expect(capturedBody).not.toBeNull());
    expect(capturedBody).toMatchObject({ height_cm: 170 });
  });
});
