# Ambiente "dev" — AWS real, backend/worker rodando local

Este ambiente cria **apenas** os recursos AWS minimos necessarios para o
backend/worker rodarem na sua maquina (via `compose.yaml`, fora deste
Terraform) usando servicos AWS reais em vez dos adaptadores `LOCAL`:

- Bucket S3 (mídia + saida do Transcribe)
- Fila SQS principal + DLQ
- Chave KMS para criptografar os dois acima

Deliberadamente **nao** inclui VPC, RDS, ECS, ALB, Cognito ou Secrets
Manager — isso e infraestrutura de deploy (`environments/homologation`,
`environments/production`), fora do escopo aqui. Autenticacao continua
usando o adaptador `LOCAL` (`X-Dev-Subject`) e o Postgres continua sendo o
container do `compose.yaml`.

## Video/imagem: Amazon Rekognition e sempre COMPLEMENTAR, nunca substitui

A ADR 0016 avaliou e **rejeitou** usar Amazon Rekognition como MOTOR
PRINCIPAL das modalidades de video e imagem — o worker de video continua
usando OpenPose+YOLOv8 self-hosted (ADR 0006) porque o Rekognition nao faz
estimativa de pose articulada, e a imagem continua usando a heuristica de
pixel local como classificacao primaria. Ver
`docs/adr/0016-avaliacao-componentes-aws-gerenciados.md`.

A ADR tambem registrou Rekognition Image/Video como **enriquecimento
opcional e futuro** - essa evolucao foi implementada: com as feature flags
`image_recognition_enabled`/`vision_rekognition_video_enabled` ligadas
(tela `/admin/feature-flags`), os processadores de imagem/video chamam
`rekognition:DetectLabels` (imagem, sincrono) e
`rekognition:StartLabelDetection`/`GetLabelDetection` (video, assincrono
como o Transcribe) sobre o MESMO bucket/objeto `approved/` ja usado pelo
Transcribe - nenhum recurso Terraform novo e necessario, apenas a
permissao IAM `RekognitionRuntime` (ja incluida na policy deste ambiente).
O achado gerado e sempre um `MODEL_OBSERVATION` separado do achado do
worker self-hosted, nunca misturado ou substituindo-o.

Amazon Transcribe (audio) e Amazon Rekognition (imagem/video) sao, hoje,
os casos onde "AWS real" = ligar um servico gerenciado sem trabalho de
codigo adicional no worker.

## LLM: Amazon Bedrock como alternativa ao OpenAI (mesmo Protocol)

`app.integrations.llm.bedrock_adapter.BedrockLlmAdapter` implementa o
mesmo `LlmAdapter` Protocol de `OpenAiLlmAdapter`, usando a Converse API
com Structured Outputs (`outputConfig.textFormat`, GA desde 2026-02) para
a mesma garantia de schema rigido que o `response_format=json_schema
strict` da OpenAI oferece - o modelo fisicamente nao consegue devolver um
campo fora do schema definido (nunca `risk_level`/conduta).

Diferenca principal: usa as MESMAS credenciais IAM do processo ja usadas
por S3/SQS/Transcribe/Rekognition (`boto3`), nunca uma chave de API
externa - so a permissao `BedrockRuntime` (ja incluida na policy deste
ambiente) e necessaria, mais o acesso ao modelo liberado explicitamente no
console Bedrock da conta/regiao (Bedrock exige "model access" habilitado
por modelo antes do primeiro `InvokeModel`/`Converse` funcionar).

Selecionavel na tela `/admin/feature-flags` (`llm_provider=BEDROCK`,
`llm_bedrock_model` escolhe o modelo - Claude 3.5 Sonnet/Haiku ou Amazon
Nova Pro/Lite na lista curada atual). Nenhum recurso Terraform novo e
necessario.

## Texto/audio: Amazon Comprehend para analise de sentimento (sempre CONTEXTUAL)

