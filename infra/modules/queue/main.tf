/**
 * Fila principal de analises + DLQ (ADR 0004: "cada fila principal possui
 * uma Dead Letter Queue associada; falhas transitorias sao reenfileiradas
 * com backoff exponencial ate um limite de tentativas").
 *
 * Mensagens carregam apenas identificadores e metadados minimos
 * (ESCOPO_PROJETO.md secao 6.6) - nada aqui precisa de criptografia de
 * payload alem da criptografia gerenciada padrao do SQS com a chave KMS do
 * projeto.
 */

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${local.name_prefix}-analysis-dlq"
  message_retention_seconds = var.message_retention_seconds
  kms_master_key_id         = var.kms_key_arn

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-analysis-dlq"
  })
}

resource "aws_sqs_queue" "main" {
  name                       = "${local.name_prefix}-analysis-queue"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  kms_master_key_id          = var.kms_key_arn

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-analysis-queue"
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.main.arn]
  })
}
