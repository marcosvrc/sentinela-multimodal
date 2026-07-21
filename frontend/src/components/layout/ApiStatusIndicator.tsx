import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/services/api/client";

/** Pequeno indicador de conectividade com a API, exibido na topbar. */
export function ApiStatusIndicator() {
  const query = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: 0,
  });

  const label = query.isSuccess
    ? "API conectada"
    : query.isError
      ? "API indisponivel"
      : "Verificando API...";
  const color = query.isSuccess
    ? "var(--risk-low)"
    : query.isError
      ? "var(--risk-high)"
      : "var(--color-text-muted)";

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color }}>
      <span
        aria-hidden="true"
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
          display: "inline-block",
        }}
      />
      {label}
    </span>
  );
}
