# Estrutura do Projeto — SentinelHealth

Referência de onde encontrar cada parte do código e da documentação.
Para a arquitetura (o "porquê" da organização), ver
[`ARQUITETURA.md`](ARQUITETURA.md).

## Visão geral da raiz

```text
sentinela-multimodal/
├── backend/            API FastAPI + workers (Python, uv)
├── frontend/            SPA React + TypeScript (Vite)
├── docs/                Documentação, ADRs e diagramas
├── compose.yaml         Orquestração local (Postgres, backend, worker, frontend)
├── compose.aws-dev.yaml (nao existe mais - projeto e Azure-only)
├── Makefile             Interface unica de comandos (tambem usada pelo CI/CD)
├── .env.example         Modelo de variaveis de ambiente
└── README.md            Ponto de entrada da documentacao
```

## Backend (`backend/`)

```text
backend/
├── app/                     Código de produção da API e dos workers
│   ├── main.py              Bootstrap da aplicação FastAPI
│   ├── core/                 Configuração, enums, segurança/RBAC, rate limiting, erros
│   ├── identity/              Usuários, papéis, sessão (adaptador local X-Dev-Subject)
│   ├── patients/               Cadastro de pacientes
│   ├── observations/            Observações clínicas (sinais vitais) e validação de qualidade
│   ├── anomaly_detection/        Alertas de anomalia em série temporal
│   ├── media/                     Upload de mídia e estado das análises
│   ├── processors/                 Processadores por modalidade (áudio/vídeo/imagem/texto)
│   ├── acoustics/                   Análise acústica DSP (sem nuvem)
│   ├── clinical_nlp/                 Extração de termos clínicos (NegEx/ConText)
│   ├── vision/                        Categorização heurística de imagem + guardrail de relevância clínica
│   ├── integrations/                   Adaptadores plugáveis (LLM, transcrição, visão, storage, fila...)
│   │   ├── llm/
│   │   ├── transcription/
│   │   ├── vision/
│   │   ├── image_recognition/
│   │   └── sentiment_analysis/
│   ├── rules_engine/                    Interpretador de expressões + avaliação de regras
│   ├── risk_consolidation/               Combina regras + solicita síntese ao LLM
│   ├── clinical_support/                  Apoio a análise clínica assistido por LLM (sob demanda)
│   ├── reports/                            Composição do relatório e geração de PDF
│   ├── review/                              Fluxo de revisão profissional
│   ├── orchestrator/                         Máquina de estados + worker que consome a fila
│   ├── feature_flags/                         Toggles em runtime (banco de dados)
│   ├── administration/                         CRUD de especialidades/funcionários/unidades/usuários
│   ├── audit/                                  Trilha de auditoria append-only
│   ├── storage/                                 Adaptador de armazenamento de mídia
│   ├── queue/                                    Adaptador de fila
│   └── api/                                       Rotas FastAPI e schemas Pydantic
│       ├── routes/
│       └── schemas/
├── clinical_rules/           Regras clínicas versionadas (YAML) + CLI de validação/seed
│   ├── seeds/                 Um YAML por código de regra (blood_pressure.yaml, spo2.yaml, ...)
│   ├── schema/                  JSON Schema de validação
│   └── cli.py
├── migrations/                Migrations Alembic (sempre aditivas)
│   └── versions/
├── scripts/                    Scripts operacionais (seed de dados dev, worker standalone, export de contratos)
├── tests/                       Testes Pytest (espelham a estrutura de app/)
├── pyproject.toml               Dependências e configuração (ruff, mypy, pytest)
├── uv.lock                      Lockfile de dependências (versões exatas)
├── alembic.ini
├── Dockerfile                    Imagem da API/worker (produção)
└── Dockerfile.worker             (reservado; hoje o serviço worker reaproveita o Dockerfile principal)
```

## Frontend (`frontend/`)

