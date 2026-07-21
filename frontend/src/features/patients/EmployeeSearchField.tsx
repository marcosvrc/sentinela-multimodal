import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FormField, fieldDescribedBy } from "@/components/ui/FormField";
import formStyles from "@/components/ui/FormField.module.css";
import styles from "./EmployeeSearchField.module.css";
import { listAnalysisProfessionals } from "@/services/api/analyses";
import type { AnalysisProfessional } from "@/types/analysis";
import { formatEmployeeLabel } from "./observationConfig";

interface EmployeeSearchFieldProps {
  id: string;
  label: string;
  devSubject: string;
  value: AnalysisProfessional | null;
  onSelect: (employee: AnalysisProfessional) => void;
  onClear: () => void;
  error?: string;
  required?: boolean;
}

/**
 * Campo de "Funcionario" pesquisavel por nome, usado para o autor de uma
 * observacao clinica. Reaproveita `GET /analyses/professionals` (medicos e
 * enfermeiros ativos da instituicao - mesmo endpoint do filtro "Medico" do
 * historico de analises) em vez de `/admin/employees`, que exige papel
 * administrativo e nao esta disponivel para quem registra a observacao
 * (medico/enfermeiro). O filtro por nome e feito no cliente: a lista de
 * profissionais clinicos de uma instituicao e naturalmente pequena e ja
 * chega completa em uma unica chamada.
 */
export function EmployeeSearchField({
  id,
  label,
  devSubject,
  value,
  onSelect,
  onClear,
  error,
  required,
}: EmployeeSearchFieldProps) {
  const [term, setTerm] = useState("");
  const [focused, setFocused] = useState(false);

  const query = useQuery({
    queryKey: ["analyses", "professionals", devSubject],
    queryFn: () => listAnalysisProfessionals(devSubject),
    enabled: Boolean(devSubject),
  });

  const normalizedTerm = term.trim().toLocaleLowerCase("pt-BR");
  const matches = (query.data ?? []).filter(
    (employee) =>
      employee.full_name.toLocaleLowerCase("pt-BR").includes(normalizedTerm) ||
      (employee.registration_number ?? "").toLocaleLowerCase("pt-BR").includes(normalizedTerm),
  );
  const showResults = focused && !value;

  if (value) {
    return (
      <FormField id={id} label={label} error={error} required={required}>
        <div className={[formStyles.input, styles.selected].join(" ")}>
          <span>{formatEmployeeLabel(value)}</span>
          <button
            type="button"
            className={styles.clearButton}
            onClick={() => {
              onClear();
              setTerm("");
            }}
          >
            Trocar
          </button>
        </div>
      </FormField>
    );
  }

  return (
    <FormField id={id} label={label} error={error} required={required}>
      <div className={styles.wrapper}>
        <input
          id={id}
          className={[formStyles.input, error && formStyles.inputError].filter(Boolean).join(" ")}
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="Buscar funcionario por nome"
          autoComplete="off"
          role="combobox"
          aria-expanded={showResults}
          aria-controls={`${id}-results`}
          aria-invalid={Boolean(error)}
          aria-describedby={fieldDescribedBy(id, error)}
          required={required}
        />

        {showResults && (
          <ul id={`${id}-results`} className={styles.results} role="listbox">
            {query.isLoading && <li className={styles.resultItemMuted}>Carregando funcionarios...</li>}
            {query.isError && (
              <li className={styles.resultItemMuted} role="alert">
                Nao foi possivel carregar os funcionarios agora.
              </li>
            )}
            {query.isSuccess && matches.length === 0 && (
              <li className={styles.resultItemMuted}>Nenhum funcionario encontrado.</li>
            )}
            {query.isSuccess &&
              matches.map((employee) => (
                <li key={employee.external_subject}>
                  {/* onMouseDown (nao onClick) evita que o onBlur do input
                      feche a lista antes do clique ser processado. */}
                  <button
                    type="button"
                    className={styles.resultItem}
                    role="option"
                    aria-selected={false}
                    onMouseDown={(event) => {
                      event.preventDefault();
                      onSelect(employee);
                      setTerm("");
                    }}
                  >
                    {formatEmployeeLabel(employee)}
                  </button>
                </li>
              ))}
          </ul>
        )}
      </div>
    </FormField>
  );
}
