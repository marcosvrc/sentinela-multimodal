variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "max_receive_count" {
  description = "Tentativas antes de mover a mensagem para a DLQ (ADR 0004)."
  type        = number
  default     = 5
}

variable "visibility_timeout_seconds" {
  description = "Deve ser maior que o tempo maximo de processamento de uma mensagem por um worker."
  type        = number
  default     = 300
}

variable "message_retention_seconds" {
  type    = number
  default = 1209600 # 14 dias (maximo do SQS)
}

variable "tags" {
  type    = map(string)
  default = {}
}
