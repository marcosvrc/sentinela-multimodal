"""Exporta o snapshot versionado do contrato OpenAPI da API.

Uso:
    uv run python -m scripts.export_openapi

Escreve docs/contracts/openapi.json. O snapshot e versionado no repositorio
para permitir revisao de diffs de contrato em pull requests (ESCOPO_PROJETO.md
secao 12.1.4: "politica de versionamento e compatibilidade dos contratos").
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "contracts" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Escrito: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
