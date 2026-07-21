"""Teste de carga leve contra uma API do SentinelHealth em execucao (item 16).

NAO substitui um teste de carga completo em ambiente de homologacao (secao
7 do escopo: "volume simultaneo" e limites numericos ainda precisam ser
definidos e validados contra infraestrutura real, incluindo workers e
banco gerenciado). E um instrumento inicial, self-contained (so usa
`httpx`, ja uma dependencia de dev), para: (1) detectar regressao grosseira
de latencia/erro em CI ou localmente sem subir ferramenta externa
(k6/Locust/JMeter), e (2) servir de base para o teste de carga real, que
devera rodar contra homologation com volumes definidos numericamente antes
da entrada em producao (ver docs/governance/PLANO_RESPOSTA_INCIDENTES.md e
ESCOPO_PROJETO.md secao 7).

Cobre dois cenarios, cada um com concorrencia e duracao configuraveis:

  * `health`: GET /health repetido - mede o piso de latencia da API sem
    tocar banco/regras/IA (utilizacao pura de rede+ASGI).
  * `patients-list`: GET /patients (paginado) autenticado com um usuario de
    desenvolvimento - mede o caminho comum com banco+RBAC+isolamento por
    tenant.

Uso:
    uv run python -m scripts.load_test --scenario health --concurrency 20 --duration 10
    uv run python -m scripts.load_test --scenario patients-list --subject dev-medico

Requer a API rodando (`make dev` ou `uvicorn app.main:app`) e, para o
cenario `patients-list`, os usuarios de desenvolvimento ja semeados
(`make seed-dev-data`).
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class ScenarioResult:
    latencies_ms: list[float] = field(default_factory=list)
    status_counts: dict[int, int] = field(default_factory=dict)
    errors: int = 0

    def record(self, status_code: int | None, latency_ms: float) -> None:
        self.latencies_ms.append(latency_ms)
        if status_code is None:
            self.errors += 1
        else:
            self.status_counts[status_code] = self.status_counts.get(status_code, 0) + 1


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * p))
    return ordered[index]


async def _worker(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    headers: dict,
    stop_at: float,
    result: ScenarioResult,
) -> None:
    while time.monotonic() < stop_at:
        started = time.monotonic()
        try:
            response = await client.request(method, path, headers=headers)
            status_code: int | None = response.status_code
        except httpx.HTTPError:
            status_code = None
        latency_ms = (time.monotonic() - started) * 1000
        result.record(status_code, latency_ms)


async def run_scenario(
    *,
    base_url: str,
    method: str,
    path: str,
    headers: dict,
    concurrency: int,
    duration_seconds: float,
) -> ScenarioResult:
    result = ScenarioResult()
    stop_at = time.monotonic() + duration_seconds
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        await asyncio.gather(
            *[_worker(client, method, path, headers, stop_at, result) for _ in range(concurrency)]
        )
    return result


def _print_report(scenario: str, concurrency: int, duration: float, result: ScenarioResult) -> None:
    total = len(result.latencies_ms)
    throughput = total / duration if duration else 0.0
    error_rate = (result.errors / total * 100) if total else 0.0

    print(f"\n=== {scenario} (concorrencia={concurrency}, duracao={duration:.0f}s) ===")
    print(f"Total de requisicoes: {total}")
    print(f"Vazao: {throughput:.1f} req/s")
    print(f"Taxa de erro (conexao/timeout): {error_rate:.2f}%")
    print("Codigos de status:")
    for status_code, count in sorted(result.status_counts.items()):
        print(f"  {status_code}: {count}")
    print("Latencia (ms):")
    print(f"  p50: {_percentile(result.latencies_ms, 0.50):.1f}")
    print(f"  p95: {_percentile(result.latencies_ms, 0.95):.1f}")
    print(f"  p99: {_percentile(result.latencies_ms, 0.99):.1f}")
    print(f"  max: {max(result.latencies_ms, default=0.0):.1f}")
    if result.latencies_ms:
        print(f"  media: {statistics.mean(result.latencies_ms):.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--scenario", choices=["health", "patients-list"], default="health")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--duration", type=float, default=10.0, help="segundos")
    parser.add_argument(
        "--subject",
        default="dev-medico",
        help="X-Dev-Subject usado para cenarios autenticados (ver make seed-dev-data)",
    )
    args = parser.parse_args()

    if args.scenario == "health":
        method, path, headers = "GET", "/health", {}
    else:
        method, path, headers = (
            "GET",
            "/patients?page=1&page_size=20",
            {"X-Dev-Subject": args.subject},
        )

    result = asyncio.run(
        run_scenario(
            base_url=args.base_url,
            method=method,
            path=path,
            headers=headers,
            concurrency=args.concurrency,
            duration_seconds=args.duration,
        )
    )
    _print_report(args.scenario, args.concurrency, args.duration, result)


if __name__ == "__main__":
    main()
