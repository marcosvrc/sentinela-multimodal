# Infraestrutura (Terraform)

Modulos e ambientes Terraform que provisionam a infra AWS descrita nos ADRs
0003 (S3), 0004 (SQS + DLQ), 0006 (ECS Fargate), 0007 (Cognito) e na
ESCOPO_PROJETO.md secao 6.3/6.9.

```text
infra/
├── modules/
│   ├── kms/         Chave KMS unica por ambiente (criptografa S3, SQS, Secrets Manager, RDS)
│   ├── network/      VPC, subnets publicas/privadas, NAT, security groups (ALB/ECS/RDS)
│   ├── storage/      Bucket S3 de midia (versionado, SSE-KMS, lifecycle, CORS)
│   ├── queue/        SQS principal + DLQ com redrive policy (ADR 0004)
│   ├── database/      RDS Postgres (senha master gerenciada pelo proprio RDS via Secrets Manager)
│   ├── identity/      Cognito User Pool + client OIDC (ADR 0007)
│   ├── secrets/       Secret do OpenAI API key (populado manualmente, fora do Terraform)
│   ├── ecr/           Repositorios de imagem (api, worker), lifecycle por contagem
│   └── ecs/           Cluster Fargate, ALB da API, IAM role por processo, servicos (ADR 0006)
└── environments/
    ├── local/         Sem Terraform - usa docker-compose.yml (ver README na raiz)
    ├── homologation/   Composicao dos modulos acima + backend S3/DynamoDB proprio
    └── production/     Idem, com defaults mais conservadores (multi-AZ, MFA ON, deletion_protection)
```

## Principios de seguranca aplicados

- Nenhuma senha ou chave de acesso e definida em codigo Terraform ou fica no
  state: a senha master do RDS usa `manage_master_user_password` (gerenciada
  nativamente pela AWS), e o secret do OpenAI e criado com um valor
  placeholder que deve ser substituido manualmente (`aws secretsmanager
  put-secret-value` ou console), com `lifecycle.ignore_changes` para o
  Terraform nunca sobrescrever a rotacao manual.
- Uma unica chave KMS por ambiente criptografa S3, SQS, Secrets Manager e RDS.
- Cada processo de aplicacao (API, worker de audio, worker de video/imagem,
  worker de relatorio, orquestrador) recebe sua propria IAM task role,
  escopada ao minimo necessario - nenhuma role e compartilhada entre eles
  (ESCOPO_PROJETO.md secao 6.9).
- O bucket S3 bloqueia todo acesso publico; RDS nao e publicamente acessivel;
  security groups sao minimos e cruzados entre ALB/ECS/RDS.
- Estado remoto com locking (`backend.tf` de cada ambiente) - o bucket de
  state e a tabela DynamoDB de lock sao provisionados manualmente uma unica
  vez, fora deste Terraform.

## Como usar

```bash
cd infra/environments/homologation   # ou production
cp terraform.tfvars.example terraform.tfvars
# preencha terraform.tfvars com as imagens reais do ECR, URLs de callback etc.
terraform init
terraform plan
terraform apply
```

O ambiente `local` nao usa Terraform - veja `environments/local/README.md`.

## Limitacao conhecida desta versao

Os arquivos `.tf` foram validados apenas sintaticamente (parser HCL via
`python-hcl2`), sem o binario `terraform` disponivel no ambiente onde foram
escritos. Isso cobre erros de sintaxe e de nomes de variaveis/outputs entre
modulos, mas **nao** substitui `terraform validate` (checagem de schema do
provider AWS) nem `terraform plan` (checagem contra a API da AWS). Rode
ambos antes do primeiro `apply` real, idealmente via CI (ver alvo
`make tf-plan` no Makefile da raiz).
