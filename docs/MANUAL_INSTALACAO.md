# Manual de Instalação e Configuração — SentinelHealth

Este manual cobre **todas** as configurações possíveis do sistema: banco de
dados, Docker, e cada integração externa (Azure Cognitive Services,
OpenAI/GPT, visão computacional self-hosted). Ele é o complemento de
[`docs/MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md), que foca no fluxo de
demonstração usando apenas adaptadores locais. Aqui o foco é: **o que
configurar, e onde, para ligar cada peça real**.

> Todas as integrações reais são opcionais para rodar o sistema localmente.
> Por padrão, tudo roda com adaptadores `LOCAL` honestos (nunca inventam
> resultado — retornam "indisponível" quando o serviço real não está
> configurado). Você só precisa configurar o que efetivamente quiser testar
> de verdade (ex.: só o OpenAI, ou só o Azure Speech, ou tudo).

A única nuvem gerenciada utilizada por este projeto é a **Microsoft
Azure** (Cognitive Services). Não há infraestrutura provisionada (o MVP
roda 100% local via Docker Compose) e não há dependência de nenhum
serviço AWS.

---

## Sumário

1. [Visão geral da arquitetura de configuração](#1-visão-geral-da-arquitetura-de-configuração)
2. [Pré-requisitos de software](#2-pré-requisitos-de-software)
3. [Obter o código e o arquivo `.env`](#3-obter-o-código-e-o-arquivo-env)
4. [Banco de dados (PostgreSQL)](#4-banco-de-dados-postgresql)
5. [Docker e Docker Compose](#5-docker-e-docker-compose)
6. [OpenAI / GPT (consolidação de risco)](#6-openai--gpt-consolidação-de-risco)
7. [Armazenamento de mídia](#7-armazenamento-de-mídia)
8. [Fila de processamento](#8-fila-de-processamento)
9. [Transcrição de áudio (Azure AI Speech)](#9-transcrição-de-áudio-azure-ai-speech)
10. [Visão computacional de vídeo (OpenPose/YOLOv8)](#10-visão-computacional-de-vídeo-openposeyolov8)
11. [Tela de feature flags (`/admin/feature-flags`)](#11-tela-de-feature-flags-adminfeature-flags)
12. [Identidade](#12-identidade)
13. [Rate limiting e segurança de sessão](#13-rate-limiting-e-segurança-de-sessão)
14. [Referência completa de variáveis de ambiente](#14-referência-completa-de-variáveis-de-ambiente)
15. [Migrations, seed e primeira execução](#15-migrations-seed-e-primeira-execução)
16. [Checklist para um teste real de ponta a ponta](#16-checklist-para-um-teste-real-de-ponta-a-ponta)
17. [Solução de problemas](#17-solução-de-problemas)

---

## 1. Visão geral da arquitetura de configuração

Toda integração externa do sistema segue o mesmo padrão: um **adaptador**
(`Protocol` do Python) com pelo menos duas implementações — `LOCAL`
(honesta, sem chamar nenhum serviço externo) e a real (Azure/OpenAI). Qual
delas roda é decidido por variável de ambiente e/ou feature flag (banco de
dados, mutável em runtime pela tela `/admin/feature-flags`), nunca por
código espalhado. Isto é o que permite este manual existir: configurar o
sistema é, na prática, preencher um arquivo `.env` e, para alguns
enriquecimentos opcionais, ligar um toggle na tela de administração.

| Integração | Como liga o modo real | Adaptador local (padrão) | Adaptador real |
| --- | --- | --- | --- |
| Consolidação de risco por IA | `.env`: `LLM_PROVIDER=OPENAI` | Template determinístico, sem rede | OpenAI (GPT) |
| Transcrição de áudio | `.env`: `TRANSCRIPTION_PROVIDER=AZURE_SPEECH` | Retorna "indisponível" | Azure AI Speech |
| Análise de sentimento/termos (texto/áudio) | feature flag `sentiment_analysis_enabled` | Retorna "indisponível" | Azure AI Language |
| Reconhecimento de imagem | feature flag `image_recognition_enabled` | Retorna "indisponível" | Azure AI Vision |
| Visão computacional (vídeo) | `.env`: `VISION_PROVIDER=OPENPOSE_YOLOV8` + feature flags `vision_pose_enabled`/`vision_detection_enabled` | Retorna "indisponível" | Worker self-hosted (OpenPose + YOLOv8) |
| Armazenamento de mídia | — (único adaptador) | Filesystem local | — |
| Fila de processamento | — (único adaptador) | Tabela PostgreSQL | — |
| Identidade/login | — (único adaptador no MVP) | Cabeçalho `X-Dev-Subject` (dev) | — (fora do escopo do MVP) |

Nenhum adaptador `LOCAL` finge um resultado: quando não configurado, o
sistema devolve explicitamente "indisponível"/"inconclusivo" em vez de
inventar uma transcrição, um resumo de IA ou uma detecção de pose.

---

## 2. Pré-requisitos de software

| Ferramenta | Versão | Uso |
| --- | --- | --- |
| Python | 3.11 ou 3.12 | Backend (gerenciado por `uv`) |
| [`uv`](https://docs.astral.sh/uv/) | atual | Instala Python + dependências do backend |
| Node.js | 22+ | Frontend (Vite) |
| npm | atual | Vem com o Node |
| Docker + Docker Compose | atual | Postgres local e/ou containers da aplicação |
| `ffmpeg` | atual | Só para visão computacional de vídeo real (seção 10) |

```bash
python3 --version
uv --version
node --version
npm --version
docker --version
docker compose version
ffmpeg -version   # opcional, so para video real
```

---

## 3. Obter o código e o arquivo `.env`

```bash
git clone <url-do-repositorio> sentinela-multimodal
cd sentinela-multimodal
cp .env.example .env
```

Todas as configurações deste manual são feitas editando `.env`. **Nunca
commite `.env` com segredos reais** — ele já está no `.gitignore`.

Instale as dependências:

```bash
make setup
```

Isso roda `uv sync` (backend) e `npm install` (frontend).

---

## 4. Banco de dados (PostgreSQL)

O `compose.yaml` já sobe um Postgres 16 configurado a partir do `.env`:

```env
POSTGRES_USER=sentinel
POSTGRES_PASSWORD=sentinel
POSTGRES_DB=sentinelhealth
DATABASE_URL=postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinelhealth
```

```bash
make compose-up
docker compose -f compose.yaml ps   # confirme que "postgres" está healthy
```

> **Importante:** `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` e a
> string de conexão em `DATABASE_URL` precisam apontar para o **mesmo**
> banco. Se você mudar um, mude o outro — é a causa mais comum de erro
> `FATAL: database "..." does not exist` ao subir o container.

Se preferir usar um Postgres já existente (local ou gerenciado), basta
apontar `DATABASE_URL` para ele:

```env
DATABASE_URL=postgresql+psycopg://<usuario>:<senha>@<host>:<porta>/<banco>
```

Aplicar as migrations (em qualquer um dos casos acima):

```bash
cd backend
uv run alembic upgrade head
```

(equivalente a `make migrate`). Cria todas as tabelas, incluindo a tabela
canônica de níveis de risco (`risk_levels`, já populada).

---

## 5. Docker e Docker Compose

### 5.1 Só o banco (uso mais comum em desenvolvimento)

```bash
make compose-up      # sobe so o Postgres; API e frontend rodam via uv/npm
make compose-down    # derruba (mantem o volume de dados)
```

### 5.2 Aplicação inteira containerizada

```bash
docker compose -f compose.yaml up -d --build
```

Sobe quatro serviços:

| Serviço | Porta local | Observação |
| --- | --- | --- |
| `postgres` | `5432` | Banco de dados |
| `backend` | `8000` | API FastAPI (usa `backend/Dockerfile`) |
| `worker` | — | Worker do orquestrador (processa a fila continuamente) |
| `frontend` | `5173` | SPA React servida via build de produção |

O `backend`/`worker` leem o `.env` da raiz (`env_file: .env` no
`compose.yaml`) e sobrescrevem só `DATABASE_URL` para apontar para o
serviço `postgres` da rede interna do Compose — os demais valores
(OpenAI, Azure etc.) vêm do seu `.env` normalmente.

Migrations e seed de regras clínicas **não** sobem automaticamente com os
containers — rode-os manualmente (seção 15) mesmo usando este modo.

### 5.3 Imagem de worker de visão computacional

O worker de vídeo (OpenPose/YOLOv8) precisa de dependências pesadas
(`ultralytics`, binário do OpenPose, `ffmpeg`) que não fazem parte da
imagem genérica do backend — ver seção 10. Uma imagem Docker dedicada
para esse worker ainda não existe neste projeto; para testar visão
computacional real hoje, instale as dependências no ambiente local (fora
de container) em vez de esperar uma imagem separada.

---

## 6. OpenAI / GPT (consolidação de risco)

O LLM **nunca** decide o risco clínico — o motor de regras determinístico
é sempre a fonte de verdade. O LLM só organiza/explica achados já
calculados. Ainda assim, para ativá-lo:

```env
LLM_PROVIDER=OPENAI
OPENAI_API_KEY=sk-...            # chave real da sua conta OpenAI
OPENAI_MODEL=gpt-4o-mini          # ou outro modelo de chat disponível na conta
```

Passos:

1. Crie uma chave de API em https://platform.openai.com/api-keys.
2. Cole em `OPENAI_API_KEY` no `.env` (nunca commite este valor).
3. Além da variável de ambiente, ligue `llm_provider_enabled` na tela
   `/admin/feature-flags` e selecione `OPENAI` como provedor — a seleção
   final do adaptador vem da feature flag (banco, mutável em runtime),
   com `.env` como fallback.
4. Rode uma análise ponta a ponta (`docs/MANUAL_EXECUCAO.md`, seção 11) e
   confirme, na tela de Revisão, que o resumo deixou de dizer "template
   determinístico local" e passou a citar o modelo configurado.

Se `llm_provider_enabled=true` e `OPENAI_API_KEY` estiver vazia, o
adaptador falha explicitamente ao chamar o LLM — nunca cai silenciosamente
de volta para o template local sem avisar.

**Custo:** cada consolidação de análise faz uma chamada de chat completion
por análise confirmada. Monitore uso pelo dashboard da OpenAI; não há
limite de taxa próprio configurado no lado do SentinelHealth para chamadas
ao LLM (o rate limiting da seção 13 protege a API do SentinelHealth, não
o consumo da API da OpenAI).

---

## 7. Armazenamento de mídia

```env
MEDIA_LOCAL_STORAGE_ROOT=./.local-media
MEDIA_UPLOAD_URL_TTL_SECONDS=900
```

O único adaptador de armazenamento deste MVP é o filesystem local — não
há configuração adicional. O upload usa uma URL/token assinado
(HMAC-SHA256) com expiração controlada por `MEDIA_UPLOAD_URL_TTL_SECONDS`;
o frontend nunca recebe uma credencial de nuvem.

Migrar para um blob storage gerenciado (ex.: Azure Blob Storage) é uma
troca isolada de adaptador (`StorageAdapter`), sem impacto no domínio —
registrado como evolução futura, não implementado hoje.

---

## 8. Fila de processamento

O único adaptador de fila deste MVP é uma tabela PostgreSQL
(`analysis_queue_messages`), consumida com
`SELECT ... FOR UPDATE SKIP LOCKED` — sem configuração adicional. Nenhuma
variável de ambiente liga um provedor alternativo hoje.

Para processar a fila, é preciso ter o worker do orquestrador em execução
(ver seção 15 ou o serviço `worker` do `compose.yaml`) — sem ele, toda
análise submetida fica parada em `QUEUED` indefinidamente.

---

## 9. Transcrição de áudio (Azure AI Speech)

```env
TRANSCRIPTION_PROVIDER=AZURE_SPEECH
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=...          # ex.: eastus
```

Passos para criar o recurso no Azure:

1. No [Azure Portal](https://portal.azure.com), crie um recurso
   **Azure AI Speech** (categoria "Speech" dentro de "Azure AI services").
2. Escolha a região (anote — vai em `AZURE_SPEECH_REGION`, ex.: `eastus`,
   `brazilsouth`) e o tier de preço (o tier gratuito é suficiente para
   testes).
3. Depois de criado, vá em **Keys and Endpoint** e copie a **Key 1** (vai
   em `AZURE_SPEECH_KEY`).
4. Cole os dois valores no `.env` e reinicie a API/worker.

O adaptador usa a **Fast Transcription API** (síncrona) — envia os bytes
do áudio direto no corpo da requisição, sem exigir upload prévio a um
Blob Storage. Idioma fixo em `pt-BR`.

Sem essa configuração (`TRANSCRIPTION_PROVIDER=LOCAL`, padrão), o
processador de áudio usa o adaptador `LOCAL`: nunca inventa uma
transcrição, apenas registra "indisponível" e segue com a análise
acústica determinística (DSP) que não depende de ASR.

### 9.1 Análise de sentimento/termos (Azure AI Language)

```env
AZURE_LANGUAGE_KEY=...
AZURE_LANGUAGE_ENDPOINT=https://<seu-recurso>.cognitiveservices.azure.com/
```

1. No Azure Portal, crie um recurso **Azure AI Language** (categoria
   "Language" dentro de "Azure AI services").
2. Em **Keys and Endpoint**, copie a **Key 1** e o **Endpoint**.
3. Cole no `.env`.
4. Ligue a feature flag `sentiment_analysis_enabled` na tela
   `/admin/feature-flags` — sem isso, mesmo com as chaves configuradas, o
   adaptador `LOCAL` continua sendo usado.

Roda sobre o texto adicional da análise e sobre a transcrição de áudio
(quando disponível). Resultado sempre **contextual**: nunca determina
risco clínico nem entra no prompt de consolidação de risco.

---

## 10. Visão computacional de vídeo (OpenPose/YOLOv8)

```env
VISION_PROVIDER=OPENPOSE_YOLOV8
VISION_MAX_SAMPLE_FRAMES=8
```

Este adaptador **não é um serviço gerenciado** — é um worker self-hosted
(decisão registrada na [ADR 0016](adr/0016-avaliacao-componentes-aws-gerenciados.md):
nenhum serviço de visão gerenciado, incluindo Azure AI Vision, oferece
estimativa de pose articulada, que é o requisito central desta seção do
escopo).

**YOLOv8 e OpenPose são ligados independentemente pela tela
`/admin/feature-flags`** (`vision_detection_enabled`/`vision_pose_enabled`),
não só por variável de ambiente: os toggles só têm efeito quando
`VISION_PROVIDER=OPENPOSE_YOLOV8` no `.env`, e permitem considerar cada
motor separadamente sem reiniciar o processo, já que o custo de
instalação dos dois é bem diferente:

- **YOLOv8**: exige apenas o pacote `ultralytics` (grupo de dependências
  opcional `vision` do backend):
  ```bash
  cd backend && uv sync --group vision
  ```
  O modelo pré-treinado (`yolov8n.pt`, COCO) é baixado automaticamente na
  primeira execução. Rápido de ligar.
- **OpenPose**: exige compilar/instalar o binário oficial (não distribuído
  via `pip`) — significativamente mais trabalho (build C++, opcionalmente
  CUDA para GPU). Por isso começa **desligado** por padrão na tela; ligue
  só depois de ter o binário disponível no `PATH`.
- Pelo menos um dos dois precisa estar ligado quando `VISION_PROVIDER=
  OPENPOSE_YOLOV8` — com os dois desligados, a fábrica (`app.integrations.
  vision.get_vision_adapter`) falha explicitamente.
- Quando um motor está desligado, o resumo do achado de vídeo nunca
  menciona "0 detecções"/"0 pessoas" para ele (isso pareceria um achado
  negativo real) — só relata o resultado dos motores que de fato rodaram.

Requisito adicional, independente de qual(is) motor(es) usar: **`ffmpeg`**
disponível no `PATH` (usado por
`app/integrations/vision/ffmpeg_frame_extractor.py` para amostrar quadros
do vídeo) — necessário mesmo rodando só YOLOv8.

`VISION_MAX_SAMPLE_FRAMES` limita quantos quadros são amostrados por
vídeo, para manter a análise rápida em CPU — aumente com cautela (mais
quadros = mais tempo de processamento por análise).

Sem essa configuração (`VISION_PROVIDER=LOCAL`, padrão), o processador de
vídeo usa o adaptador `LOCAL`: nunca inventa keypoints de pose ou
detecções de objeto, apenas registra "indisponível" e segue com a
avaliação de qualidade baseada em duração do arquivo.

---

## 11. Tela de feature flags (`/admin/feature-flags`)

Acesso restrito a administrador (técnico ou clínico — mesma regra de
`/admin/*`). Permite, sem reiniciar o processo:

- Ligar/desligar o uso de LLM real (OpenAI) — desligado, o sistema usa o
  adaptador `LOCAL` (template determinístico, sem chamada de rede).
- Escolher o modelo OpenAI (`gpt-4o-mini`, `gpt-4o`, etc.) — Gemini está
  registrado na tela apenas para planejamento; selecioná-lo falha
  explicitamente ao chamar o LLM, nunca finge funcionar.
- Ligar/desligar cada modalidade de mídia (áudio/vídeo/imagem) aceita em
  novas análises — desligar uma modalidade impede novos uploads dela
  (`422` na API), sem afetar análises já existentes.
- Ligar/desligar YOLOv8 e OpenPose de forma independente (só têm efeito
  quando `VISION_PROVIDER=OPENPOSE_YOLOV8` no `.env`).
- Ligar/desligar o reconhecimento de imagem via Azure AI Vision
  (`image_recognition_enabled`) — enriquecimento OPCIONAL, nunca
  substitui a heurística de categoria de imagem já existente.
- Ligar/desligar a análise de sentimento via Azure AI Language
  (`sentiment_analysis_enabled`) — sempre contextual, nunca determina
  risco clínico.
- Ligar/desligar o apoio à análise clínica automático
  (`auto_clinical_support_enabled`).

Toda alteração é registrada em auditoria (categoria `ADMINISTRATION`,
ação `FEATURE_FLAGS_UPDATED`) com o valor antes/depois de cada campo
alterado.

### 11.1 Azure AI Vision (imagem, enriquecimento opcional)

```env
AZURE_VISION_KEY=...
AZURE_VISION_ENDPOINT=https://<seu-recurso>.cognitiveservices.azure.com/
```

1. No Azure Portal, crie um recurso **Azure AI Vision** (categoria
   "Vision" dentro de "Azure AI services").
2. Em **Keys and Endpoint**, copie a **Key 1** e o **Endpoint**.
3. Cole no `.env` e ligue `image_recognition_enabled` na tela de feature
   flags.

Chama a **Image Analysis** (feature `tags`) sobre a imagem já aprovada,
gravando um achado `MODEL_OBSERVATION` separado com rótulos genéricos
(ex.: "X-Ray", "Person"). Roda **depois** da heurística de categoria já
existente (`app.vision.image_category`) e nunca a substitui.

---

## 12. Identidade

O único adaptador de identidade deste MVP é local: resolve o usuário a
partir do cabeçalho de desenvolvimento `X-Dev-Subject`, contendo o
`external_subject` de um usuário já cadastrado (ver `make seed-dev-data`).
Não há senha, MFA ou token gerenciado — autenticação real fica fora do
escopo do MVP. Um provedor de identidade gerenciado (ex.: Microsoft Entra
ID) é evolução futura, não implementada hoje.

---

## 13. Rate limiting e segurança de sessão

Estas variáveis já têm defaults razoáveis e normalmente não precisam ser
alteradas:

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=120/minute      # limite por IP em toda a API
RATE_LIMIT_AUTH=10/minute          # limite mais restrito em /patients/{id}/break-glass

SESSION_MAX_AGE_SECONDS=28800      # 8 horas (teto de duracao de um grant break-glass)
```

---

## 14. Referência completa de variáveis de ambiente

| Variável | Padrão | Obrigatória quando... |
| --- | --- | --- |
| `ENVIRONMENT` | `local` | Sempre |
| `LOG_LEVEL` | `INFO` | — |
| `DATABASE_URL` | Postgres do Compose | Sempre |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Ajuste para a URL real do frontend |
| `MEDIA_LOCAL_STORAGE_ROOT` | `./.local-media` | — |
| `MEDIA_UPLOAD_URL_TTL_SECONDS` | `900` | — |
| `LLM_PROVIDER` | `LOCAL` | Ligar OpenAI real: `OPENAI` (combinar com a feature flag, seção 6) |
| `OPENAI_API_KEY` | vazio | `LLM_PROVIDER=OPENAI` |
| `OPENAI_MODEL` | `gpt-4o-mini` | — |
| `TRANSCRIPTION_PROVIDER` | `LOCAL` | Ligar Azure Speech real: `AZURE_SPEECH` |
| `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` | vazio | `TRANSCRIPTION_PROVIDER=AZURE_SPEECH` |
| `AZURE_LANGUAGE_KEY` / `AZURE_LANGUAGE_ENDPOINT` | vazio | feature flag `sentiment_analysis_enabled` |
| `AZURE_VISION_KEY` / `AZURE_VISION_ENDPOINT` | vazio | feature flag `image_recognition_enabled` |
| `VISION_PROVIDER` | `LOCAL` | Ligar visão real: `OPENPOSE_YOLOV8` |
| `VISION_MAX_SAMPLE_FRAMES` | `8` | — |
| `SESSION_MAX_AGE_SECONDS` | `28800` (8h) | — |
| `RATE_LIMIT_ENABLED` | `true` | — |
| `RATE_LIMIT_DEFAULT` | `120/minute` | — |
| `RATE_LIMIT_AUTH` | `10/minute` | — |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Frontend: URL real da API |

Variáveis somente de Docker Compose local (não lidas pela aplicação
diretamente, usadas para montar `DATABASE_URL`):

| Variável | Padrão |
| --- | --- |
| `POSTGRES_USER` | `sentinel` |
| `POSTGRES_PASSWORD` | `sentinel` |
| `POSTGRES_DB` | `sentinelhealth` |

---

## 15. Migrations, seed e primeira execução

Depois de qualquer configuração acima, a sequência para colocar o sistema
de pé é sempre a mesma:

```bash
# 1. Migrations
cd backend && uv run alembic upgrade head && cd ..

# 2. Regras clinicas (validar + carregar; entram em "draft")
make rules-validate
make rules-seed

# 3. Instituicao/usuarios de desenvolvimento
make seed-dev-data

# 4. Subir API, worker do orquestrador e frontend
cd backend && uv run uvicorn app.main:app --reload &
cd backend && PYTHONPATH=. uv run python -m scripts.run_orchestrator_worker &
cd frontend && npm run dev
```

Para o fluxo completo de demonstração (cadastrar paciente, publicar
regras, rodar uma análise, revisar e baixar o PDF), siga
[`docs/MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) a partir da seção 6.

---

## 16. Checklist para um teste real de ponta a ponta

- [ ] `.env` criado (`cp .env.example .env`) e `make setup` executado
- [ ] Postgres de pé (`make compose-up`) e migrations aplicadas (`make migrate`)
- [ ] Regras clínicas validadas e carregadas (`make rules-validate && make rules-seed`)
- [ ] Instituição/usuários de desenvolvimento criados (`make seed-dev-data`, e opcionalmente `make seed-care-units`/`seed-employees`/`seed-patients`)
- [ ] API, worker do orquestrador e frontend rodando
- [ ] Para transcrição real: recurso Azure AI Speech criado, `AZURE_SPEECH_KEY`/`AZURE_SPEECH_REGION` no `.env`, `TRANSCRIPTION_PROVIDER=AZURE_SPEECH`
- [ ] Para sentimento/termos real: recurso Azure AI Language criado, chaves no `.env`, flag `sentiment_analysis_enabled` ligada em `/admin/feature-flags`
- [ ] Para reconhecimento de imagem real: recurso Azure AI Vision criado, chaves no `.env`, flag `image_recognition_enabled` ligada
- [ ] Para visão de vídeo real: `uv sync --group vision`, `ffmpeg` no `PATH`, `VISION_PROVIDER=OPENPOSE_YOLOV8`, flag `vision_detection_enabled` ligada (YOLOv8 é o mais rápido de habilitar; OpenPose exige compilar o binário separadamente)
- [ ] Para consolidação por LLM real: `OPENAI_API_KEY` no `.env`, `LLM_PROVIDER=OPENAI`, flag `llm_provider_enabled` ligada com `llm_provider=OPENAI`

---

## 17. Solução de problemas

**`FATAL: database "..." does not exist` no container do Postgres.**
`POSTGRES_DB` no `.env` não bate com o banco referenciado em
`DATABASE_URL` (ou com o healthcheck do `compose.yaml`). Alinhe os dois e
rode `docker compose -f compose.yaml down -v && make compose-up` para
recriar o volume do zero.

**Análise fica parada em `QUEUED` e nunca avança.**
O worker do orquestrador não está rodando. Rode
`make worker` (uma iteração) ou suba o serviço `worker` do
`compose.yaml` (loop contínuo).

**Resumo de IA continua dizendo "template determinístico local" mesmo com `OPENAI_API_KEY` preenchida.**
Confirme que `LLM_PROVIDER=OPENAI` no `.env` **e** que
`llm_provider_enabled=true`/`llm_provider=OPENAI` estão ligados na tela
`/admin/feature-flags` — a feature flag no banco é a fonte de verdade
final, com `.env` como fallback.

**Transcrição/sentimento/imagem sempre retornam "indisponível" mesmo com as chaves configuradas.**
Para transcrição, confirme `TRANSCRIPTION_PROVIDER=AZURE_SPEECH` no
`.env` (variável de ambiente). Para sentimento e imagem, confirme que a
feature flag correspondente (`sentiment_analysis_enabled`/
`image_recognition_enabled`) está **ligada** na tela de administração —
ter só a chave no `.env` não é suficiente para esses dois.

**Vídeo sempre retorna "indisponível" mesmo com `VISION_PROVIDER=OPENPOSE_YOLOV8`.**
Confirme que pelo menos uma das flags `vision_detection_enabled`/
`vision_pose_enabled` está ligada na tela de administração, e que a
dependência correspondente está instalada (`ultralytics` para YOLOv8,
binário compilado para OpenPose) e `ffmpeg` está no `PATH`.

---

## Documentação relacionada

- [`docs/MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) — fluxo de demonstração ponta a ponta usando os adaptadores locais.
- [`docs/adr/`](adr/) — decisões arquiteturais (ex.: ADR 0016, avaliação de componentes de nuvem gerenciados para vídeo).
- [`README.md`](../README.md) — visão geral rápida do repositório.
