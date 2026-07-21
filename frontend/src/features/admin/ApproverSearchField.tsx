import { useState } from "react";
import { FormField, fieldDescribedBy } from "@/components/ui/FormField";
import formStyles from "@/components/ui/FormField.module.css";
import styles from "./ApproverSearchField.module.css";
import type { Employee } from "@/types/administration";

interface ApproverSearchFieldProps {
  id: string;
  label: string;
  employees: Employee[];
  isLoading: boolean;
  isError: boolean;
  value: Employee | null;
  onSelect: (employee: Employee) => void;
  onClear: () => void;
  hint?: string;
  required?: boolean;
}

/**
 * Campo de "Aprovador" pesquisavel por nome ou matricula, usado na
 * publicacao/rollback de conjunto de regras clinicas
 * (`ClinicalRuleSetsPage`). Mesmo padrao visual/comportamental de
 * `app/features/patients/EmployeeSearchField.tsx` (digitar filtra a
 * lista, selecionar trava o valor) - aqui sobre `Employee` (nao
 * `AnalysisProfessional`) porque a fonte e `GET /admin/employees`, ja
 * filtrada para medicos ativos pelo chamador. Nao existe input de texto
 * livre: sem selecionar um item da lista, `value` permanece vazio e o
 * formulario nao pode ser confirmado (o backend tambem rejeita qualquer
 * id que nao seja um medico ativo cadastrado - ver
 * `app.administration.service.get_active_doctor_for_approval`).
 */
export function ApproverSearchField({
  id,
  label,
  employees,
  isLoading,
  isError,
  value,
  onSelect,
  onClear,
  hint,
  required,
}: ApproverSearchFieldProps) {
  const [term, setTerm] = useState("");
  const [focused, setFocused] = useState(false);

  const normalizedTerm = term.trim().toLocaleLowerCase("pt-BR");
  const matches = employees.filter(
    (employee) =>
      employee.full_name.toLocaleLowerCase("pt-BR").includes(normalizedTerm) ||
      employee.registration_number.toLocaleLowerCase("pt-BR").includes(normalizedTerm),
  );
  const showResults = focused && !value;

  if (value) {
    return (
      <FormField id={id} label={label} hint={hint} required={required}>
        <div className={[formStyles.input, styles.selected].join(" ")}>
          <span>
            {value.full_name} ({value.registration_number})
          </span>
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
    <FormField id={id} label={label} hint={hint} required={required}>
      <div className={styles.wrapper}>
        <input
          id={id}
          className={formStyles.input}
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="Buscar médico por nome ou matrícula"
          autoComplete="off"
          role="combobox"
          aria-expanded={showResults}
          aria-controls={`${id}-results`}
          aria-describedby={fieldDescribedBy(id, undefined, hint)}
          required={required}
        />

        {showResults && (
          <ul id={`${id}-results`} className={styles.results} role="listbox">
            {isLoading && <li className={styles.resultItemMuted}>Carregando médicos...</li>}
            {isError && (
              <li className={styles.resultItemMuted} role="alert">
                Não foi possível carregar os médicos cadastrados agora.
              </li>
            )}
            {!isLoading && !isError && matches.length === 0 && (
              <li className={styles.resultItemMuted}>Nenhum médico ativo encontrado.</li>
            )}
            {!isLoading &&
              !isError &&
              matches.map((employee) => (
                <li key={employee.id}>
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
                    {employee.full_name} ({employee.registration_number})
                  </button>
                </li>
              ))}
          </ul>
        )}
      </div>
    </FormField>
  );
}
