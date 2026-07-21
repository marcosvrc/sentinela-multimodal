/**
 * Segredos de aplicacao que nao sao gerenciados por outro servico AWS.
 * A credencial do PostgreSQL NAO esta aqui - e gerenciada pelo proprio RDS
 * (ver modules/database, `manage_master_user_password`). Este modulo cria
 * apenas o secret vazio para a chave da OpenAI: o VALOR e definido fora do
 * Terraform (`aws secretsmanager put-secret-value`, por pessoal autorizado
 * - ESCOPO_PROJETO.md secao 6.9), nunca commitado no state nem no
 * repositorio.
 */

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  name       = "${local.name_prefix}/openai-api-key"
  kms_key_id = var.kms_key_arn

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-openai-api-key"
  })
}

# O valor inicial e um placeholder obviamente invalido: forca quem sobe o
# ambiente a substituir explicitamente antes do LLM_PROVIDER=OPENAI
# funcionar, em vez de falhar silenciosamente com uma chave vazia.
resource "aws_secretsmanager_secret_version" "openai_api_key_placeholder" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = "REPLACE_ME_VIA_AWS_CLI_OU_CONSOLE"

  lifecycle {
    ignore_changes = [secret_string]
  }
}
