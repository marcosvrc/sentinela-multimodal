import type { ComponentProps } from "react";
import { Link } from "react-router-dom";
import styles from "./Button.module.css";

type Variant = "primary" | "secondary" | "danger";

interface LinkButtonProps extends ComponentProps<typeof Link> {
  variant?: Variant;
}

/** Mesma aparencia do Button, mas navega via react-router (nao envia POST). */
export function LinkButton({ variant = "primary", className, ...props }: LinkButtonProps) {
  const variantClass = styles[variant] ?? styles.primary;
  return (
    <Link
      className={[styles.button, variantClass, className].filter(Boolean).join(" ")}
      {...props}
    />
  );
}
