"""Gera enums TypeScript a partir de app.core.enums (fonte unica de verdade).

ESCOPO_PROJETO.md secao 12.1.4: "Enums e schemas compartilhados deverao
possuir uma unica fonte de verdade ou geracao automatizada. O frontend nao
duplicara manualmente regras de transicao ou classificacao do backend."

Uso:
    uv run python -m scripts.export_enums

Escreve frontend/src/types/enums.generated.ts. O arquivo gerado nao deve
ser editado manualmente (cabecalho de aviso incluido automaticamente).
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from app.core import enums as enums_module
from app.core.enums import ANALYSIS_STATUS_TRANSITIONS, AnalysisStatus

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend"
    / "src"
    / "types"
    / "enums.generated.ts"
)

HEADER = """// ARQUIVO GERADO AUTOMATICAMENTE - NAO EDITAR.
// Fonte: backend/app/core/enums.py
// Gerar novamente com: make codegen
"""


def _enum_classes() -> list[type[Enum]]:
    classes = []
    for name in dir(enums_module):
        value = getattr(enums_module, name)
        if isinstance(value, type) and issubclass(value, Enum) and value is not Enum:
            classes.append(value)
    return classes


def _render_enum(enum_cls: type[Enum]) -> str:
    lines = [f"export enum {enum_cls.__name__} {{"]
    for member in enum_cls:
        value = member.value
        rendered_value = f'"{value}"' if isinstance(value, str) else str(value)
        lines.append(f"  {member.name} = {rendered_value},")
    lines.append("}")
    return "\n".join(lines)


def _render_transitions() -> str:
    lines = [
        "export const ANALYSIS_STATUS_TRANSITIONS: Record<AnalysisStatus, AnalysisStatus[]> = {"
    ]
    for status in AnalysisStatus:
        targets = ANALYSIS_STATUS_TRANSITIONS.get(status, ())
        targets_ts = ", ".join(f"AnalysisStatus.{target.name}" for target in targets)
        lines.append(f"  [AnalysisStatus.{status.name}]: [{targets_ts}],")
    lines.append("};")
    return "\n".join(lines)


def generate() -> str:
    parts = [HEADER]
    for enum_cls in sorted(_enum_classes(), key=lambda c: c.__name__):
        parts.append(_render_enum(enum_cls))
        parts.append("")
    parts.append(_render_transitions())
    parts.append("")
    return "\n".join(parts)


def main() -> None:
    content = generate()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Escrito: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
