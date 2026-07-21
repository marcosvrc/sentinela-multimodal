import { useEffect, useState } from "react";

/**
 * Retorna `value` com atraso (debounce), para campos de busca em tempo
 * real (ex.: pacientes por nome/prontuario) sem disparar uma requisicao a
 * cada tecla digitada.
 */
export function useDebouncedValue<T>(value: T, delayMs = 350): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timeoutId);
  }, [value, delayMs]);

  return debounced;
}
