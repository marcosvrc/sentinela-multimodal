/**
 * Ambiente "dev": recursos AWS MINIMOS para permitir que o backend/worker
 * rodando LOCALMENTE (docker compose, fora deste Terraform) se conecte a
 * servicos AWS reais (S3, SQS, Transcribe) em vez dos adaptadores LOCAL
 * (ver ESCOPO_PROJETO.md secao 12.1.3 e app/storage, app/queue,
 * app/integrations/transcription).
 *
 * Deliberadamente NAO inclui VPC, RDS, ECS, ALB, Cognito ou Secrets
 * Manager - isso e infraestrutura de DEPLOY (ver environments/homologation
 * e environments/production), fora do escopo de "rodar local conectado a
 * AWS". O Postgres, a API e os workers continuam rodando via
 * docker-compose.yaml na maquina do desenvolvedor.
 *
 * Amazon Transcribe nao tem um recurso Terraform provisionavel (jobs sao
 * efemeros, criados em runtime pelo proprio adaptador -
 * app/integrations/transcription/aws_transcribe.py) - por isso nao ha
 * modulo/recurso "transcribe" aqui; a permissao de chamar a API roda por
 * fora, concedida diretamente ao usuario IAM via
 * infra/iam-policies/sentinelhealth-dev-local-aws-policy.json.
 */

module "kms" {
  source       = "../../modules/kms"
  project_name = var.project_name
  environment  = var.environment
  tags         = var.tags
}

module "storage" {
  source                            = "../../modules/storage"
  project_name                      = var.project_name
  environment                       = var.environment
  kms_key_arn                       = module.kms.key_arn
  noncurrent_version_retention_days = var.noncurrent_version_retention_days
  tags                              = var.tags
}

module "queue" {
  source                     = "../../modules/queue"
  project_name               = var.project_name
  environment                = var.environment
  kms_key_arn                = module.kms.key_arn
  visibility_timeout_seconds = var.queue_visibility_timeout_seconds
  tags                       = var.tags
}
