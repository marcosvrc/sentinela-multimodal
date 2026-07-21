import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FormField } from "@/components/ui/FormField";
import formStyles from "@/components/ui/FormField.module.css";
import styles from "./PatientSearchField.module.css";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { listPatients } from "@/services/api/patients";
import type { Patient } from "@/types/patient";

const MIN_SEARCH_LENGTH = 3;

interface PatientSearchFieldProps {
  devSubject: string;
  selectedPatient: Patient | null;
  onSelect: (patient: Patient) => void;
  onClear: () => void;
}

function isSearchable(term: string): boolean {
  const trimmed = term.trim();
  if (trimmed.length === 0) return false;
  if (/^\d+$/.test(trimmed)) return true;
  return trimmed.length >= MIN_SEARCH_LENGTH;
}

/**
 * Busca de paciente por nome ou prontuario, usada na criacao de uma nova
 * analise. Substitui o dropdown que antes carregava ate 100 pacientes de
 * uma vez.
 */
export function PatientSearchField({
  devSubject,
  selectedPatient,
  onSelect,
  onClear,
}: PatientSearchFieldProps) {
  const [term, setTerm] = useState("");
  const debouncedTerm = useDebouncedValue(term);
  const searchable = isSearchable(debouncedTerm);

  const query = useQuery({
    queryKey: ["patients", devSubject, "search", debouncedTerm],
    queryFn: () => listPatients(devSubject, { page: 1, pageSize: 10, search: debouncedTerm.trim() }),
    enabled: Boolean(devSubject) && searchable && !selectedPatient,
  });

  if (selectedPatient) {
    return (
      <FormField id="patient-search" label="Paciente">
        <div className={styles.selectedPatient}>
          <span>
            {selectedPatient.full_name} ({selectedPatient.medical_record_number})
          </span>
          <button type="button" className={styles.clearButton} onClick={onClear}>
            Trocar paciente
          </button>
        </div>
      </FormField>
    );
  }

  return (
    <FormField
      id="patient-search"
      label="Paciente"
      required
      hint="Digite ao menos 3 letras do nome, ou o numero do prontuario."
    >
      <input
        id="patient-search"
        className={formStyles.input}
        value={term}
        onChange={(event) => setTerm(event.target.value)}
        placeholder="Buscar por nome ou prontuario"
        autoComplete="off"
        role="combobox"
        aria-expanded={searchable}
        aria-controls="patient-search-results"
      />

      {searchable && (
        <ul id="patient-search-results" className={styles.results} role="listbox">
          {query.isLoading && <li className={styles.resultItemMuted}>Buscando...</li>}
          {query.isError && (
            <li className={styles.resultItemMuted} role="alert">
              Nao foi possivel buscar pacientes agora.
            </li>
          )}
          {query.isSuccess && query.data.items.length === 0 && (
            <li className={styles.resultItemMuted}>Nenhum paciente encontrado.</li>
          )}
          {query.isSuccess &&
            query.data.items.map((patient) => (
              <li key={patient.id}>
                <button
                  type="button"
                  className={styles.resultItem}
                  role="option"
                  aria-selected={false}
                  onClick={() => {
                    onSelect(patient);
                    setTerm("");
                  }}
                >
                  <span className={styles.resultName}>{patient.full_name}</span>
                  <span className={styles.resultMeta}>
                    Prontuario {patient.medical_record_number} · {patient.age} anos
                  </span>
                </button>
              </li>
            ))}
        </ul>
      )}
    </FormField>
  );
}
