variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "repository_names" {
  description = "Nomes logicos dos repositorios (ex: [\"api\", \"worker\"])."
  type        = list(string)
  default     = ["api", "worker"]
}

variable "image_retention_count" {
  description = "Quantidade de imagens mais recentes mantidas por repositorio."
  type        = number
  default     = 20
}

variable "tags" {
  type    = map(string)
  default = {}
}
