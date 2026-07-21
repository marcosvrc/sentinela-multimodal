import { useState } from "react";
import { FlaskConical } from "lucide-react";
import { useDevSession } from "@/hooks/useDevSession";
import { Button } from "@/components/ui/Button";
import styles from "./InstitutionBanner.module.css";

/**
 * Banner TEMPORARIO para selecionar o usuario de desenvolvimento ativo.
 *
 * Substitui a sessao autenticada que normalmente forneceria identidade,
 * instituicao e papel (ver app/core/security.py::get_current_user no
 * backend). Sera removido quando a Identidade (Cognito) existir; ate la,
 * rode `make seed-dev-data` no backend para obter os `external_subject`
 * validos (um por papel: medico, enfermeiro, administrador tecnico,
 * administrador clinico, auditor).
 */
export function DevSessionBanner() {
  const { subject, setSubject, clearSubject } = useDevSession();
  const [draft, setDraft] = useState("");

  if (subject) {
    return (
      <div className={styles.banner}>
        <span className={styles.message}>
          <FlaskConical size={15} strokeWidth={2} aria-hidden="true" />
          Usuario de desenvolvimento ativo: <code>{subject}</code>
        </span>
        <Button variant="secondary" onClick={clearSubject}>
          Trocar
        </Button>
      </div>
    );
  }

  return (
    <div className={styles.banner} role="alert">
      <span className={styles.message}>
        <FlaskConical size={15} strokeWidth={2} aria-hidden="true" />
        Nenhum usuario de desenvolvimento configurado. Rode <code>make seed-dev-data</code> no
        backend e cole abaixo o `external_subject` de um dos usuarios impressos (ex:
        <code>dev-medico</code>).
      </span>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          if (draft.trim()) setSubject(draft.trim());
        }}
      >
        <input
          className={styles.input}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="external_subject (ex: dev-medico)"
          aria-label="Identificador do usuario de desenvolvimento"
        />
        <Button type="submit">Usar</Button>
      </form>
    </div>
  );
}