`app.integrations.sentiment_analysis` (Amazon Comprehend `DetectSentiment`)
roda sobre o texto adicional da analise (`app.processors.text`) e sobre a
transcricao de audio quando disponivel (`app.processors.audio`) -
ESCOPO_PROJETO.md secao 4.2: "Analise de sentimento, quando utilizada,
sera apenas contextual e nunca determinara risco clinico". O achado
gerado (`nature=MODEL_OBSERVATION`) NUNCA alcanca o prompt do LLM de
consolidacao de risco (`app.risk_consolidation.service` so envia achados
`nature=ORIGINAL_DATA`) - fica visivel apenas no laudo, como qualquer
outra observacao derivada de modelo.

Diferente do Amazon Comprehend Medical (so ingles dos EUA), o Comprehend
padrao usado aqui suporta portugues (`pt`) - por isso e viavel para a
cadeia principal do projeto (ver ADR 0016).

Selecionavel na tela `/admin/feature-flags`
(`sentiment_analysis_enabled`). Requer apenas a permissao IAM
`ComprehendRuntime` (ja incluida na policy deste ambiente) - nenhum
recurso Terraform novo e necessario.

## Passo 1 — permissao IAM

O usuario IAM usado localmente (`profile fase4` neste projeto) precisa de
uma politica adicional antes do `terraform apply` funcionar — hoje ele nao
tem permissao nem para listar buckets. Peca ao administrador da conta
`479844459009` para criar a policy em
`infra/iam-policies/sentinelhealth-dev-local-aws-policy.json` como
**managed policy** (nao inline) e anexa-la ao usuario:

```bash
aws iam create-policy \
  --policy-name sentinelhealth-dev-local-aws \
  --policy-document file://infra/iam-policies/sentinelhealth-dev-local-aws-policy.json

aws iam attach-user-policy \
  --user-name fase4 \
  --policy-arn arn:aws:iam::479844459009:policy/sentinelhealth-dev-local-aws
```

