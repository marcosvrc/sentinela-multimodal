variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "callback_urls" {
  description = "URLs de redirecionamento pos-login do frontend."
  type        = list(string)
}

variable "logout_urls" {
  type = list(string)
}

variable "mfa_configuration" {
  description = "OFF | OPTIONAL | ON. Recomendado ON em production (dados de saude)."
  type        = string
  default     = "OPTIONAL"
}

variable "tags" {
  type    = map(string)
  default = {}
}
