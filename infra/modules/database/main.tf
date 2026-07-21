/**
 * Amazon RDS for PostgreSQL (ESCOPO_PROJETO.md secao 6.3), fonte de verdade
 * transacional (ADR 0002). A senha do usuario master NUNCA e definida por
 * Terraform: `manage_master_user_password = true` delega ao proprio RDS a
 * geracao e rotacao da senha, guardada como um secret gerenciado no Secrets
 * Manager - a API/workers leem essa credencial em runtime via IAM, nunca a
 * partir do state do Terraform (secao 6.9: "access keys permanentes nao
 * serao incluidas no codigo, .env, imagem, repositorio ou secrets do
 * CI/CD").
 */

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

resource "aws_db_subnet_group" "this" {
  name       = "${local.name_prefix}-db-subnets"
  subnet_ids = var.private_subnet_ids

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-db-subnets"
  })
}

resource "aws_db_instance" "this" {
  identifier     = "${local.name_prefix}-postgres"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.kms_key_arn

  db_name  = var.database_name
  username = var.master_username

  manage_master_user_password = true
  master_user_secret_kms_key_id = var.kms_key_arn

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible     = false

  multi_az                = var.multi_az
  backup_retention_period = var.backup_retention_days
  deletion_protection     = var.deletion_protection
  skip_final_snapshot     = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${local.name_prefix}-postgres-final" : null

  auto_minor_version_upgrade = true

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-postgres"
  })
}
