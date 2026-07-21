import type { InputHTMLAttributes } from "react";
import formStyles from "./FormField.module.css";
import { FormField, fieldDescribedBy } from "./FormField";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label: string;
  error?: string;
  hint?: string;
}

export function TextField({
  id,
  label,
  error,
  hint,
  required,
  className,
  ...props
}: TextFieldProps) {
  return (
    <FormField id={id} label={label} error={error} hint={hint} required={required}>
      <input
        id={id}
        className={[formStyles.input, error && formStyles.inputError, className]
          .filter(Boolean)
          .join(" ")}
        aria-invalid={Boolean(error)}
        aria-describedby={fieldDescribedBy(id, error, hint)}
        required={required}
        {...props}
      />
    </FormField>
  );
}
