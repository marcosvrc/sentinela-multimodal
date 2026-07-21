variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "sentinelhealth"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "vpc_cidr" {
  type    = string
  default = "10.30.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "single_nat_gateway" {
  description = "Production usa um NAT Gateway por AZ (alta disponibilidade) - nunca true aqui."
  type        = bool
  default     = false
}

variable "db_instance_class" {
  type    = string
  default = "db.r6g.large"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 200
}

variable "db_multi_az" {
  type    = bool
  default = true
}

variable "db_backup_retention_days" {
  type    = number
  default = 30
}

variable "db_deletion_protection" {
  type    = bool
  default = true
}

variable "cognito_mfa_configuration" {
  description = "Dados de saude - MFA obrigatorio em production (ON)."
  type        = string
  default     = "ON"
}

variable "cognito_callback_urls" {
  type    = list(string)
  default = ["https://app.sentinelhealth.example.com/auth/callback"]
}

variable "cognito_logout_urls" {
  type    = list(string)
  default = ["https://app.sentinelhealth.example.com/logout"]
}

variable "api_image" {
  description = "Imagem da API (repo do ECR + tag pelo commit). Definido no pipeline de deploy."
  type        = string
}

variable "api_desired_count" {
  description = "Production roda com mais replicas por padrao (definido via modules/ecs default se nao sobrescrito aqui)."
  type        = number
  default     = 3
}

variable "workers" {
  description = "Ver infra/modules/ecs/variables.tf - um worker por processo."
  type = map(object({
    image         = string
    cpu           = number
    memory        = number
    desired_count = number
    command       = optional(list(string))
  }))
  default = {
    audio = {
      image         = "REPLACE_ME"
      cpu           = 1024
      memory        = 2048
      desired_count = 2
    }
    video-image = {
      image         = "REPLACE_ME"
      cpu           = 2048
      memory        = 4096
      desired_count = 2
    }
    report = {
      image         = "REPLACE_ME"
      cpu           = 512
      memory        = 1024
      desired_count = 2
    }
    orchestrator = {
      image         = "REPLACE_ME"
      cpu           = 512
      memory        = 1024
      desired_count = 2
    }
  }
}

variable "log_retention_days" {
  type    = number
  default = 365
}

variable "tags" {
  type = map(string)
  default = {
    Project     = "sentinelhealth"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
