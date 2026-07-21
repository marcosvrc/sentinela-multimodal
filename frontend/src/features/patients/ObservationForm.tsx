import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SelectField } from "@/components/ui/SelectField";
import { TextField } from "@/components/ui/TextField";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/feedback/ToastProvider";
import { extractErrorMessage } from "@/lib/errorMessage";
import { createObservation } from "@/services/api/patients";
import { ApiRequestError } from "@/types/api";
import type { AnalysisProfessional } from "@/types/analysis";
import { ObservationType } from "@/types/enums.generated";
import { EmployeeSearchField } from "./EmployeeSearchField";
import {
  CREATABLE_OBSERVATION_TYPES,
  formatEmployeeLabel,
  GLYCEMIA_MOMENT_OPTIONS,
  GLYCEMIA_PATIENT_TYPE_OPTIONS,
  OBSERVATION_TYPE_CONFIG,
  PAIN_LOCATION_OPTIONS,
} from "./observationConfig";

const TYPE_OPTIONS = CREATABLE_OBSERVATION_TYPES.map((type) => ({
  value: type,
  label: OBSERVATION_TYPE_CONFIG[type].label,
}));

interface ObservationFormProps {
  devSubject: string;
  patientId: string;
  onCreated: () => void;
  onCancel: () => void;
}

/**
 * Formulario de registro de observacao clinica, exibido dentro de um
 * modal (`PatientDetailPage`). Os campos exibidos dependem do
 * `observation_type` escolhido: valor unico, par sistolica/diastolica
 * (pressao arterial), ou valor + contexto obrigatorio (glicemia - momento,
 * tipo de paciente, uso de insulina; ver app.observations.validation).
 */
