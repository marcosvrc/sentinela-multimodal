# Manual de Instalação e Configuração — SentinelHealth

Este manual cobre **todas** as configurações possíveis do sistema: banco de
dados, Docker, e cada integração externa (AWS S3, SQS, Transcribe, Cognito,
OpenAI/GPT, visão computacional). Ele é o complemento de
[`docs/MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md), que foca no fluxo de
demonstração usando apenas adaptadores locais. Aqui o foco é: **o que
configurar, e onde, para ligar cada peça real**.

> Todas as integrações reais são opcionais para rodar o sistema localmente.
> Por padrão, tudo roda com adaptadores `LOCAL` honestos (nunca inventam
> resultado — retornam "indisponível" quando o serviço real não está
> configurado). Você só precisa configurar o que efetivamente quiser testar
> de verdade (ex.: só o OpenAI, ou só o S3, ou tudo).

---

## Sumário

1. [Visão geral da arquitetura de configuração](#1-visão-geral-da-arquitetura-de-configuração)
2. [Pré-requisitos de software](#2-pré-requisitos-de-software)
3. [Obter o código e o arquivo `.env`](#3-obter-o-código-e-o-arquivo-env)
4. [Banco de dados (PostgreSQL)](#4-banco-de-dados-postgresql)
5. [Docker e Docker Compose](#5-docker-e-docker-compose)
6. [OpenAI / GPT (consolidação de risco)](#6-openai--gpt-consolidação-de-risco)
7. [Armazenamento de mídia (local vs. Amazon S3)](#7-armazenamento-de-mídia-local-vs-amazon-s3)
8. [Fila de processamento (local vs. Amazon SQS)](#8-fila-de-processamento-local-vs-amazon-sqs)
9. [Transcrição de áudio (Amazon Transcribe)](#9-transcrição-de-áudio-amazon-transcribe)
10. [Visão computacional de vídeo (OpenPose/YOLOv8)](#10-visão-computacional-de-vídeo-openposeyolov8)
11. [Identidade real (Amazon Cognito + MFA)](#11-identidade-real-amazon-cognito--mfa)
12. [Rate limiting e segurança de sessão](#12-rate-limiting-e-segurança-de-sessão)
13. [Referência completa de variáveis de ambiente](#13-referência-completa-de-variáveis-de-ambiente)
14. [Infraestrutura completa via Terraform (homologação/produção)](#14-infraestrutura-completa-via-terraform-homologaçãoprodução)
15. [Migrations, seed e primeira execução](#15-migrations-seed-e-primeira-execução)
16. [Checklist antes de ir para produção](#16-checklist-antes-de-ir-para-produção)
17. [Solução de problemas](#17-solução-de-problemas)

---

## 1. Visão geral da arquitetura de configuração

Toda integração externa do sistema segue o mesmo padrão: um **adaptador**
(`Protocol` do Python) com pelo menos duas implementações — `LOCAL`
(honesta, sem chamar nenhum serviço externo) e a real (AWS/OpenAI/Cognito).
Qual delas roda é decidido só por variável de ambiente, nunca por código
espalhado. Isto é o que permite este manual existir: configurar o sistema é,
na prática, preencher um arquivo `.env` (ou variáveis de ambiente no ECS).

| Integração | Variável que liga o modo real | Adaptador local (padrão) | Adaptador real |
| --- | --- | --- | --- |
| Consolidação de risco por IA | `LLM_PROVIDER=OPENAI` | Template determinístico, sem rede | OpenAI (GPT) |
| Armazenamento de mídia | `MEDIA_STORAGE_BACKEND=S3` | Filesystem local | Amazon S3 |
| Fila de processamento | segue `MEDIA_STORAGE_BACKEND` (ver seção 8) | Fila em tabela do Postgres | Amazon SQS |
| Transcrição de áudio | `TRANSCRIPTION_PROVIDER=AWS_TRANSCRIBE` | Retorna "indisponível" | Amazon Transcribe |
| Visão computacional (vídeo) | `VISION_PROVIDER=OPENPOSE_YOLOV8` | Retorna "indisponível" | Worker self-hosted (OpenPose + YOLOv8) |
| Identidade/login | `IDENTITY_PROVIDER=COGNITO` | Cabeçalho `X-Dev-Subject` (dev) | Amazon Cognito (token real + MFA) |

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
| Terraform | ≥ 1.5 | Só necessário se for provisionar infraestrutura real em AWS (seção 14) |
| AWS CLI | atual | Só necessário para configurar credenciais AWS (seções 7–11) |

```bash
python3 --version
uv --version
node --version
npm --version
docker --version
docker compose version
terraform --version   # opcional
aws --version          # opcional
```

---

## 3. Obter o código e o arquivo `.env`

```bash
git clone <url-do-repositorio> sentinela-multimodal
cd sentinela-multimodal
cp .env.example .env
```

Todas as configurações deste manual são feitas editando `.env` (execução
local/Docker Compose) ou as variáveis de ambiente da Task Definition do ECS
(homologação/produção — providas pelo Terraform, seção 14). **Nunca
commite `.env` com segredos reais** — ele já está no `.gitignore`.

Instale as dependências:

```bash
make setup
```

Isso roda `uv sync` (backend) e `npm install` (frontend).

---

## 4. Banco de dados (PostgreSQL)

### 4.1 Local (Docker Compose — recomendado para desenvolvimento)

O `compose.yaml` já sobe um Postgres 16 configurado a partir do `.env`:

```env
POSTGRES_USER=sentinel
POSTGRES_PASSWORD=sentinel
POSTGRES_DB=sentinel
DATABASE_URL=postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinel
```

```bash
make compose-up
docker compose -f compose.yaml ps   # confirme que "postgres" está healthy
```

> **Importante:** `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` e a
> string de conexão em `DATABASE_URL` precisam apontar para o **mesmo**
> banco. Se você mudar um, mude o outro — é a causa mais comum de erro
> `FATAL: database "..." does not exist` ao subir o container.

### 4.2 Um Postgres já existente (local ou gerenciado)

Basta apontar `DATABASE_URL` para ele — nenhuma outra configuração muda:

```env
DATABASE_URL=postgresql+psycopg://<usuario>:<senha>@<host>:<porta>/<banco>
```

### 4.3 Amazon RDS (homologação/produção)

Provisionado pelo módulo Terraform `infra/modules/database` (seção 14). O
RDS usa `manage_master_user_password` — a senha do usuário administrativo
é gerada e rotacionada pelo próprio RDS via Secrets Manager, **nunca**
fixada em `.env` ou código. A Task Definition do ECS recebe a
`DATABASE_URL` já resolvida a partir do Secrets Manager; não há passo
manual de configurar senha de banco em produção.

### 4.4 Aplicar as migrations

Em qualquer um dos três casos acima:

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

Sobe três serviços:

| Serviço | Porta local | Observação |
| --- | --- | --- |
| `postgres` | `5432` | Banco de dados |
| `backend` | `8000` | API FastAPI (usa `backend/Dockerfile`) |
| `frontend` | `5173` | SPA React servida via build de produção |

O `backend` lê o `.env` da raiz (`env_file: .env` no `compose.yaml`) e
sobrescreve só `DATABASE_URL` para apontar para o serviço `postgres` da
rede interna do Compose — os demais valores (OpenAI, S3, Cognito etc.)
vêm do seu `.env` normalmente.

Migrations, seed de regras clínicas e o worker do orquestrador **não**
sobem automaticamente com os containers — rode-os manualmente (seção 15)
mesmo usando este modo.

### 5.3 Imagens de worker (processamento assíncrono)

`backend/Dockerfile.worker` builda a imagem genérica usada pelos workers
de CPU (áudio, texto, consolidação/relatório, orquestrador). O worker de
visão computacional (OpenPose/YOLOv8) usa uma imagem **separada**, com
dependências pesadas de visão (`ultralytics`, binário do OpenPose,
`ffmpeg`) — ver seção 10. Essa imagem de vídeo ainda não está incluída
neste scaffold; o adaptador de orquestração já existe e é testado
(`app/integrations/vision/openpose_yolo.py`), mas o Dockerfile do worker
de vídeo self-hosted precisa ser criado antes de rodar `VISION_PROVIDER`
real em produção (ver `docs/governance/VALIDACAO_ESCOPO.md`, item 4.1).

```bash
docker build -f backend/Dockerfile.worker -t sentinelhealth-worker ./backend
```

Em homologação/produção, essas imagens vão para o ECR (módulo
`infra/modules/ecr`, seção 14) e são referenciadas pela Task Definition do
ECS — não pelo `compose.yaml`.

---

## 6. OpenAI / GPT (consolidação de risco)

O LLM **nunca** decide o risco clínico — o motor de regras determinístico
é sempre a fonte de verdade. O LLM só organiza/explica achados já
calculados (ESCOPO_PROJETO.md seção 5.5). Ainda assim, para ativá-lo:

```env
LLM_PROVIDER=OPENAI
OPENAI_API_KEY=sk-...            # chave real da sua conta OpenAI
OPENAI_MODEL=gpt-4o-mini          # ou outro modelo de chat disponível na conta
```

Passos:

1. Crie uma chave de API em https://platform.openai.com/api-keys.
2. Cole em `OPENAI_API_KEY` no `.env` (nunca commite este valor).
3. Reinicie a API (`uvicorn`/container) — a seleção do adaptador acontece
   uma vez por processo (`app/integrations/llm/`).
4. Rode uma análise ponta a ponta (`docs/MANUAL_EXECUCAO.md`, seção 11) e
   confirme, na tela de Revisão, que o resumo deixou de dizer "template
   determinístico local" e passou a citar o modelo configurado.

Em homologação/produção, `OPENAI_API_KEY` **não** vai no `.env`: fica no
AWS Secrets Manager (módulo `infra/modules/secrets`, output
`openai_api_key_secret_arn`) e é injetada na Task Definition do ECS pelo
Terraform. Se `LLM_PROVIDER=OPENAI` e `OPENAI_API_KEY` estiver vazia, o
adaptador falha explicitamente no startup — nunca cai silenciosamente de
volta para o template local.

**Custo:** cada consolidação de análise faz uma chamada de chat completion
por análise confirmada. Monitore uso pelo dashboard da OpenAI; não há
limite de taxa próprio configurado no lado do SentinelHealth para chamadas
ao LLM (o rate limiting da seção 12 protege a API do SentinelHealth, não
o consumo da API da OpenAI).

---

## 7. Armazenamento de mídia (local vs. Amazon S3)

```env
# LOCAL (padrão) - filesystem, nada a configurar
MEDIA_STORAGE_BACKEND=LOCAL
MEDIA_LOCAL_STORAGE_ROOT=./.local-media
MEDIA_UPLOAD_URL_TTL_SECONDS=900
```

Para usar S3 real:

```env
MEDIA_STORAGE_BACKEND=S3
AWS_REGION=us-east-1
S3_MEDIA_BUCKET=sentinelhealth-homologation-media   # nome do bucket real
```

Requisitos:

1. **Bucket S3** já existente com criptografia (KMS) e versionamento — o
   módulo Terraform `infra/modules/storage` provisiona isso corretamente
   (política de retenção de versões antigas incluída). Se for criar o
   bucket manualmente fora do Terraform, replique essas configurações.
2. **Credenciais AWS** disponíveis para o processo backend: em produção,
   isso é a IAM Role da Task ECS (`infra/modules/ecs`, uma role por
   processo — API e cada worker têm a própria, nunca compartilhada). Em
   desenvolvimento local fora de containers, use um profile AWS local
   (`aws configure` + `AWS_PROFILE=<nome>` no ambiente) — **nunca** cole
   uma access key fixa no `.env`.
3. O frontend nunca recebe credencial AWS: todo upload usa URL
   pré-assinada gerada pelo backend (`MEDIA_UPLOAD_URL_TTL_SECONDS`
   controla a expiração).

> Ativar `MEDIA_STORAGE_BACKEND=S3` também troca o adaptador de **fila**
> para SQS automaticamente — ver seção 8.

---

## 8. Fila de processamento (local vs. Amazon SQS)

A fila não tem uma variável própria de "provider": ela segue
`MEDIA_STORAGE_BACKEND` (`app/queue/__init__.py`) — a mesma alternância
LOCAL/AWS dos dois anda junto, porque em desenvolvimento os dois
adaptadores locais trabalham juntos, e em produção os dois adaptadores AWS
trabalham juntos.

```env
MEDIA_STORAGE_BACKEND=S3     # ja liga S3 (storage) + SQS (fila)
SQS_ANALYSIS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/<conta>/sentinelhealth-<env>-analysis
SQS_ANALYSIS_DLQ_URL=https://sqs.us-east-1.amazonaws.com/<conta>/sentinelhealth-<env>-analysis-dlq
```

Se `MEDIA_STORAGE_BACKEND=S3` e `SQS_ANALYSIS_QUEUE_URL` não estiver
preenchida, o backend falha explicitamente ao resolver o adaptador de fila
(`RuntimeError`) em vez de silenciosamente usar a fila local.

A fila e a DLQ (dead-letter queue, para mensagens que falharam
repetidamente) são provisionadas pelo módulo Terraform
`infra/modules/queue` — `max_receive_count` (tentativas antes de mover
para a DLQ) e `visibility_timeout_seconds` são configuráveis lá.

---

## 9. Transcrição de áudio (Amazon Transcribe)

```env
TRANSCRIPTION_PROVIDER=AWS_TRANSCRIBE
TRANSCRIPTION_OUTPUT_BUCKET=sentinelhealth-homologation-transcribe-output
```

Requisitos:

1. Um bucket S3 para o Transcribe escrever o resultado do job
   (`TRANSCRIPTION_OUTPUT_BUCKET`) — pode ser o mesmo bucket de mídia ou
   um dedicado; garanta que a IAM Role do processo tenha permissão de
   escrita nele.
2. `S3_MEDIA_BUCKET` também precisa estar configurado (o áudio de origem
   é lido de lá).
3. Permissões IAM: `transcribe:StartTranscriptionJob`,
   `transcribe:GetTranscriptionJob`, além do acesso de leitura/escrita nos
   buckets envolvidos.

Sem essa configuração, o processador de áudio usa o adaptador `LOCAL`:
nunca inventa uma transcrição, apenas registra "indisponível" e segue com
a análise acústica determinística (DSP) que não depende de ASR.

---

## 10. Visão computacional de vídeo (OpenPose/YOLOv8)

```env
VISION_PROVIDER=OPENPOSE_YOLOV8
VISION_MAX_SAMPLE_FRAMES=8
```

Este é o adaptador mais pesado de configurar porque **não é um serviço
gerenciado da AWS** — é um worker self-hosted (decisão registrada na
ADR 0016: o Amazon Rekognition Video não oferece estimativa de pose, que
é o requisito central desta seção do escopo).

**YOLOv8 e OpenPose são ligados independentemente pela tela
`/admin/feature-flags`** (acesso restrito a administrador — ver
`app.feature_flags`), não por variável de ambiente: os toggles "YOLOv8" e
"OpenPose" da tela só têm efeito quando `VISION_PROVIDER=OPENPOSE_YOLOV8`
no `.env`, e permitem considerar cada motor separadamente sem reiniciar o
processo, já que o custo de instalação dos dois é bem diferente:

- **YOLOv8**: exige apenas o pacote `ultralytics` (grupo de dependências
  opcional `vision` do backend — `uv sync --group vision`). O modelo
  pré-treinado (`yolov8n.pt`, COCO) é baixado automaticamente na primeira
  execução. Rápido de ligar.
- **OpenPose**: exige compilar/instalar o binário oficial (não distribuído
  via `pip`) — significativamente mais trabalho (build C++, opcionalmente
  CUDA para GPU). Por isso começa **desligado** por padrão na tela; ligue
  só depois de ter o binário disponível na imagem do worker.
- Pelo menos um dos dois precisa estar ligado quando `VISION_PROVIDER=
  OPENPOSE_YOLOV8` — com os dois desligados, a fábrica (`app.integrations.
  vision.get_vision_adapter`) falha explicitamente.
- Quando um motor está desligado, o resumo do achado de vídeo nunca
  menciona "0 detecções"/"0 pessoas" para ele (isso pareceria um achado
  negativo real) — só relata o resultado dos motores que de fato rodaram.

Requisitos adicionais, independente de qual(is) motor(es) usar:

1. **`ffmpeg`** disponível no `PATH` da imagem do worker (usado por
   `app/integrations/vision/ffmpeg_frame_extractor.py` para amostrar
   quadros do vídeo) — necessário mesmo rodando só YOLOv8.
2. Uma imagem Docker dedicada para este worker (maior que a genérica de
   `Dockerfile.worker`) — **ainda não incluída neste scaffold**; é o
   próximo passo antes de rodar visão computacional real em produção (ver
   `docs/governance/VALIDACAO_ESCOPO.md`, item 4.1, e a nota da seção 5.3
   deste manual).
3. `VISION_MAX_SAMPLE_FRAMES` limita quantos quadros são amostrados por
   vídeo, para manter a análise rápida em CPU — aumente com cautela (mais
   quadros = mais tempo de processamento por análise).

Sem essa configuração (`VISION_PROVIDER=LOCAL`, padrão), o processador de
vídeo usa o adaptador `LOCAL`: nunca inventa keypoints de pose ou
detecções de objeto, apenas registra "indisponível" e segue com a
avaliação de qualidade baseada em duração do arquivo (que não depende de
visão computacional).

---

## 11. Identidade real (Amazon Cognito + MFA)

```env
IDENTITY_PROVIDER=COGNITO
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
COGNITO_ISSUER_URL=              # opcional; derivado automaticamente se vazio
COGNITO_JWKS_CACHE_TTL_SECONDS=3600

# Frontend (valores publicos, nao segredos)
VITE_COGNITO_ISSUER_URL=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXXXXXXXX
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
```

Requisitos:

1. **User Pool do Cognito** provisionado — o módulo Terraform
   `infra/modules/identity` cria o User Pool e o Client (`callback_urls`,
   `logout_urls` e `mfa_configuration` são variáveis desse módulo; use
   `mfa_configuration = "ON"` em produção, já que o sistema lida com dados
   de saúde). Os outputs do módulo (`user_pool_id`, `user_pool_client_id`,
   `issuer_url`) alimentam diretamente as variáveis acima.
2. Sem AWS, você pode criar o User Pool manualmente pelo console AWS
   Cognito, mas replique a configuração de MFA e os callback URLs do
   frontend.
3. **`homologation` e `production` nunca podem rodar com
   `IDENTITY_PROVIDER=LOCAL`** — há uma trava de segurança no próprio
   código (`Settings.requires_real_identity_provider`) que bloqueia o
   cabeçalho `X-Dev-Subject` nesses ambientes, mesmo que alguém
   reconfigure por engano.
4. Depois que o Cognito estiver ativo, o provisionamento de contas de
   usuário passa a ter dois passos: (a) criar a conta no Cognito
   (`AdminCreateUser`, fora deste backend) e (b) espelhar
   instituição/papel no SentinelHealth via `POST /admin/users` (tela
   **Administração → Usuários e papéis**), usando o mesmo `sub` do
   Cognito como `external_subject`.

Sem essa configuração, o sistema roda com o cabeçalho de desenvolvimento
`X-Dev-Subject` (fluxo descrito em `docs/MANUAL_EXECUCAO.md`) — apropriado
apenas para desenvolvimento local e testes.

---

## 12. Rate limiting e segurança de sessão

Estas variáveis já têm defaults razoáveis e normalmente não precisam ser
alteradas, mas podem ser ajustadas por ambiente:

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=120/minute      # limite por IP em toda a API
RATE_LIMIT_AUTH=10/minute          # limite mais restrito em /patients/{id}/break-glass

LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_LOCKOUT_WINDOW_SECONDS=900
SESSION_MAX_AGE_SECONDS=28800      # 8 horas
```

O bloqueio por tentativa e a sessão revogável centralmente só têm efeito
real com `IDENTITY_PROVIDER=COGNITO` (seção 11) — o adaptador local de
desenvolvimento não simula sessão persistente.

---

## 13. Referência completa de variáveis de ambiente

| Variável | Padrão | Obrigatória quando... |
| --- | --- | --- |
| `ENVIRONMENT` | `local` | Sempre. Use `local`/`test`/`homologation`/`production` |
| `LOG_LEVEL` | `INFO` | — |
| `DATABASE_URL` | Postgres do Compose | Sempre |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Ajuste para a URL real do frontend em cada ambiente |
| `AWS_REGION` | `us-east-1` | Qualquer integração AWS ativa |
| `S3_MEDIA_BUCKET` | vazio | `MEDIA_STORAGE_BACKEND=S3` ou `TRANSCRIPTION_PROVIDER=AWS_TRANSCRIBE` |
| `SQS_ANALYSIS_QUEUE_URL` / `SQS_ANALYSIS_DLQ_URL` | vazio | `MEDIA_STORAGE_BACKEND=S3` |
| `MEDIA_STORAGE_BACKEND` | `LOCAL` | Ligar S3 real: `S3` |
| `MEDIA_LOCAL_STORAGE_ROOT` | `./.local-media` | Só quando `MEDIA_STORAGE_BACKEND=LOCAL` |
| `MEDIA_UPLOAD_URL_TTL_SECONDS` | `900` | — |
| `LLM_PROVIDER` | `LOCAL` | Ligar OpenAI real: `OPENAI` |
| `OPENAI_API_KEY` | vazio | `LLM_PROVIDER=OPENAI` |
| `OPENAI_MODEL` | `gpt-4o-mini` | — |
| `TRANSCRIPTION_PROVIDER` | `LOCAL` | Ligar Transcribe real: `AWS_TRANSCRIBE` |
| `TRANSCRIPTION_OUTPUT_BUCKET` | vazio | `TRANSCRIPTION_PROVIDER=AWS_TRANSCRIBE` |
| `VISION_PROVIDER` | `LOCAL` | Ligar visão real: `OPENPOSE_YOLOV8` |
| `VISION_MAX_SAMPLE_FRAMES` | `8` | — |

YOLOv8/OpenPose (ligados dentro do `VISION_PROVIDER=OPENPOSE_YOLOV8`), provedor de LLM (OpenAI/Gemini) e quais modalidades de mídia (áudio/vídeo/imagem) ficam disponíveis são controlados pela tela `/admin/feature-flags` (banco de dados, mutável em runtime), não por variável de ambiente — ver seção 11 abaixo.

## 11. Tela de feature flags (`/admin/feature-flags`)

Acesso restrito a administrador (técnico ou clínico — mesma regra de `/admin/*`). Permite, sem reiniciar o processo:

- Ligar/desligar o uso de LLM real (OpenAI ou Gemini) — desligado, o sistema usa o adaptador `LOCAL` (template determinístico, sem chamada de rede).
- Escolher o modelo OpenAI (`gpt-4o-mini`, `gpt-4o`, etc.) ou Gemini (Gemini ainda não tem adaptador real implementado — selecioná-lo falha explicitamente ao chamar o LLM, nunca finge funcionar).
- Ligar/desligar cada modalidade de mídia (áudio/vídeo/imagem) aceita em novas análises — desligar uma modalidade impede novos uploads dela (`422` na API), sem afetar análises já existentes.
- Ligar/desligar YOLOv8 e OpenPose de forma independente (só têm efeito quando `VISION_PROVIDER=OPENPOSE_YOLOV8` no `.env` — a tela não substitui a necessidade de ter o worker de vídeo configurado).
- Ligar/desligar Amazon Rekognition Image e Amazon Rekognition Video de forma independente (ver seção 10.1 abaixo) — enriquecimento OPCIONAL e COMPLEMENTAR, nunca substitui a heurística de categoria de imagem nem o worker OpenPose/YOLOv8 (ADR 0016).

Toda alteração é registrada em auditoria (categoria `ADMINISTRATION`, ação `FEATURE_FLAGS_UPDATED`) com o valor antes/depois de cada campo alterado.

### 10.1 Amazon Rekognition (imagem/vídeo, enriquecimento opcional)

Diferente do worker OpenPose/YOLOv8 (self-hosted, seção 10), o Amazon Rekognition é um serviço gerenciado — ligar as flags abaixo não exige nenhuma imagem Docker adicional nem instalação de dependência pesada, apenas credenciais AWS e `S3_MEDIA_BUCKET` configurados (o mesmo bucket já usado pelo Transcribe).

- **`image_recognition_enabled`**: chama `rekognition:DetectLabels` (síncrono) sobre a imagem já aprovada, gravando um achado `MODEL_OBSERVATION` separado com rótulos genéricos (ex.: "X-Ray", "Person"). Roda **depois** da heurística de categoria já existente (`app.vision.image_category`) e nunca a substitui.
- **`vision_rekognition_video_enabled`**: chama `rekognition:StartLabelDetection`/`GetLabelDetection` (assíncrono, mesmo padrão de poll síncrono do Transcribe) sobre o vídeo já aprovado, gravando outro achado `MODEL_OBSERVATION` separado com rótulos e timestamp. Roda **depois** do worker OpenPose/YOLOv8 e nunca o substitui — o Rekognition não faz estimativa de pose (ver ADR 0016).

Permissão IAM necessária (já incluída em `infra/iam-policies/sentinelhealth-dev-local-aws-policy.json`, statement `RekognitionRuntime`):

```json
{
  "Effect": "Allow",
  "Action": [
    "rekognition:DetectLabels",
    "rekognition:StartLabelDetection",
    "rekognition:GetLabelDetection"
  ],
  "Resource": "*"
}
```

**Amazon Transcribe Medical e Amazon Comprehend Medical foram avaliados e descartados** (ver ADR 0016, seção "Atualização"): ambos suportam exclusivamente inglês dos EUA (`en-US`), sem suporte a `pt-BR` — como toda a cadeia clínica deste projeto opera em português brasileiro, os dois serviços nunca produziriam um resultado real no fluxo atual. Não há adaptador para eles neste projeto.
| `IDENTITY_PROVIDER` | `LOCAL` | Ligar Cognito real: `COGNITO`. **Obrigatório `COGNITO` em `homologation`/`production`** |
| `COGNITO_USER_POOL_ID` / `COGNITO_CLIENT_ID` | vazio | `IDENTITY_PROVIDER=COGNITO` |
| `COGNITO_ISSUER_URL` | vazio (derivado) | Opcional |
| `COGNITO_JWKS_CACHE_TTL_SECONDS` | `3600` | — |
| `LOGIN_MAX_FAILED_ATTEMPTS` | `5` | — |
| `LOGIN_LOCKOUT_WINDOW_SECONDS` | `900` | — |
| `LOGIN_LOCKOUT_DURATION_SECONDS` | `900` | — |
| `SESSION_MAX_AGE_SECONDS` | `28800` (8h) | — |
| `RATE_LIMIT_ENABLED` | `true` | — |
| `RATE_LIMIT_DEFAULT` | `120/minute` | — |
| `RATE_LIMIT_AUTH` | `10/minute` | — |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Frontend: URL real da API em cada ambiente |
| `VITE_COGNITO_ISSUER_URL` / `VITE_COGNITO_CLIENT_ID` | vazio | Frontend, quando `IDENTITY_PROVIDER=COGNITO` |

Variáveis somente de Docker Compose local (não lidas pela aplicação
diretamente, usadas para montar `DATABASE_URL`):

| Variável | Padrão |
| --- | --- |
| `POSTGRES_USER` | `sentinel` |
| `POSTGRES_PASSWORD` | `sentinel` |
| `POSTGRES_DB` | `sentinel` |

---

## 14. Infraestrutura completa via Terraform (homologação/produção)

Para além de configurar variáveis de ambiente, homologação e produção
precisam da infraestrutura AWS provisionada. Isso é feito pelo Terraform
em `infra/` — **nenhum recurso é criado manualmente pelo console** nesses
ambientes.

```text
infra/
├── modules/            # blocos reutilizáveis (um por responsabilidade)
│   ├── network/         # VPC, subnets publicas/privadas, security groups
│   ├── database/        # RDS PostgreSQL
│   ├── storage/         # bucket S3 de midia (KMS + versionamento)
│   ├── queue/            # SQS (fila + DLQ)
│   ├── identity/         # Cognito User Pool + Client
│   ├── secrets/          # Secrets Manager (ex.: OPENAI_API_KEY)
│   ├── kms/               # chave de criptografia compartilhada
│   ├── ecr/                # repositorios de imagem Docker
│   └── ecs/                 # cluster, Task Definitions, IAM Role por processo
└── environments/
    ├── local/            # apenas documentação (usa Docker Compose, nao Terraform)
    ├── homologation/
    └── production/
```

Passos (repita para `homologation` e depois `production`):

```bash
cd infra/environments/homologation
cp terraform.tfvars.example terraform.tfvars
# edite terraform.tfvars: imagens do ECR (com tag do commit), callback URLs
# do Cognito, etc. Nao commite terraform.tfvars (ja esta no .gitignore).

terraform init
terraform plan
terraform apply
```

Isso provisiona, nesta ordem de dependência: KMS → rede (VPC/subnets) →
S3 → SQS → RDS → Cognito → Secrets Manager → ECR → ECS (API + um serviço
por worker, cada um com sua própria IAM Role — nunca compartilhada entre
processos, conforme ESCOPO_PROJETO.md seção 6.9).

Depois do `apply`, pegue os outputs relevantes (`terraform output`) e
preencha as variáveis de ambiente da Task Definition (a maior parte já é
gerada automaticamente pelo próprio Terraform a partir dos outputs dos
outros módulos — `S3_MEDIA_BUCKET`, `SQS_ANALYSIS_QUEUE_URL`,
`COGNITO_USER_POOL_ID` etc. — mas confirme cada uma contra a seção 13
deste manual).

**Build e push das imagens Docker para o ECR:**

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <conta>.dkr.ecr.us-east-1.amazonaws.com

docker build -t <conta>.dkr.ecr.us-east-1.amazonaws.com/sentinelhealth-homologation-api:<sha> \
  -f backend/Dockerfile backend
docker push <conta>.dkr.ecr.us-east-1.amazonaws.com/sentinelhealth-homologation-api:<sha>
```

Repita para cada worker (`Dockerfile.worker`), usando uma tag por commit
(`<sha>`) — nunca `latest` em produção, para rastreabilidade.

> **Limitação conhecida:** os arquivos Terraform foram validados apenas
> sintaticamente neste projeto (`python-hcl2`), nunca com `terraform
> plan`/`apply` contra uma conta AWS real. Revise cada módulo com atenção
> antes do primeiro `apply` real, especialmente `variables.tf` e os
> `terraform.tfvars.example` (ver `docs/governance/VALIDACAO_ESCOPO.md`,
> seção 6.3).

---

## 15. Migrations, seed e primeira execução

Depois de qualquer configuração acima (local ou AWS), a sequência para
colocar o sistema de pé é sempre a mesma:

```bash
# 1. Migrations
cd backend && uv run alembic upgrade head && cd ..

# 2. Regras clinicas (validar + carregar; entram em "draft")
make rules-validate
make rules-seed

# 3. Instituicao/usuarios de desenvolvimento (LOCAL) OU
#    provisionamento via Cognito + POST /admin/users (COGNITO - secao 11)
make seed-dev-data   # apenas quando IDENTITY_PROVIDER=LOCAL

# 4. Subir API, worker do orquestrador e frontend
cd backend && uv run uvicorn app.main:app --reload &
cd backend && PYTHONPATH=. uv run python -m scripts.run_orchestrator_worker &
cd frontend && npm run dev
```

Para o fluxo completo de demonstração (cadastrar paciente, publicar
regras, rodar uma análise, revisar e baixar o PDF), siga
[`docs/MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) a partir da seção 6.

