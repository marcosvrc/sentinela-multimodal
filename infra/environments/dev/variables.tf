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
  default = "dev"
}

variable "noncurrent_version_retention_days" {
  description = "Ver ADR 0015 - placeholder configuravel, nao o prazo final de governanca."
  type        = number
  default     = 30
}

variable "queue_visibility_timeout_seconds" {
  description = "Deve ser maior que o tempo maximo de processamento de uma mensagem por um worker local."
  type        = number
  default     = 300
}

variable "tags" {
  type = map(string)
  default = {
    Project     = "sentinelhealth"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
