variable "project_name" {
  description = "Prefixo usado no nome de todos os recursos (ex: sentinelhealth)."
  type        = string
}

variable "environment" {
  description = "Nome do ambiente (homologation, production)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block da VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Zonas de disponibilidade usadas (minimo 2, para alta disponibilidade do ALB/RDS)."
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "Usa um unico NAT Gateway (mais barato) em vez de um por AZ. Recomendado apenas para homologation."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags comuns aplicadas a todos os recursos do modulo."
  type        = map(string)
  default     = {}
}
