# Interface unica de comandos do SentinelHealth.
# Usada tanto localmente quanto pelo CI/CD (ver ESCOPO_PROJETO.md secao 12.1.3).
# A logica das verificacoes vive aqui, nao apenas no YAML do GitHub Actions.

.PHONY: setup dev stop format lint typecheck test test-integration load-test build check \
        migrate migration rules-validate rules-seed compose-up compose-down \
        codegen export-openapi seed-dev-data seed-care-units seed-employees seed-patients worker \
        test-db-create test-db-migrate

BACKEND := backend
FRONTEND := frontend

# Banco de dados usado pelos testes (backend/tests) - isolado do banco de
# desenvolvimento (DATABASE_URL do .env) para que dados criados por teste
# nunca apareçam nas telas da aplicação em execução localmente. Mesmo
# Postgres do compose, banco diferente (padrão: sentinelhealth_test).
# Sobrescreva com `make test TEST_DATABASE_URL=postgresql+psycopg://...`
# se preferir outro banco/host.
TEST_DATABASE_URL ?= postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinelhealth_test

## Instala dependencias de backend e frontend
setup:
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm install
	@test -f .env || cp .env.example .env
	@echo "Setup concluido. Ajuste o .env se necessario e rode 'make compose-up'."

## Sobe Postgres via Compose e inicia API + frontend em modo desenvolvimento
dev: compose-up
	@echo "Postgres disponivel em localhost:5432."
	@echo "Em terminais separados, rode:"
	@echo "  cd backend  && uv run uvicorn app.main:app --reload"
	@echo "  cd frontend && npm run dev"

## Para os containers do Compose
stop:
	docker compose -f compose.yaml down

## Formata backend e frontend
format:
	cd $(BACKEND) && uv run ruff format .
	cd $(FRONTEND) && npm run format

## Lint backend e frontend
lint:
	cd $(BACKEND) && uv run ruff check .
	cd $(FRONTEND) && npm run lint

## Checagem de tipos backend e frontend
typecheck:
	cd $(BACKEND) && uv run mypy app
	cd $(FRONTEND) && npm run typecheck

## Testes unitarios backend e frontend.
## Backend usa TEST_DATABASE_URL (banco Postgres separado do de
## desenvolvimento, ver test-db-create/test-db-migrate) para nunca gravar
## dados de teste (ex.: clinical_rule_sets com codigo "acs-spo2-<uuid>") no
## banco usado pela API/frontend em modo dev.
test:
	cd $(BACKEND) && DATABASE_URL="$(TEST_DATABASE_URL)" uv run pytest
	cd $(FRONTEND) && npm run test

## Testes de integracao (dependem de Postgres ativo via compose-up)
test-integration:
	cd $(BACKEND) && DATABASE_URL="$(TEST_DATABASE_URL)" uv run pytest -m integration

## Cria o banco de dados de teste (idempotente) no mesmo Postgres do
## compose - roda uma vez apos compose-up, antes do primeiro `make test`.
test-db-create:
	docker compose -f compose.yaml exec -T postgres psql -U $${POSTGRES_USER:-sentinel} -d postgres \
		-tc "SELECT 1 FROM pg_database WHERE datname = '$${POSTGRES_TEST_DB:-sentinelhealth_test}'" \
		| grep -q 1 || docker compose -f compose.yaml exec -T postgres \
		createdb -U $${POSTGRES_USER:-sentinel} $${POSTGRES_TEST_DB:-sentinelhealth_test}

## Aplica as migrations no banco de teste
test-db-migrate:
	cd $(BACKEND) && DATABASE_URL="$(TEST_DATABASE_URL)" uv run alembic upgrade head

## Teste de carga leve contra uma API em execucao (uso: make load-test scenario=health)
## Nao substitui um teste de carga completo em homologacao (ver ESCOPO_PROJETO.md secao 7).
load-test:
	cd $(BACKEND) && uv run python -m scripts.load_test --scenario $(or $(scenario),health)

## Build das imagens de container
build:
	docker compose -f compose.yaml build

## Validacao local equivalente ao gate de pull request
check: lint typecheck test rules-validate

## Gera os tipos TypeScript compartilhados a partir dos enums Python
## (docs/contracts/README.md - fonte unica de verdade dos enums)
codegen:
	cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.export_enums

## Exporta o snapshot versionado do contrato OpenAPI para docs/contracts/openapi.json
export-openapi:
	cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.export_openapi

## Aplica as migrations pendentes
migrate:
	cd $(BACKEND) && uv run alembic upgrade head

## Cria uma nova migration (uso: make migration name="descricao")
migration:
	cd $(BACKEND) && uv run alembic revision -m "$(name)"

## Valida os arquivos YAML/JSON de regras clinicas contra o schema
rules-validate:
	cd $(BACKEND) && uv run python -m clinical_rules.cli validate

## Carrega as regras clinicas versionadas no banco (idempotente)
rules-seed:
	cd $(BACKEND) && uv run python -m clinical_rules.cli seed

## Cria (ou reaproveita) uma instituicao de desenvolvimento e imprime o ID.
## TEMPORARIO ate existir cadastro real de instituicoes/identidade.
seed-dev-data:
	cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.seed_dev_data

## Popula as 25 unidades assistenciais padrao (idempotente)
seed-care-units:
	cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.seed_care_units

## Popula 25 funcionarios ficticios com especialidade e papel de acesso aleatorios (idempotente)
seed-employees:
	cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.seed_employees

## Popula 50 pacientes ficticios com 10 observacoes de cada sinal vital (idempotente)
seed-patients:
	cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.seed_patients

## Roda uma iteracao do worker do orquestrador (item 10) e sai
worker:
	cd $(BACKEND) && PYTHONPATH=. uv run python -m scripts.run_orchestrator_worker --once

## Sobe os servicos definidos no compose.yaml
compose-up:
	docker compose -f compose.yaml up -d postgres

## Derruba os servicos definidos no compose.yaml
compose-down:
	docker compose -f compose.yaml down -v