export function ObservationForm({
  devSubject,
  patientId,
  onCreated,
  onCancel,
}: ObservationFormProps) {
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [type, setType] = useState<ObservationType>(ObservationType.SPO2);
  const [singleValue, setSingleValue] = useState("");
  const [systolic, setSystolic] = useState("");
  const [diastolic, setDiastolic] = useState("");
  const [origin, setOrigin] = useState("");
  const [author, setAuthor] = useState<AnalysisProfessional | null>(null);
  const [glycemiaMoment, setGlycemiaMoment] = useState("");
  const [glycemiaPatientType, setGlycemiaPatientType] = useState("");
  const [glycemiaInsulinUse, setGlycemiaInsulinUse] = useState("");
  const [painLocation, setPainLocation] = useState("");
  const [painSuddenOnset, setPainSuddenOnset] = useState("");
  const [painAlarmSymptoms, setPainAlarmSymptoms] = useState("");
  const [seizureOccurred, setSeizureOccurred] = useState("");
  const [seizureWitnessed, setSeizureWitnessed] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const config = OBSERVATION_TYPE_CONFIG[type];
  const isBloodPressure = type === ObservationType.BLOOD_PRESSURE;
  const isGlycemia = type === ObservationType.GLYCEMIA;
  const isPain = type === ObservationType.PAIN;
  const isSeizure = type === ObservationType.SEIZURE;

  const mutation = useMutation({
    mutationFn: () => {
      const value = isBloodPressure
        ? { systolic: Number(systolic), diastolic: Number(diastolic) }
        : isSeizure
          ? { occurred: seizureOccurred === "sim" }
          : { value: Number(singleValue) };

      const context = isGlycemia
        ? {
            moment: glycemiaMoment,
            patient_type: glycemiaPatientType,
            insulin_use: glycemiaInsulinUse === "sim",
          }
        : isPain
          ? {
              location: painLocation,
              sudden_onset: painSuddenOnset === "sim",
              alarm_symptoms_present: painAlarmSymptoms === "sim",
            }
          : isSeizure
            ? { witnessed: seizureWitnessed === "sim" }
            : undefined;

      return createObservation(devSubject, patientId, {
        observation_type: type,
        value,
        unit: config.unit,
        context,
        measured_at: new Date().toISOString(),
        origin,
        author: author ? formatEmployeeLabel(author) : "",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["observations", patientId] });
      setSingleValue("");
      setSystolic("");
      setDiastolic("");
      setGlycemiaMoment("");
      setGlycemiaPatientType("");
      setGlycemiaInsulinUse("");
      setPainLocation("");
      setPainSuddenOnset("");
      setPainAlarmSymptoms("");
      setSeizureOccurred("");
      setSeizureWitnessed("");
      setAuthor(null);
      setFieldErrors({});
      showSuccess("Observação registrada com sucesso.");
      onCreated();
    },
    onError: (error: unknown) => {
      if (error instanceof ApiRequestError) setFieldErrors(error.fieldErrors);
      showError(extractErrorMessage(error, "Não foi possível registrar a observação."));
    },
  });

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <SelectField
        id="observation_type"
        label="Tipo de observacao"
        options={TYPE_OPTIONS}
        value={type}
        onChange={(event) => setType(event.target.value as ObservationType)}
      />

      {isBloodPressure ? (
        <div style={{ display: "flex", gap: "var(--space-3)" }}>
          <TextField
            id="systolic"
            label="Sistolica (mmHg)"
            type="number"
            required
            value={systolic}
            onChange={(event) => setSystolic(event.target.value)}
            error={fieldErrors.systolic}
          />
          <TextField
            id="diastolic"
            label="Diastolica (mmHg)"
            type="number"
            required
            value={diastolic}
            onChange={(event) => setDiastolic(event.target.value)}
            error={fieldErrors.diastolic}
          />
        </div>
      ) : isSeizure ? (
        <SelectField
          id="seizure_occurred"
          label="Ocorreu convulsão nesta observação?"
          required
          options={[
            { value: "", label: "Selecione" },
            { value: "sim", label: "Sim" },
            { value: "nao", label: "Não" },
          ]}
          value={seizureOccurred}
          onChange={(event) => setSeizureOccurred(event.target.value)}
          error={fieldErrors.occurred}
        />
      ) : (
        <TextField
          id="value"
          label={`Valor (${config.unit})`}
          type="number"
          step="any"
          required
          value={singleValue}
          onChange={(event) => setSingleValue(event.target.value)}
          error={fieldErrors.value}
        />
      )}

      {isGlycemia && (
        <>
          <SelectField
            id="glycemia_moment"
            label="Momento da medicao"
            required
            options={[{ value: "", label: "Selecione" }, ...GLYCEMIA_MOMENT_OPTIONS]}
            value={glycemiaMoment}
            onChange={(event) => setGlycemiaMoment(event.target.value)}
            error={fieldErrors.moment}
          />
          <SelectField
            id="glycemia_patient_type"
            label="Tipo de paciente"
            required
            options={[{ value: "", label: "Selecione" }, ...GLYCEMIA_PATIENT_TYPE_OPTIONS]}
            value={glycemiaPatientType}
            onChange={(event) => setGlycemiaPatientType(event.target.value)}
            error={fieldErrors.patient_type}
          />
          <SelectField
            id="glycemia_insulin_use"
            label="Uso de insulina"
            required
            options={[
              { value: "", label: "Selecione" },
              { value: "sim", label: "Sim" },
              { value: "nao", label: "Nao" },
            ]}
            value={glycemiaInsulinUse}
            onChange={(event) => setGlycemiaInsulinUse(event.target.value)}
            error={fieldErrors.insulin_use}
          />
        </>
      )}

      {isPain && (
        <>
          <SelectField
            id="pain_location"
            label="Localização da dor"
            required
            options={[{ value: "", label: "Selecione" }, ...PAIN_LOCATION_OPTIONS]}
            value={painLocation}
            onChange={(event) => setPainLocation(event.target.value)}
            error={fieldErrors.location}
          />
          <SelectField
            id="pain_sudden_onset"
            label="Início súbito?"
            required
            options={[
              { value: "", label: "Selecione" },
              { value: "sim", label: "Sim" },
              { value: "nao", label: "Não" },
            ]}
            value={painSuddenOnset}
            onChange={(event) => setPainSuddenOnset(event.target.value)}
            error={fieldErrors.sudden_onset}
          />
          <SelectField
            id="pain_alarm_symptoms"
            label="Sintomas associados (dispneia, sudorese, náusea, irradiação)?"
            required
            options={[
              { value: "", label: "Selecione" },
              { value: "sim", label: "Sim" },
              { value: "nao", label: "Não" },
            ]}
            value={painAlarmSymptoms}
            onChange={(event) => setPainAlarmSymptoms(event.target.value)}
            error={fieldErrors.alarm_symptoms_present}
          />
        </>
      )}

      {isSeizure && (
        <SelectField
          id="seizure_witnessed"
          label="Evento presenciado?"
          required
          options={[
            { value: "", label: "Selecione" },
            { value: "sim", label: "Sim" },
            { value: "nao", label: "Não" },
          ]}
          value={seizureWitnessed}
          onChange={(event) => setSeizureWitnessed(event.target.value)}
          error={fieldErrors.witnessed}
        />
      )}

      <TextField
        id="origin"
        label="Origem"
        required
        placeholder="ex: dispositivo, formulario"
        value={origin}
        onChange={(event) => setOrigin(event.target.value)}
        error={fieldErrors.origin}
      />
      <EmployeeSearchField
        id="author"
        label="Funcionario"
        devSubject={devSubject}
        required
        value={author}
        onSelect={setAuthor}
        onClear={() => setAuthor(null)}
        error={fieldErrors.author}
      />

      <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={mutation.isPending}>
          Cancelar
        </Button>
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Registrando..." : "Registrar observacao"}
        </Button>
      </div>
    </form>
  );
}
