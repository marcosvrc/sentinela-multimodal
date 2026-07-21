output "s3_media_bucket" {
  description = "Valor para S3_MEDIA_BUCKET e TRANSCRIPTION_OUTPUT_BUCKET no .env local."
  value       = module.storage.bucket_name
}

output "sqs_analysis_queue_url" {
  description = "Valor para SQS_ANALYSIS_QUEUE_URL no .env local."
  value       = module.queue.queue_url
}

output "sqs_analysis_dlq_url" {
  description = "Valor para SQS_ANALYSIS_DLQ_URL no .env local."
  value       = module.queue.dlq_url
}

output "kms_key_arn" {
  value = module.kms.key_arn
}
