output "endpoint" {
  value = aws_db_instance.this.endpoint
}

output "port" {
  value = aws_db_instance.this.port
}

output "database_name" {
  value = aws_db_instance.this.db_name
}

output "master_user_secret_arn" {
  description = "ARN do secret gerenciado pelo RDS com as credenciais master (leitura via IAM, nunca via Terraform state)."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "instance_arn" {
  value = aws_db_instance.this.arn
}
