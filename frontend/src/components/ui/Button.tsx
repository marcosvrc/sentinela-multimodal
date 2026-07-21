import type { ButtonHTMLAttributes } from "react";
import styles from "./Button.module.css";

type Variant = "primary" | "secondary" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ variant = "primary", className, ...props }: ButtonProps) {
  const variantClass = styles[variant] ?? styles.primary;
  return (
    <button
      className={[styles.button, variantClass, className].filter(Boolean).join(" ")}
      {...props}
    />
  );
}
