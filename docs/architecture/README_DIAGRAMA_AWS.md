# Diagramas de arquitetura AWS

Dois diagramas, para apresentar **nesta ordem** ao comitê (do que já
existe/foi testado para o que é o alvo de produção):

1. **`sentinelhealth_architecture_local_dev.png` / `.svg` / `.pdf`** — o
   que está montado e testado HOJE: ambiente local (Docker Compose) e o
   modo dev conectado a serviços AWS reais (S3/SQS/KMS/Transcribe/
   Rekognition), sem VPC/ECS/RDS. Ver seção "Diagrama 1" abaixo.
2. **`sentinelhealth_architecture.png` / `.svg` / `.pdf`** — a arquitetura
   alvo de produção/homologação (VPC, ECS Fargate, RDS Multi-AZ, Cognito,
   etc.), ainda não implantada. Ver seção "Diagrama 2" abaixo.

Gerados com [`diagrams`](https://diagrams.mingrammer.com/) (mingrammer),
que usa os ícones oficiais dos provedores (AWS, GitHub, etc.). Scripts
versionados em `scripts/build_diagram_local_dev.py` e
`scripts/build_diagram.py` — as imagens nunca devem ser editadas
manualmente; qualquer ajuste de arquitetura deve alterar o script e
regenerar.

## Como regenerar

```bash
brew install graphviz          # ou: apt-get install graphviz
python3 -m venv .venv && source .venv/bin/activate
pip install diagrams
python3 docs/architecture/scripts/build_diagram_local_dev.py
python3 docs/architecture/scripts/build_diagram.py
mv sentinelhealth_architecture*.* docs/architecture/
```

## Diagrama 1 — Local / Dev (o que já está montado e testado)

Reflete `compose.yaml`, o override opcional `compose.aws-dev.yaml` e o
ambiente Terraform `infra/environments/dev/` (S3+SQS+KMS mínimos, sem
VPC/ECS/RDS — ver `infra/environments/dev/README.md`). Mostra os dois
submodos que coexistem hoje na MESMA base de código/containers:

- **Modo 100% local** (`docker compose -f compose.yaml up`): frontend
  (nginx), backend (FastAPI/uvicorn) e Postgres em containers Docker na
  máquina do desenvolvedor. Adaptadores `LOCAL` para storage (filesystem),
  fila (tabela Postgres), LLM (template determinístico) e transcrição/
  visão (retornam `UNAVAILABLE` honesto — nunca fabricam resultado). Zero
  chamada de rede externa.
- **Modo dev conectado à AWS real** (override
  `-f compose.yaml -f compose.aws-dev.yaml`): os MESMOS containers, sem
  nenhuma imagem diferente — apenas variáveis de ambiente trocadas
  (`MEDIA_STORAGE_BACKEND=S3`, `TRANSCRIPTION_PROVIDER=AWS_TRANSCRIBE`,
  feature flags de Rekognition ligadas) e uma cópia **isolada e read-only**
  das credenciais AWS do desenvolvedor (`~/.aws-sentinelhealth-dev` — nunca
  o `~/.aws` completo). Conecta a um bucket S3, fila SQS e chave KMS reais
  provisionados na conta AWS 479844459009, deliberadamente **sem**
  VPC/ECS/RDS (o Postgres continua sendo o container local).
- Este é o ambiente onde a integração com Amazon Transcribe e Amazon
  Rekognition (Image/Video) foi validada de ponta a ponta com dados reais
  antes de qualquer decisão de subir para produção.

## Diagrama 2 — Arquitetura AWS de produção/homologação (alvo)

Reflete o ambiente `production`/`homologation` definido em
`infra/environments/production/` (topologia idêntica entre os dois,
variando apenas tamanho/replicas — ver `infra/modules/*`), **não** o
ambiente `dev` local (que só provisiona S3+SQS+KMS mínimos para testar
localmente contra AWS real — ver `infra/environments/dev/README.md`).

Componentes confirmados na Terraform (`infra/modules/`):

- **Rede**: 1 VPC (3 AZs em produção), subnets públicas (ALB + NAT
  Gateway, 1 por AZ em produção) e privadas (ECS Fargate + RDS), Security
  Groups em cadeia (`ALB → ECS → RDS`, banco nunca público).
- **Computação**: 1 cluster ECS Fargate com **5 serviços** — 1 API (atrás
  do ALB, 3 réplicas em produção) + 4 workers sem ALB que consomem a fila
  SQS: `orchestrator` (máquina de estados), `audio` (transcrição + NLP),
  `video-image` (visão computacional self-hosted — OpenPose + YOLOv8 +
  ffmpeg, maior CPU/memória alocada) e `report` (PDF + síntese LLM). Cada
  serviço tem sua própria IAM task role (least privilege).
- **Dados**: Amazon RDS PostgreSQL 16, Multi-AZ em produção, fonte única
  de verdade (nunca o LLM/estatística).
- **Mensageria**: 1 fila SQS principal + DLQ, KMS-encriptadas.
- **Armazenamento**: 1 bucket S3 (mídia), com progressão de prefixos
  `quarantine/ → approved/ → generated/`, versionado, SSE-KMS, upload
  direto do navegador via URL pré-assinada (a API nunca é proxy de
  arquivo).
- **Identidade**: Amazon Cognito (OIDC, MFA obrigatório em produção, sem
  self-signup — contas só são criadas pelo admin).
- **Segurança**: AWS KMS (uma CMK por ambiente, criptografa RDS/S3/SQS/
  Secrets/logs), Secrets Manager (chave OpenAI + credenciais do RDS).
- **Registro de imagens**: Amazon ECR (2 repositórios — `api` e `worker`,
  os 4 workers compartilham o repositório `worker` diferenciados por tag).
- **Observabilidade**: CloudWatch Logs (retenção 365 dias em produção).
- **Serviços AWS gerenciados chamados em runtime (via boto3, fora do que é
  provisionado por Terraform — não têm recurso próprio, só permissão
  IAM)**: Amazon Transcribe (transcrição de áudio, batch, pt-BR) e Amazon
  Rekognition Image/Video (enriquecimento **opcional e complementar**,
  nunca substitui o worker self-hosted de pose/detecção — decisão
  registrada na ADR 0016).
- **Terceiro fora da AWS**: OpenAI (síntese textual explicativa a partir
  de uma allowlist de campos já minimizados — nunca decide o nível de
  risco clínico, que vem sempre do motor de regras determinístico).

## Gap conhecido (para levar ao comitê)

**Não há infraestrutura de hospedagem do frontend em produção ainda** —
nenhum módulo Terraform para CloudFront/S3 estático existe hoje
(confirmado em `infra/modules/`). O frontend atualmente só roda como
container nginx local (`compose.yaml`, dev). Isso precisa ser endereçado
antes de um deploy real de produção — não é uma omissão do diagrama, é uma
lacuna real da infraestrutura atual.

## CI/CD

O pipeline (`.github/workflows/ci.yml`) hoje faz apenas lint/testes/build
(backend + frontend) e scan de segurança (gitleaks, pip-audit). **Não há
deploy automatizado para a AWS** (sem push para ECR nem atualização de
serviço ECS) — por isso o diagrama mostra a seta `build/push` para o ECR
como manual/tracejada, não um pipeline de CD real.
