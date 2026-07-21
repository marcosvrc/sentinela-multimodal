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
  default = "homologation"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "single_nat_gateway" {
  description = "Homologacao usa um unico NAT gateway para reduzir custo."
  type        = bool
  default     = true
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 50
}

variable "db_multi_az" {
  type    = bool
  default = false
}

variable "db_backup_retention_days" {
  type    = number
  default = 7
}

variable "db_deletion_protection" {
  type    = bool
  default = false
}

variable "cognito_mfa_configuration" {
  type    = string
  default = "OPTIONAL"
}

variable "cognito_callback_urls" {
  description = "URLs de redirecionamento pos-login do frontend de homologacao."
  type        = list(string)
  default     = ["https://homolog.sentinelhealth.example.com/auth/callback"]
}

variable "cognito_logout_urls" {
  type    = list(string)
  default = ["https://homolog.sentinelhealth.example.com/logout"]
}

variable "api_image" {
  description = "Imagem da API (repo do ECR + tag pelo commit). Definido no pipeline de deploy."
  type        = string
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
      cpu           = 512
      memory        = 1024
      desired_count = 1
    }
    video-image = {
      image         = "REPLACE_ME"
      cpu           = 1024
      memory        = 2048
      desired_count = 1
    }
    report = {
      image         = "REPLACE_ME"
      cpu           = 256
      memory        = 512
      desired_count = 1
    }
    orchestrator = {
      image         = "REPLACE_ME"
      cpu           = 256
      memory        = 512
      desired_count = 1
    }
  }
}

variable "log_retention_days" {
  type    = number
  default = 90
}

variable "tags" {
  type = map(string)
  default = {
    Project     = "sentinelhealth"
    Environment = "homologation"
    ManagedBy   = "terraform"
  }
}
