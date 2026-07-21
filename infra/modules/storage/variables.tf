variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "kms_key_arn" {
  description = "Chave KMS usada para criptografar o bucket (modulo secrets/kms)."
  type        = string
}

variable "noncurrent_version_retention_days" {
  description = "Dias de retencao de versoes antigas antes de expirar (ADR 0015 - politica de retencao)."
  type        = number
  default     = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}
