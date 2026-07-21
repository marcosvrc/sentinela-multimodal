output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.this.arn
}

output "alb_dns_name" {
  value = aws_lb.api.dns_name
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "worker_service_names" {
  value = { for k, s in aws_ecs_service.worker : k => s.name }
}

output "execution_role_arn" {
  value = aws_iam_role.execution.arn
}

output "task_role_arns" {
  value = { for k, r in aws_iam_role.task : k => r.arn }
}
