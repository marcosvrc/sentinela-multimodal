/**
 * Sessao de desenvolvimento (identidade local).
 *
 * TEMPORARIO: ate o modulo de Identidade (Cognito) existir, o frontend nao
 * tem sessao autenticada real. O usuario ativo e escolhido manualmente por
 * `external_subject` (gerado por `make seed-dev-data`) e guardado no
 * navegador. Isto espelha `app.core.security.get_current_user` no backend -
 * a instituicao e o papel do usuario NUNCA sao escolhidos aqui: ambos sao
 * resolvidos pelo backend a partir do `subject`, nunca aceitos do cliente.
 * Este hook e o banner serao substituidos juntos quando a autenticacao
 * real existir.
 */
import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "sentinelhealth.dev_subject";

export function useDevSession() {
  const [subject, setSubjectState] = useState<string | null>(() =>
    window.localStorage.getItem(STORAGE_KEY),
  );

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY) {
        setSubjectState(event.newValue);
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const setSubject = useCallback((value: string) => {
    window.localStorage.setItem(STORAGE_KEY, value);
    setSubjectState(value);
  }, []);

  const clearSubject = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY);
    setSubjectState(null);
  }, []);

  return { subject, setSubject, clearSubject };
}
