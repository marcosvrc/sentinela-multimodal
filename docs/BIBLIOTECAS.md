# Bibliotecas e Versões — SentinelHealth

Versões efetivamente resolvidas nos lockfiles do projeto
(`backend/uv.lock` e `frontend/package-lock.json`) na data desta
atualização. Os lockfiles são a fonte de verdade — em caso de
divergência com este documento, prevalece o lockfile.

## Runtime

| Camada | Tecnologia | Versão exigida | Observação |
| --- | --- | --- | --- |
| Backend | Python | `>=3.11,<3.13` | Fixado em `backend/pyproject.toml` (`requires-python`); gerenciado pelo `uv` |
| Backend | `uv` | atual | Instala o Python e sincroniza as dependências |
| Frontend | Node.js | `22+` | Mesma versão usada na imagem Docker (`node:22-slim`) |
| Frontend | npm | atual (vem com o Node) | — |
| Banco de dados | PostgreSQL | `16` (imagem `postgres:16-alpine`) | Único banco usado; sem dependência de extensões específicas |
| Containerização | Docker / Docker Compose | atual | Compose v2 (`docker compose`, sem hífen) |
| Visão computacional (opcional) | `ffmpeg` | atual | Só necessário para vídeo real (amostragem de quadros) |

## Backend (`backend/pyproject.toml` / `backend/uv.lock`)

### Dependências de produção

| Biblioteca | Versão | Uso |
| --- | --- | --- |
| `fastapi` | 0.139.0 | Framework HTTP da API |
| `uvicorn[standard]` | 0.51.0 | Servidor ASGI |
| `pydantic` | 2.13.4 | Validação de dados e schemas |
| `pydantic-settings` | 2.14.2 | Configuração via `.env`/variáveis de ambiente |
| `sqlalchemy` | 2.0.51 | ORM e camada de acesso a dados |
| `alembic` | 1.18.5 | Migrations do banco |
| `psycopg[binary]` | 3.3.4 | Driver PostgreSQL |
| `python-json-logger` | 4.1.0 | Log estruturado em JSON |
| `pyyaml` | 6.0.3 | Leitura dos YAML de regras clínicas |
| `jsonschema` | 4.26.0 | Validação das regras clínicas contra o schema |
| `email-validator` | 2.3.0 | Validação de e-mail (Pydantic) |
| `openai` | 2.45.0 | Adaptador de LLM (consolidação de risco / apoio clínico) |
| `reportlab` | 5.0.0 | Geração do PDF do relatório |
| `Pillow` | 12.3.0 | Leitura de metadados/dimensões de imagem |
| `PyJWT[crypto]` | 2.13.0 | Tokens assinados (URLs de upload pré-assinadas) |
| `cachetools` | 7.1.4 | Cache em memória (ex.: configuração/feature flags) |
| `slowapi` | 0.1.10 | Rate limiting por IP |
| `httpx` | 0.28.1 | Cliente HTTP (chamadas aos adaptadores Azure) |

### Dependências de desenvolvimento (`dependency-groups.dev`)

| Biblioteca | Versão | Uso |
| --- | --- | --- |
| `pytest` | 9.1.1 | Framework de testes |
| `pytest-cov` | 7.1.0 | Cobertura de testes |
| `httpx` | 0.28.1 | Cliente usado pelo `TestClient` do FastAPI |
| `ruff` | 0.15.21 | Lint e formatação |
| `mypy` | 2.2.0 | Checagem de tipos estática |

### Grupo opcional `vision` (worker de vídeo)

Instalado só com `uv sync --group vision`; nunca faz parte da imagem da
API nem dos demais workers (áudio, imagem, relatório, orquestrador) — ver
[`docs/MANUAL_INSTALACAO.md`](MANUAL_INSTALACAO.md) seção 10.

| Biblioteca | Versão | Uso |
| --- | --- | --- |
| `ultralytics` | 8.4.92 | YOLOv8 (detecção de objetos em quadros de vídeo) |
| `numpy` | 2.5.1 | Suporte numérico para o pipeline de visão |

O binário do **OpenPose** (estimativa de pose articulada) não é
distribuído via `pip` — precisa ser compilado separadamente e disponível
no `PATH` (ver seção 10 do manual de instalação).

## Frontend (`frontend/package.json` / `frontend/package-lock.json`)

### Dependências de produção

| Biblioteca | Versão | Uso |
| --- | --- | --- |
| `react` | 18.3.1 | Biblioteca de UI |
| `react-dom` | 18.3.1 | Renderização DOM do React |
| `react-router-dom` | 6.30.4 | Roteamento SPA |
| `@tanstack/react-query` | 5.101.2 | Cache/estado de servidor, mutations, invalidação |
| `lucide-react` | 0.468.0 | Ícones |
| `recharts` | 3.9.2 | Gráficos (dashboard) |
| `@fontsource/inter` | 5.1.0 | Fonte tipográfica (Inter) |
| `html2canvas` | 1.4.1 | Captura de elementos para exportação |
| `jspdf` | 4.2.1 | Geração de PDF no cliente (auxiliar) |

### Dependências de desenvolvimento

| Biblioteca | Versão | Uso |
| --- | --- | --- |
| `typescript` | 5.9.3 | Compilador/checagem de tipos |
| `vite` | 5.4.21 | Build e dev server |
| `@vitejs/plugin-react` | 4.7.0 | Suporte a React no Vite |
| `vitest` | 2.1.9 | Framework de testes |
| `jsdom` | 25.0.1 | Ambiente DOM para os testes |
| `@testing-library/react` | 16.3.2 | Testes de componentes |
| `@testing-library/jest-dom` | 6.9.1 | Matchers de DOM para os testes |
| `eslint` | 9.39.5 | Lint |
| `@typescript-eslint/eslint-plugin` / `parser` | 8.15.0 | Regras de lint para TypeScript |
| `eslint-plugin-react-hooks` | 5.0.0 | Regras de lint para hooks do React |
| `prettier` | 3.9.5 | Formatação de código |
| `@types/react`, `@types/react-dom`, `@types/node` | 18.3.x / 18.3.x / 26.1.1 | Tipos para bibliotecas sem tipagem própria |

## Imagens base (Docker)

| Serviço | Imagem base | Versão |
| --- | --- | --- |
| Backend/worker | `python` | `3.11-slim` |
| Banco de dados | `postgres` | `16-alpine` |
| Frontend (build) | `node` | `22-slim` |
| Frontend (runtime) | `nginx` | `1.27-alpine` |
| Gerenciador de pacotes Python | `ghcr.io/astral-sh/uv` | `latest` (copiado como binário estático no build) |

## Como verificar as versões você mesmo

```bash
# Backend - versão exata resolvida de qualquer pacote
cd backend && uv run python -c "import fastapi; print(fastapi.__version__)"

# Ou consulte diretamente o lockfile (fonte de verdade)
grep -A1 'name = "fastapi"' backend/uv.lock

# Frontend - versão exata resolvida
cd frontend && npm ls react react-dom --depth=0
```

## Documentação relacionada

- [`README.md`](../README.md) — visão geral do repositório
- [`docs/ARQUITETURA.md`](ARQUITETURA.md) — arquitetura e decisões estruturais
- [`docs/MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) — passo a passo para rodar o projeto
