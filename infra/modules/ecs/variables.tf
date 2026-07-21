variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "alb_security_group_id" {
  type = string
}

variable "ecs_security_group_id" {
  type = string
}

variable "api_image" {
  description = "URI completa da imagem da API no ECR, com tag pelo commit (ex: <repo_url>:<sha>)."
  type        = string
}

variable "api_cpu" {
  type    = number
  default = 512
}

variable "api_memory" {
  type    = number
  default = 1024
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "workers" {
  description = <<-EOT
    Um worker por processo (ESCOPO_PROJETO.md secao 6.9: "cada processo tera
    IAM Role proprio: API, worker de audio, worker de video/imagem, worker
    de relatorio e orquestrador nao compartilharao permissoes amplas").
    Chave = nome logico do worker (ex: "audio", "video-image", "orchestrator").
  EOT
  type = map(object({
    image         = string
    cpu           = number
    memory        = number
    desired_count = number
    command       = optional(list(string))
  }))
}

variable "database_secret_arn" {
  description = "ARN do secret master do RDS (modules/database.master_user_secret_arn)."
  type        = string
}

variable "openai_secret_arn" {
  type = string
}

variable "media_bucket_arn" {
  type = string
}

variable "queue_arn" {
  type = string
}

variable "dlq_arn" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "log_retention_days" {
  type    = number
  default = 90
}

variable "cognito_user_pool_id" {
  description = "ID do User Pool (modules/identity.user_pool_id). homologation/production sempre usam COGNITO."
  type        = string
}

variable "cognito_client_id" {
  type = string
}

variable "cognito_issuer_url" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