---

## 16. Checklist antes de ir para produção

- [ ] `ENVIRONMENT=production`
- [ ] `IDENTITY_PROVIDER=COGNITO`, `mfa_configuration = "ON"` no módulo Terraform de identidade
- [ ] `LLM_PROVIDER=OPENAI` com `OPENAI_API_KEY` vindo do Secrets Manager (nunca do `.env`)
- [ ] `MEDIA_STORAGE_BACKEND=S3` com bucket real e `SQS_ANALYSIS_QUEUE_URL`/`SQS_ANALYSIS_DLQ_URL` preenchidos
- [ ] `TRANSCRIPTION_PROVIDER=AWS_TRANSCRIBE` (se a modalidade de áudio for usada com paciente real)
- [ ] `VISION_PROVIDER=OPENPOSE_YOLOV8` **apenas** depois que a imagem do worker de vídeo self-hosted existir de fato (seção 10) — caso contrário, mantenha `LOCAL` e comunique a lacuna
- [ ] `CORS_ALLOWED_ORIGINS` restrito ao domínio real do frontend (nunca `*`)
- [ ] Cada processo (API + cada worker) com sua própria IAM Role, sem permissões amplas compartilhadas
- [ ] RIPD/LGPD aprovado e avaliação de fornecedores (AWS/OpenAI) concluída — **nenhum dado real de paciente antes disso**, independentemente do que estiver tecnicamente configurado (ver `docs/governance/VALIDACAO_ESCOPO.md`, seção 8)
- [ ] SAST/SCA/DAST/pentest executados — ainda não instrumentados neste projeto, é responsabilidade do time de segurança antes do go-live

