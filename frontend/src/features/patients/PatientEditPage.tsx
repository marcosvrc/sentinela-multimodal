import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { TextField } from "@/components/ui/TextField";
import { SelectField } from "@/components/ui/SelectField";
import { Button } from "@/components/ui/Button";
import { Section } from "@/components/ui/Section";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Skeleton } from "@/components/feedback/Skeleton";
import { useToast } from "@/components/feedback/ToastProvider";
import { useDevSession } from "@/hooks/useDevSession";
import { extractErrorMessage } from "@/lib/errorMessage";
import { getPatient, updatePatient } from "@/services/api/patients";
import { ApiRequestError } from "@/types/api";
import type { PatientUpdateInput } from "@/types/patient";

const REGISTERED_SEX_OPTIONS = [
  { value: "", label: "Selecione" },
  { value: "feminino", label: "Feminino" },
  { value: "masculino", label: "Masculino" },
  { value: "nao_informado", label: "Prefere nao informar" },
];

interface EditForm {
  medical_record_number: string;
  full_name: string;
  birth_date: string;
  registered_sex: string;
  email: string;
  height_cm: string;
}

const EMPTY_FORM: EditForm = {
  medical_record_number: "",
  full_name: "",
  birth_date: "",
  registered_sex: "",
  email: "",
  height_cm: "",
};

/**
 * Edicao de paciente (rota `/patients/:patientId/edit`, acionada pela
 * listagem de pacientes). Carrega o registro atual via `GET /patients/:id`
 * e preenche o formulario assim que a consulta resolve - o profissional
 * nunca preenche do zero, apenas ajusta o que for necessario.
 */
export function PatientEditPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const { subject } = useDevSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [form, setForm] = useState<EditForm>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const patientQuery = useQuery({
    queryKey: ["patient", subject, patientId],
    queryFn: () => getPatient(subject as string, patientId as string),
    enabled: Boolean(subject && patientId),
  });

  // Preenche o formulario assim que os dados do paciente chegam (ou
  // mudam de identidade - ex.: navegacao direta entre dois pacientes).
  useEffect(() => {
    const patient = patientQuery.data;
    if (!patient) return;
    setForm({
      medical_record_number: patient.medical_record_number,
      full_name: patient.full_name,
      birth_date: patient.birth_date,
      registered_sex: patient.registered_sex,
      email: patient.email ?? "",
      height_cm: patient.height_cm != null ? String(patient.height_cm) : "",
    });
  }, [patientQuery.data]);

  const mutation = useMutation({
    mutationFn: () => {
      const data: PatientUpdateInput = {
        medical_record_number: form.medical_record_number,
        full_name: form.full_name,
        birth_date: form.birth_date,
        registered_sex: form.registered_sex,
        email: form.email ? form.email : null,
        height_cm: form.height_cm ? Number(form.height_cm) : null,
      };
      return updatePatient(subject as string, patientId as string, data);
    },
    onSuccess: (patient) => {
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      queryClient.invalidateQueries({ queryKey: ["patient", subject, patientId] });
      showSuccess("Paciente atualizado com sucesso.");
      navigate(`/patients/${patient.id}`);
    },
    onError: (error: unknown) => {
      if (error instanceof ApiRequestError) {
        setFieldErrors(error.fieldErrors);
      }
      showError(extractErrorMessage(error, "Não foi possível salvar as alterações."));
    },
  });

  function updateField<K extends keyof EditForm>(key: K, value: EditForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  if (!subject || !patientId) {
    return <EmptyState title="Configure o usuario de desenvolvimento primeiro." />;
  }

  if (patientQuery.isLoading) return <Skeleton rows={5} />;
  if (patientQuery.isError) {
    return (
      <ErrorState
        description={(patientQuery.error as Error).message}
        onRetry={() => patientQuery.refetch()}
      />
    );
  }

  if (!patientQuery.data) return null;

  return (
    <>
      <PageHeader
        title="Editar paciente"
        description={`Prontuario ${patientQuery.data.medical_record_number}`}
      />

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
            value={form.email}
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
            hint="Usada junto com o peso mais recente para calcular o IMC."
            value={form.height_cm}
            onChange={(event) => updateField("height_cm", event.target.value)}
            error={fieldErrors.height_cm}
          />
        </Section>

        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button
            type="button"
            variant="secondary"
            onClick={() => navigate(`/patients/${patientId}`)}
            disabled={mutation.isPending}
          >
            Cancelar
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Salvando..." : "Salvar alteracoes"}
          </Button>
        </div>
      </form>
    </>
  );
}
