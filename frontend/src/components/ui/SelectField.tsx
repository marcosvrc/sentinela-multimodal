import type { SelectHTMLAttributes } from "react";
import formStyles from "./FormField.module.css";
import { FormField, fieldDescribedBy } from "./FormField";

interface Option {
  value: string;
  label: string;
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  id: string;
  label: string;
  options: Option[];
  error?: string;
  hint?: string;
}

export function SelectField({
  id,
  label,
  options,
  error,
  hint,
  required,
  className,
  ...props
}: SelectFieldProps) {
  return (
    <FormField id={id} label={label} error={error} hint={hint} required={required}>
      <select
        id={id}
        className={[formStyles.input, error && formStyles.inputError, className]
          .filter(Boolean)
          .join(" ")}
        aria-invalid={Boolean(error)}
        aria-describedby={fieldDescribedBy(id, error, hint)}
        required={required}
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FormField>
  );
}
