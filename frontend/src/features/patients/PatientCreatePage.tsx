import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { TextField } from "@/components/ui/TextField";
import { SelectField } from "@/components/ui/SelectField";
import { Button } from "@/components/ui/Button";
import { Section } from "@/components/ui/Section";
import { useToast } from "@/components/feedback/ToastProvider";
import { useDevSession } from "@/hooks/useDevSession";
import { extractErrorMessage } from "@/lib/errorMessage";
import { createPatient } from "@/services/api/patients";
import { ApiRequestError } from "@/types/api";
import type { PatientCreateInput } from "@/types/patient";

const REGISTERED_SEX_OPTIONS = [
  { value: "", label: "Selecione" },
  { value: "feminino", label: "Feminino" },
  { value: "masculino", label: "Masculino" },
  { value: "nao_informado", label: "Prefere nao informar" },
];

const EMPTY_FORM: PatientCreateInput = {
  medical_record_number: "",
  full_name: "",
  birth_date: "",
  registered_sex: "",
  email: "",
};

export function PatientCreatePage() {
  const { subject } = useDevSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [form, setForm] = useState<PatientCreateInput>(EMPTY_FORM);
  const [heightInput, setHeightInput] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const mutation = useMutation({
    mutationFn: () =>
      createPatient(subject as string, {
        ...form,
        email: form.email ? form.email : undefined,
        height_cm: heightInput ? Number(heightInput) : undefined,
      }),
    onSuccess: (patient) => {
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      showSuccess("Paciente criado com sucesso.");
      navigate(`/patients/${patient.id}`);
    },
    onError: (error: unknown) => {
      if (error instanceof ApiRequestError) {
        setFieldErrors(error.fieldErrors);
      }
      showError(extractErrorMessage(error, "Não foi possível salvar o paciente."));
    },
  });

  function updateField<K extends keyof PatientCreateInput>(key: K, value: PatientCreateInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  return (
    <>
      <PageHeader
        title="Novo paciente"
        description="Identificacao, contato e informacoes clinicas relevantes."
      />

      {!subject && <p role="alert">Configure o usuario de desenvolvimento primeiro.</p>}

      <form
        style={{ maxWidth: 480 }}
        onSubmit={(event) => {
          event.preventDefault();
          setFieldErrors({});
          mutation.mutate();
        }}
      >
        <Section title="Identificação" variant="plain">
          <TextField
            id="medical_record_number"
            label="Identificador institucional / prontuario"
            required
            value={form.medical_record_number}
            onChange={(event) => updateField("medical_record_number", event.target.value)}
            error={fieldErrors.medical_record_number}
          />
          <TextField
            id="full_name"
            label="Nome"
            required
            value={form.full_name}
            onChange={(event) => updateField("full_name", event.target.value)}
            error={fieldErrors.full_name}
          />
          <TextField
            id="birth_date"
            label="Data de nascimento"
            type="date"
            required
            value={form.birth_date}
            onChange={(event) => updateField("birth_date", event.target.value)}
            error={fieldErrors.birth_date}
          />
          <SelectField
            id="registered_sex"
            label="Sexo registrado ao nascimento"
            required
            options={REGISTERED_SEX_OPTIONS}
            value={form.registered_sex}
            onChange={(event) => updateField("registered_sex", event.target.value)}
            error={fieldErrors.registered_sex}
          />
          <TextField
            id="email"
            label="Email (opcional)"
            type="email"
            value={form.email ?? ""}
            onChange={(event) => updateField("email", event.target.value)}
            error={fieldErrors.email}
          />
        </Section>

        <Section title="Dados clínicos" variant="plain">
          <TextField
            id="height_cm"
            label="Altura em cm (opcional)"
            type="number"
            step="0.1"
            min={30}
            max={272}
            placeholder="Ex.: 170"
            hint="Usada junto com o peso para calcular o IMC."
            value={heightInput}
            onChange={(event) => setHeightInput(event.target.value)}
            error={fieldErrors.height_cm}
          />
        </Section>

        <Button type="submit" disabled={!subject || mutation.isPending}>
          {mutation.isPending ? "Salvando..." : "Salvar"}
        </Button>
      </form>
    </>
  );
}
