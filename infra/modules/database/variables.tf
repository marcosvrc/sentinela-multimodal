variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "security_group_id" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "master_username" {
  description = "Usuario administrativo do RDS. A senha e gerenciada pelo proprio RDS via Secrets Manager (manage_master_user_password) - nunca fixada em codigo ou variavel."
  type        = string
  default     = "sentinel_admin"
}

variable "instance_class" {
  type    = string
  default = "db.t3.medium"
}

variable "allocated_storage_gb" {
  type    = number
  default = 50
}

variable "multi_az" {
  description = "Alta disponibilidade (recomendado apenas para production)."
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "database_name" {
  type    = string
  default = "sentinelhealth"
}

variable "tags" {
  type    = map(string)
  default = {}
}