```text
frontend/
├── src/
│   ├── main.tsx              Ponto de entrada
│   ├── App.tsx
│   ├── app/                   Router, guarda de permissões, providers, layout (AppShell/sidebar/topbar)
│   │   ├── router/
│   │   ├── layouts/
│   │   ├── providers/
│   │   ├── permissions.ts      Mapeamento papel -> rotas visíveis
│   │   └── enumLabels.ts        Rótulos em pt-BR para os enums gerados
│   ├── features/                Uma pasta por área de produto
│   │   ├── patients/
│   │   ├── analyses/
│   │   ├── audit/
│   │   ├── admin/
│   │   ├── dashboard/
│   │   ├── auth/
│   │   └── dev/                  Banner de sessão de desenvolvimento (X-Dev-Subject)
│   ├── components/                Componentes compartilhados
│   │   ├── ui/                     Design system (badges, botões, seções)
│   │   ├── data-display/            Tabelas, paginação
│   │   ├── feedback/                 Toasts, skeletons, estados vazio/erro
│   │   ├── forms/                     Campos de formulário
│   │   └── layout/                     PageHeader e afins
│   ├── services/
│   │   ├── api/                       Um módulo por recurso da API (fetch tipado)
│   │   └── uploads/                    Upload direto ao storage via URL pré-assinada
│   ├── hooks/                          Hooks compartilhados (sessão dev, debounce, usuário atual)
│   ├── types/                          Tipos TypeScript (espelham os schemas Pydantic)
│   │   └── enums.generated.ts           Gerado por `make codegen` — nunca editar manualmente
│   ├── lib/                             Utilitários (extração de mensagem de erro, etc.)
│   ├── styles/                          Tokens de design (CSS variables)
│   └── test/                            Setup de testes (Vitest)
├── package.json
├── package-lock.json                    Lockfile de dependências (versões exatas)
├── tsconfig*.json
├── vite.config.ts
├── eslint.config.js
├── Dockerfile                           Build de produção (Nginx)
└── nginx.conf
```

## Documentação (`docs/`)

```text
docs/
├── ARQUITETURA.md                       Contexto, containers, fluxo multimodal, ADRs
├── ESTRUTURA_PROJETO.md                 Este documento
├── BIBLIOTECAS.md                       Versões de todas as dependências, por camada
├── MANUAL_EXECUCAO.md                   Como rodar o sistema, passo a passo (Windows/macOS/Linux)
├── MANUAL_INSTALACAO.md                 Como configurar cada integração real (Azure, OpenAI, visão)
├── MANUAL_USO.md                        Manual de uso do sistema, tela a tela
├── ANALISES_DISPONIVEIS.md              O que cada análise multimodal produz, em detalhe
├── DATASETS_RECOMENDADOS.md             Onde achar datasets públicos para teste
├── ESCOPO_PROJETO.md                    Escopo completo do produto
├── ESPECIFICACAO_FRONTEND.md            Telas, design system e contratos de frontend
├── CLASSIFICACAO_DADOS_CLINICOS.md      Base de conhecimento clínica (referência preliminar)
├── adr/                                 Decisões arquiteturais (ADRs)
├── architecture/                        Diagramas Mermaid (.mmd) adicionais
├── contracts/                           Snapshot versionado do contrato OpenAPI
├── governance/                          Plano de resposta a incidentes, validação de escopo
└── images/                              Referências visuais usadas no design do frontend
```

## Onde encontrar cada coisa (atalhos comuns)

| Preciso de... | Onde está |
| --- | --- |
| Regras clínicas (limiares de pressão, SpO2, etc.) | `backend/clinical_rules/seeds/*.yaml` |
| Motor de regras (avaliação determinística) | `backend/app/rules_engine/` |
| Detecção de anomalia em série temporal | `backend/app/anomaly_detection/` |
| Processador de cada modalidade (áudio/vídeo/imagem/texto) | `backend/app/processors/` |
| Adaptadores Azure/OpenAI | `backend/app/integrations/` |
| Geração do relatório/PDF | `backend/app/reports/` |
| Trilha de auditoria | `backend/app/audit/` |
| Migrations do banco | `backend/migrations/versions/` |
| Tela de revisão da análise | `frontend/src/features/analyses/AnalysisReviewPage.tsx` |
| Telas de administração | `frontend/src/features/admin/` |
| Cliente HTTP de cada recurso | `frontend/src/services/api/` |
| Enums compartilhados back/front | `backend/app/core/enums.py` → `frontend/src/types/enums.generated.ts` (via `make codegen`) |
| Comandos disponíveis (`make ...`) | `Makefile` (raiz) |

## Documentação relacionada

- [`README.md`](../README.md) — visão geral do repositório
- [`docs/ARQUITETURA.md`](ARQUITETURA.md) — arquitetura e decisões estruturais
- [`docs/BIBLIOTECAS.md`](BIBLIOTECAS.md) — versões das dependências
