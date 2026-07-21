/**
 * Chave KMS unica do projeto/ambiente para criptografar S3, RDS e Secrets
 * Manager (ESCOPO_PROJETO.md secao 6.2: "AWS KMS e Secrets Manager: chaves
 * de criptografia e segredos de aplicacao").
 */

locals {
  alias_name = "alias/${var.project_name}-${var.environment}"
}

resource "aws_kms_key" "this" {
  description             = "Chave de criptografia do SentinelHealth (${var.environment})."
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-kms"
  })
}

resource "aws_kms_alias" "this" {
  name          = local.alias_name
  target_key_id = aws_kms_key.this.key_id
}
