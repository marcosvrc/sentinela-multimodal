/**
 * Bucket S3 de midias, derivados e relatorios (ADR 0003).
 *
 * Prazos de retencao definitivos ainda nao foram aprovados (ADR 0015 -
 * "a tabela de retencao definitiva sera aprovada antes do uso com dados
 * reais"); a regra de ciclo de vida abaixo usa `noncurrent_version_retention_days`
 * como placeholder configuravel, nao como o prazo final de governanca.
 */

locals {
  bucket_name = "${var.project_name}-${var.environment}-media"
}

resource "aws_s3_bucket" "media" {
  bucket = local.bucket_name

  tags = merge(var.tags, {
    Name = local.bucket_name
  })
}

resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket = aws_s3_bucket.media.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_retention_days
    }
  }

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# CORS necessario para upload direto do navegador via URL pre-assinada
# (ESCOPO_PROJETO.md secao 6.6: "o backend nao recebera arquivos grandes
# como intermediario").
resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  cors_rule {
    allowed_methods = ["PUT", "GET"]
    allowed_origins  = ["*"] # restringir ao dominio real do frontend antes de producao
    allowed_headers  = ["*"]
    max_age_seconds  = 3000
  }
}