---

## 17. Solução de problemas

**`FATAL: database "..." does not exist` no container do Postgres.**
`POSTGRES_DB` no `.env` não bate com o banco referenciado em
`DATABASE_URL` (ou com o healthcheck do `compose.yaml`). Alinhe os dois e
rode `docker compose -f compose.yaml down -v && make compose-up` para
recriar o volume do zero.

**`RuntimeError: Fila SQS selecionada mas SQS_ANALYSIS_QUEUE_URL nao configurada`.**
Você setou `MEDIA_STORAGE_BACKEND=S3` sem preencher `SQS_ANALYSIS_QUEUE_URL`
— as duas variáveis andam juntas (seção 8).

**`identity_provider=COGNITO exige cognito_user_pool_id e cognito_client_id configurados`.**
Preencha `COGNITO_USER_POOL_ID` e `COGNITO_CLIENT_ID` (seção 11), ou volte
para `IDENTITY_PROVIDER=LOCAL` em desenvolvimento.

**Erro `403 LOCAL_IDENTITY_PROVIDER_FORBIDDEN`.**
`ENVIRONMENT=homologation` ou `production` com `IDENTITY_PROVIDER=LOCAL`
— essa combinação é bloqueada de propósito. Configure o Cognito (seção 11).

**Resumo de IA continua dizendo "template determinístico local" mesmo com `OPENAI_API_KEY` preenchida.**
Confirme que `LLM_PROVIDER=OPENAI` (não basta a chave) e reinicie o
processo da API — a seleção do adaptador é cacheada por processo.

**Vídeo/áudio sempre retornam "indisponível" mesmo com o provider configurado.**
Confirme que o worker que processa aquela modalidade tem, de fato, as
dependências reais instaladas (ver seções 9 e 10) — o adaptador real
lança erro explícito de configuração ausente em vez de voltar
silenciosamente para o comportamento local.

**Terraform `apply` falha com erro de permissão.**
Confirme que suas credenciais AWS (`aws sts get-caller-identity`) têm
permissão para criar os recursos de cada módulo — o Terraform deste
projeto nunca foi exercitado contra uma conta AWS real (ver aviso na
seção 14); é esperado precisar iterar no primeiro `apply`.

---

## Documentação relacionada

- [`docs/MANUAL_EXECUCAO.md`](MANUAL_EXECUCAO.md) — fluxo de demonstração ponta a ponta usando os adaptadores locais.
- [`docs/governance/VALIDACAO_ESCOPO.md`](governance/VALIDACAO_ESCOPO.md) — o que está implementado de fato versus o escopo, incluindo o estado real de cada integração.
- [`docs/adr/`](adr/) — decisões arquiteturais (ex.: ADR 0016, avaliação de componentes AWS gerenciados).
- [`README.md`](../README.md) — visão geral rápida do repositório.
