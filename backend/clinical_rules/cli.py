"""CLI de validacao e carga (seed) das regras clinicas versionadas.

Escopo do scaffold: valida os arquivos YAML em `clinical_rules/seeds/`
contra o JSON Schema `clinical_rule_set.schema.json` e permite a carga
idempotente em uma tabela de referencia. A execucao do motor de regras
(avaliacao de `when` sobre dados reais) pertence ao modulo funcional
`rules_engine` e nao faz parte deste scaffold.

Uso:
    uv run python -m clinical_rules.cli validate
    uv run python -m clinical_rules.cli seed
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from clinical_rules.seeding import SeedOutcome, decide, default_action_descriptions

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schemas" / "clinical_rule_set.schema.json"
SEEDS_DIR = BASE_DIR / "seeds"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_all_seed_files() -> list[tuple[Path, dict]]:
    return [
        (path, yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(SEEDS_DIR.glob("*.yaml"))
    ]


def validate() -> int:
    schema = _load_schema()
    validator = Draft202012Validator(schema)
    exit_code = 0

    seed_files = _load_all_seed_files()
    if not seed_files:
        print("Nenhum arquivo de regra encontrado em clinical_rules/seeds/.")
        return 0

    for path, content in seed_files:
        errors = sorted(validator.iter_errors(content), key=lambda e: e.path)
        if errors:
            exit_code = 1
            print(f"[INVALIDO] {path.name}")
            for error in errors:
                location = "/".join(str(p) for p in error.path) or "(raiz)"
                print(f"  - {location}: {error.message}")
        else:
            print(f"[OK] {path.name} ({content['code']} v{content['version']})")

    return exit_code


def seed() -> int:
    """Carrega os conjuntos de regras validados no PostgreSQL, de forma idempotente.

    Requer uma conexao valida com o banco (ver app.core.config.Settings).
    Cada conjunto e tratado como uma unidade transacional: falha em um nao
    impede a carga dos demais, mas o exit code final reflete qualquer
    conflito encontrado.
    """
    # Import tardio: cli.py e usado tambem por `validate`, que nao precisa
    # de banco de dados nem de todo o app FastAPI carregado.
    from sqlalchemy.orm import Session

    from app.core.db import SessionLocal
    from app.rules_engine import models

    if validate() != 0:
        print("Corrija os erros de validacao antes de rodar o seed.")
        return 1

    seed_files = _load_all_seed_files()
    exit_code = 0

    session: Session = SessionLocal()
    try:
        risk_level_meanings = dict(session.query(models.RiskLevel.code, models.RiskLevel.meaning))
        if not risk_level_meanings:
            print(
                "[ERRO] Tabela risk_levels vazia. Rode 'make migrate' antes do seed "
                "(a migration 0001 ja carrega os 6 niveis canonicos)."
            )
            return 1

        for path, content in seed_files:
            existing = (
                session.query(models.ClinicalRuleSet)
                .filter_by(code=content["code"], version=content["version"])
                .one_or_none()
            )
            decision = decide(content, existing.content_hash if existing else None)

            if decision.outcome == SeedOutcome.SKIPPED_UNCHANGED:
                print(f"[SEM MUDANCA] {path.name} ({decision.code} v{decision.version})")
                continue

            if decision.outcome == SeedOutcome.CONFLICT:
                exit_code = 1
                print(
                    f"[CONFLITO] {path.name}: a versao {decision.code} v{decision.version} "
                    "ja existe no banco com conteudo diferente. Versoes sao imutaveis "
                    "apos publicadas - publique uma nova versao em vez de editar esta."
                )
                continue

            effective_to_raw = content.get("effective_to")
            rule_set = models.ClinicalRuleSet(
                code=content["code"],
                version=content["version"],
                population=content["population"],
                status=content["status"],
                effective_from=date.fromisoformat(content["effective_from"]),
                effective_to=date.fromisoformat(effective_to_raw) if effective_to_raw else None,
                required_inputs=content.get("required_inputs", []),
                exclusions=content.get("exclusions", []),
                content_hash=decision.new_hash,
            )
            session.add(rule_set)

            source = content["source"]
            session.add(
                models.ClinicalRuleSource(
                    rule_set=rule_set,
                    reference=source["reference"],
                    approved_by=source["approved_by"],
                )
            )

            action_descriptions = default_action_descriptions(content, risk_level_meanings)
            for risk_level, description in action_descriptions.items():
                session.add(
                    models.ClinicalRuleAction(
                        rule_set=rule_set,
                        risk_level=risk_level,
                        description=description,
                    )
                )

            for position, rule in enumerate(content["rules"]):
                clinical_rule = models.ClinicalRule(
                    rule_set=rule_set,
                    rule_key=rule["id"],
                    risk_level=rule["risk_level"],
                    classification_label=rule["classification_label"],
                    notes=rule.get("notes"),
                    position=position,
                )
                session.add(clinical_rule)
                session.add(
                    models.ClinicalRuleCondition(
                        rule=clinical_rule,
                        expression=rule["when"],
                    )
                )

            print(f"[CARREGADO] {path.name} ({decision.code} v{decision.version})")

        if exit_code == 0:
            session.commit()
            print(
                "Lembrete: conjuntos carregados ficam em status 'draft' e NAO sao "
                "considerados vigentes pelo motor de regras ate serem publicados por um "
                "administrador clinico (POST /admin/clinical-rule-sets/{id}/publish - "
                "item 5.3 do escopo)."
            )
        else:
            session.rollback()
            print("Seed interrompido por conflito(s). Nenhuma alteracao foi salva.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="Valida os arquivos de regras contra o schema")
    subparsers.add_parser("seed", help="Carrega as regras no banco (idempotente)")

    args = parser.parse_args()
    if args.command == "validate":
        return validate()
    if args.command == "seed":
        return seed()
    return 1


if __name__ == "__main__":
    sys.exit(main())
