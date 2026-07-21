import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { ObservationForm } from "@/features/patients/ObservationForm";
import { renderWithProviders } from "../../utils/renderWithProviders";

const DEV_SUBJECT = "dev-medico";
const PATIENT_ID = "patient-1";

const PROFESSIONALS = [
  {
    external_subject: "dev-medico",
    full_name: "Dra. Ana Souza",
    registration_number: "CRM-12345",
  },
];

function stubFetch() {
  const fetchMock = vi.fn((url: string) => {
    const href = url.toString();
    if (href.includes("/analyses/professionals")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(PROFESSIONALS) });
    }
    if (href.includes("/observations")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "obs-1",
            patient_id: PATIENT_ID,
            observation_type: "PAIN",
            value: { value: 5 },
            unit: "score_0_10",
            context: {},
            measured_at: "2026-07-18T10:00:00Z",
            origin: "formulario",
            author: "Dra. Ana Souza",
            method: null,
            reading_quality: "VALID",
            created_at: "2026-07-18T10:00:00Z",
          }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  }) as unknown as typeof fetch;
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function selectAuthor() {
  const authorInput = await screen.findByRole("combobox", { name: /funcionario/i });
  fireEvent.focus(authorInput);
  fireEvent.change(authorInput, { target: { value: "Ana" } });
  const option = await screen.findByRole("option", { name: /Dra\. Ana Souza/i });
  fireEvent.mouseDown(option);
}

describe("ObservationForm", () => {
  it("registra dor com o contexto ampliado (localização, início súbito, sintomas de alarme)", async () => {
    const fetchMock = stubFetch();
    const onCreated = vi.fn();
    renderWithProviders(
      <ObservationForm
        devSubject={DEV_SUBJECT}
        patientId={PATIENT_ID}
        onCreated={onCreated}
        onCancel={vi.fn()}
      />,
    );

    const typeSelect = screen.getByLabelText(/tipo de observacao/i);
    fireEvent.change(typeSelect, { target: { value: "PAIN" } });

    fireEvent.change(screen.getByLabelText(/^valor/i), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText(/localização da dor/i), {
      target: { value: "toracica" },
    });
    fireEvent.change(screen.getByLabelText(/início súbito/i), { target: { value: "sim" } });
    fireEvent.change(
      screen.getByLabelText(/sintomas associados \(dispneia, sudorese/i),
      { target: { value: "nao" } },
    );
    fireEvent.change(screen.getByLabelText(/^origem/i), { target: { value: "formulario" } });
    await selectAuthor();

    fireEvent.click(screen.getByRole("button", { name: /registrar observacao/i }));

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(
        (call) =>
          typeof call[0] === "string" &&
          call[0].includes("/observations") &&
          (call[1] as { method?: string })?.method === "POST",
      );
      expect(postCall).toBeTruthy();
    });
    const postCall = fetchMock.mock.calls.find(
      (call) =>
        typeof call[0] === "string" &&
        call[0].includes("/observations") &&
        (call[1] as { method?: string })?.method === "POST",
    );
    const body = JSON.parse((postCall![1] as { body: string }).body);
    expect(body.observation_type).toBe("PAIN");
    expect(body.value).toEqual({ value: 5 });
    expect(body.context).toEqual({
      location: "toracica",
      sudden_onset: true,
      alarm_symptoms_present: false,
    });
    expect(onCreated).toHaveBeenCalled();
  });

  it("registra convulsão com o evento e o contexto de testemunha", async () => {
    const fetchMock = stubFetch();
    renderWithProviders(
      <ObservationForm
        devSubject={DEV_SUBJECT}
        patientId={PATIENT_ID}
        onCreated={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const typeSelect = screen.getByLabelText(/tipo de observacao/i);
    fireEvent.change(typeSelect, { target: { value: "SEIZURE" } });

    fireEvent.change(screen.getByLabelText(/ocorreu convulsão/i), { target: { value: "sim" } });
    fireEvent.change(screen.getByLabelText(/evento presenciado/i), { target: { value: "nao" } });
    fireEvent.change(screen.getByLabelText(/^origem/i), { target: { value: "formulario" } });
    await selectAuthor();

    fireEvent.click(screen.getByRole("button", { name: /registrar observacao/i }));

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(
        (call) =>
          typeof call[0] === "string" &&
          call[0].includes("/observations") &&
          (call[1] as { method?: string })?.method === "POST",
      );
      expect(postCall).toBeTruthy();
    });
    const postCall = fetchMock.mock.calls.find(
      (call) =>
        typeof call[0] === "string" &&
        call[0].includes("/observations") &&
        (call[1] as { method?: string })?.method === "POST",
    );
    const body = JSON.parse((postCall![1] as { body: string }).body);
    expect(body.observation_type).toBe("SEIZURE");
    expect(body.value).toEqual({ occurred: true });
    expect(body.context).toEqual({ witnessed: false });
  });

  it("registra débito urinário como valor numérico simples", async () => {
    const fetchMock = stubFetch();
    renderWithProviders(
      <ObservationForm
        devSubject={DEV_SUBJECT}
        patientId={PATIENT_ID}
        onCreated={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const typeSelect = screen.getByLabelText(/tipo de observacao/i);
    fireEvent.change(typeSelect, { target: { value: "URINE_OUTPUT" } });

    fireEvent.change(screen.getByLabelText(/^valor/i), { target: { value: "40" } });
    fireEvent.change(screen.getByLabelText(/^origem/i), { target: { value: "formulario" } });
    await selectAuthor();

    fireEvent.click(screen.getByRole("button", { name: /registrar observacao/i }));

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(
        (call) =>
          typeof call[0] === "string" &&
          call[0].includes("/observations") &&
          (call[1] as { method?: string })?.method === "POST",
      );
      expect(postCall).toBeTruthy();
    });
    const postCall = fetchMock.mock.calls.find(
      (call) =>
        typeof call[0] === "string" &&
        call[0].includes("/observations") &&
        (call[1] as { method?: string })?.method === "POST",
    );
    const body = JSON.parse((postCall![1] as { body: string }).body);
    expect(body.observation_type).toBe("URINE_OUTPUT");
    expect(body.value).toEqual({ value: 40 });
  });
});