**Importante:** o JSON minificado tem ~2135 caracteres, acima do limite de
2048 de uma *inline* user policy (`aws iam put-user-policy` ou "Add inline
policy" no console falha com "X characters exceeding quota"). Managed
policies tem limite de 6144 caracteres — use `create-policy` +
`attach-user-policy` (ou "Create policy" + "Attach policies directly" no
console), nunca inline. Ela concede apenas:

- Terraform state (bucket/tabela de lock ja existentes, reaproveitados de
  homologation com uma `key` separada — ver `backend.tf`)
- Criar/gerenciar a chave KMS `alias/sentinelhealth-dev`
- Criar/gerenciar buckets `sentinelhealth-dev-*` e filas
  `sentinelhealth-dev-*`
- Chamar `transcribe:StartTranscriptionJob`/`GetTranscriptionJob`/
  `DeleteTranscriptionJob` em runtime (Transcribe nao suporta permissao por
  ARN de job nestas acoes, por isso e `Resource: "*"` so para essas 3
  acoes especificas)

### Atualizando a policy depois de uma correcao

Se a policy ja foi criada como managed policy e precisar de um ajuste (ex.:
uma acao adicional descoberta durante o `apply`), IAM managed policies sao
versionadas - nao dá para so re-rodar `create-policy` com o mesmo nome. Use
`create-policy-version`:

```bash
aws iam create-policy-version \
  --policy-arn arn:aws:iam::479844459009:policy/sentinelhealth-dev-local-aws \
  --policy-document file://infra/iam-policies/sentinelhealth-dev-local-aws-policy.json \
  --set-as-default
```

(Managed policies guardam no maximo 5 versoes - se atingir o limite, delete
uma versao antiga com `aws iam delete-policy-version` antes de criar outra.)

## Passo 2 — terraform apply

```bash
cd infra/environments/dev
AWS_PROFILE=fase4 terraform init
AWS_PROFILE=fase4 terraform plan
AWS_PROFILE=fase4 terraform apply
```

## Passo 3 — copiar os outputs para o `.env` local

```bash
AWS_PROFILE=fase4 terraform output
```

Preencha no `.env` da raiz do projeto (nao commitar):

```dotenv
AWS_REGION=us-east-1
S3_MEDIA_BUCKET=<output: s3_media_bucket>
TRANSCRIPTION_OUTPUT_BUCKET=<output: s3_media_bucket>   # mesmo bucket, prefixo "transcriptions/" já usado pelo adaptador
SQS_ANALYSIS_QUEUE_URL=<output: sqs_analysis_queue_url>
SQS_ANALYSIS_DLQ_URL=<output: sqs_analysis_dlq_url>

MEDIA_STORAGE_BACKEND=S3
TRANSCRIPTION_PROVIDER=AWS_TRANSCRIBE
```

`IDENTITY_PROVIDER` e `LLM_PROVIDER` ficam como estao (`LOCAL`/`OPENAI`) —
nao fazem parte deste ambiente.

## Passo 4 — credenciais AWS no container (isoladas, nunca o `~/.aws` completo)

O `boto3` dentro do container `backend` precisa de credenciais para
assumir a mesma identidade do seu `profile fase4`. Em vez de montar o seu
`~/.aws` real (que pode conter outros perfis/contas, incluindo o
`[default]`), crie uma copia MINIMA e isolada, uma unica vez:

```bash
mkdir -p ~/.aws-sentinelhealth-dev
chmod 700 ~/.aws-sentinelhealth-dev

# extrai so a secao [fase4] do seu ~/.aws/credentials real e renomeia
# para [default] (o container nao precisa saber o nome do profile)
awk '/^\[fase4\]/{flag=1; print; next} /^\[/{flag=0} flag' ~/.aws/credentials \
  | sed 's/^\[fase4\]/[default]/' > ~/.aws-sentinelhealth-dev/credentials
chmod 600 ~/.aws-sentinelhealth-dev/credentials

printf '[default]\nregion = us-east-1\noutput = json\n' > ~/.aws-sentinelhealth-dev/config
chmod 600 ~/.aws-sentinelhealth-dev/config
```

Esse diretorio fica FORA do repositorio (na sua home), nunca e commitado e
nunca e lido/exibido por ferramentas do projeto - so existe para ser
montado read-only no container.

## Passo 5 — subir com o override de AWS

`compose.aws-dev.yaml` (raiz do repo) e um override OPCIONAL que monta
`~/.aws-sentinelhealth-dev` (read-only) no container `backend`. Ele nunca
entra em vigor a menos que voce combine explicitamente os dois arquivos
com `-f`:

```bash
docker compose -f compose.yaml -f compose.aws-dev.yaml up -d --build backend
```

Para voltar ao modo 100% local (sem AWS), basta usar `docker compose -f
compose.yaml up -d --build backend` normalmente - o override nunca e
aplicado por padrao.

Confirme que o backend inicializou sem erro (`docker compose logs backend`)
e teste o fluxo completo de upload de audio + submissao de analise; o
`AwsTranscribeAdapter` fara a chamada real ao Transcribe.

**Cuidado com credenciais:**
- O diretorio `~/.aws-sentinelhealth-dev` tem permissao `700`/`600` (so o
  seu usuario le) e fica fora do repositorio - nunca sera commitado.
- O volume no `compose.aws-dev.yaml` e sempre `:ro` (read-only) - o
  container nunca escreve nessas credenciais.
- Nunca cole o conteudo de `~/.aws/credentials` ou
  `~/.aws-sentinelhealth-dev/credentials` em chat, log, commit ou issue.
- Se as credenciais do profile `fase4` forem rotacionadas/revogadas,
  repita o Passo 4 para atualizar a copia isolada.

## Destruir

```bash
AWS_PROFILE=fase4 terraform destroy
```

O bucket S3 tem versionamento habilitado — objetos de teste enviados
durante o desenvolvimento ficam retidos como versoes nao-atuais até o
prazo de `noncurrent_version_retention_days` (30 dias neste ambiente); um
`destroy` completo do bucket exige esvaziar todas as versoes primeiro
(`aws s3api list-object-versions` + `delete-objects`, ou
`force_destroy = true` no recurso caso queira evitar esse passo manual em
um ambiente descartavel como este).
