# SentinelHealth

Sistema de apoio a analises clinicas com inteligencia artificial multimodal.
**Nao realiza diagnostico autonomo** e depende de revisao profissional antes
de qualquer relatorio se tornar definitivo. Ver o escopo completo em
[`docs/ESCOPO_PROJETO.md`](docs/ESCOPO_PROJETO.md).

## Estado atual

O sistema esta funcional de ponta a ponta em ambiente de desenvolvimento:
cadastro de pacientes e unidades assistenciais, upload multimodal (audio,
video, imagem, texto), motor de regras clinicas versionado, orquestrador
que processa cada analise por modalidade, consolidacao de risco (com LLM
opcional), geracao de laudo em PDF, auditoria imutavel e controle de acesso
(identidade local para dev, Cognito para homologacao/producao). Os
adaptadores de nuvem (OpenAI, AWS Transcribe/Rekognition, Azure Cognitive
Services, S3/SQS) sao plugaveis e comecam desligados — a aplicacao roda
100% local sem nenhuma credencial externa (ver `LOCAL` providers em
[`docs/MANUAL_EXECUCAO.md`](docs/MANUAL_EXECUCAO.md)).

A infraestrutura de nuvem (Terraform) e a base para os ambientes `dev`,
`homologation` e `production` ja existe em [`infra/`](infra/README.md);
o deploy real depende de valores especificos de cada conta AWS (ver
`terraform.tfvars.example` em cada ambiente).

## Estrutura do repositorio

```text
backend/     API FastAPI + workers (Python, uv, SQLAlchemy, Alembic)
frontend/    SPA React + TypeScript + Vite
infra/       Terraform (modules/ e environments/)
docs/        Escopo, especificacoes, ADRs e diagramas de arquitetura
compose.yaml Orquestracao local (Postgres, backend, frontend)
Makefile     Interface unica de comandos (tambem usada pelo CI/CD)
```

## Pre-requisitos

- Python 3.11 ou 3.12
- [`uv`](https://docs.astral.sh/uv/) instalado
- Node.js 22+ e npm
- Docker e Docker Compose

## Setup rapido

```bash
make setup       # instala dependencias de backend e frontend, cria .env
make compose-up  # sobe o PostgreSQL local
cd backend  && uv run alembic upgrade head   # aplica a migration inicial
cd backend  && uv run uvicorn app.main:app --reload   # API em :8000
cd frontend && npm run dev                             # SPA em :5173
```

Ou, de forma resumida:

```bash
make setup
make dev
```

Acesse `http://localhost:5173` — a pagina inicial confirma a conexao com
`GET /health` da API. A documentacao interativa da API fica em
`http://localhost:8000/docs`.

## Comandos principais

| Comando | Descricao |
| --- | --- |
| `make setup` | Instala dependencias (backend e frontend) |
| `make dev` | Sobe o Postgres via Compose e orienta a subir API/frontend |
| `make stop` | Derruba os containers do Compose |
| `make format` | Formata backend (ruff) e frontend (prettier) |
| `make lint` | Lint backend (ruff) e frontend (eslint) |
| `make typecheck` | Checagem de tipos backend (mypy) e frontend (tsc) |
| `make test` | Testes unitarios de backend e frontend (backend usa `sentinelhealth_test`, ver `make test-db-create`) |
| `make test-integration` | Testes de integracao (requer Postgres ativo) |
| `make test-db-create` | Cria o banco de teste `sentinelhealth_test` (idempotente, rode uma vez apos `compose-up`) |
| `make test-db-migrate` | Aplica as migrations no banco de teste |
| `make build` | Build das imagens Docker |
| `make check` | Validacao local equivalente ao gate de PR (lint+typecheck+test) |
| `make migrate` | Aplica migrations pendentes |
| `make migration name="..."` | Cria uma nova migration Alembic |
| `make rules-validate` | Valida os arquivos YAML de regras clinicas contra o schema |
| `make rules-seed` | Carrega as regras clinicas no banco (idempotente) |
| `make codegen` | Gera `frontend/src/types/enums.generated.ts` a partir dos enums Python |
| `make export-openapi` | Gera o snapshot `docs/contracts/openapi.json` |
| `make compose-up` / `make compose-down` | Sobe/derruba os servicos do Compose |
| `make tf-fmt` | Formata os arquivos Terraform de todos os modulos/ambientes |
| `make tf-validate env=<ambiente>` | Valida a sintaxe/schema Terraform de um ambiente |
| `make tf-plan env=<ambiente>` | Gera o plano Terraform de um ambiente |
| `make tf-apply env=<ambiente>` | Aplica as mudancas Terraform de um ambiente |

## Resolucao de problemas comuns

**`uv sync` falha ao baixar o interpretador Python.**
Garanta acesso a rede ou instale localmente uma versao compativel
(3.11 ou 3.12) e rode `uv python pin 3.11`.

**API nao conecta ao Postgres.**
Confirme que `make compose-up` esta rodando (`docker compose ps`) e que
`DATABASE_URL` no `.env` aponta para `localhost:5432` (fora de containers)
ou `postgres:5432` (dentro do compose).

**Frontend nao encontra a API (`ERR_CONNECTION_REFUSED`).**
Verifique `VITE_API_BASE_URL` no `.env`/`.env.example` e se a API esta
respondendo em `GET /health`.

**Migration falha em banco ja existente.**
As migrations sao aditivas e idempotentes por design; se o banco local
ficou inconsistente durante desenvolvimento, use `make compose-down` para
remover o volume e recriar do zero com `make compose-up`.

## Documentacao

- [`docs/ESCOPO_PROJETO.md`](docs/ESCOPO_PROJETO.md) — escopo completo do produto
- [`docs/ESPECIFICACAO_FRONTEND.md`](docs/ESPECIFICACAO_FRONTEND.md) — telas, design system e contratos de frontend
- [`docs/CLASSIFICACAO_DADOS_CLINICOS.md`](docs/CLASSIFICACAO_DADOS_CLINICOS.md) — base de conhecimento clinica (referencia preliminar)
- [`docs/adr/`](docs/adr/) — decisoes arquiteturais (ADRs) P0
- [`docs/architecture/`](docs/architecture/) — diagramas Mermaid (contexto, containers, implantacao, sequencias, ER)

## Seguranca e dados

Nenhum dado real de paciente deve ser usado neste repositorio. Somente
dados sinteticos sao permitidos fora de producao (ver ESCOPO_PROJETO.md
secao 8.2 e o gate de uso com dados reais, secao 12.2). Nao commite `.env`,
`terraform.tfvars`, chaves de API ou credenciais AWS/Azure — o `.gitignore`
da raiz ja bloqueia esses arquivos (e o estado/lock do Terraform, o
`.venv`, `node_modules` e a midia local gerada em `backend/.local-media`),
mas a revisão de PR também verifica isso.
