/**
 * Cluster ECS Fargate, ALB da API e um servico por processo (ADR 0006).
 *
 * IAM: a `task execution role` (usada pelo agente ECS para puxar a imagem e
 * escrever logs) e separada da `task role` usada pelo CODIGO da aplicacao
 * em runtime (ESCOPO_PROJETO.md secao 6.9). Cada processo - API e cada
 * worker do mapa `var.workers` - recebe sua PROPRIA task role, escopada ao
 * minimo necessario (S3 no prefixo do bucket, SQS da fila principal,
 * Secrets Manager apenas dos segredos que aquele processo usa). Nenhuma
 * role e compartilhada entre processos.
 */

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # aws_lb e aws_lb_target_group tem limite de 32 caracteres no "name" e
  # nao podem terminar com hifen. Truncamos apenas os nomes desses dois
  # recursos para caber no limite (os demais recursos - cluster, IAM
  # roles, log groups - nao tem esse limite e continuam usando o
  # name_prefix completo).
  lb_name = trimsuffix(substr("${local.name_prefix}-api-alb", 0, 32), "-")
  tg_name = trimsuffix(substr("${local.name_prefix}-api-tg", 0, 32), "-")
}

# --- Cluster ---

resource "aws_ecs_cluster" "this" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-cluster"
  })
}

# --- ALB publico da API ---

resource "aws_lb" "api" {
  name               = local.lb_name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-api-alb"
  })
}

resource "aws_lb_target_group" "api" {
  name        = local.tg_name
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    timeout             = 5
    matcher             = "200"
  }

  tags = var.tags
}

# HTTP puro: valido para homologation atras de um dominio proprio com HTTPS
# terminando no CDN/proxy, ou como placeholder ate um certificado ACM ser
# emitido. Producao deve substituir por um listener 443 com `aws_lb_listener`
# apontando para um `aws_acm_certificate` (fora do escopo deste modulo -
# depende do dominio real, ainda nao definido).
resource "aws_lb_listener" "api_http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# --- Logs ---

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name_prefix}/api"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "workers" {
  for_each = var.workers

  name              = "/ecs/${local.name_prefix}/worker-${each.key}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

# --- IAM: execution role compartilhada (agente ECS, nao codigo da app) ---

data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    sid       = "ReadSecretsForContainerInjection"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.database_secret_arn, var.openai_secret_arn]
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "${local.name_prefix}-ecs-execution-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

# --- IAM: task role por processo (codigo da aplicacao) ---

data "aws_iam_policy_document" "task_permissions" {
  for_each = merge({ api = {} }, var.workers)

  statement {
    sid = "MediaBucketAccess"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${var.media_bucket_arn}/*"]
  }

  statement {
    sid       = "MediaBucketList"
    actions   = ["s3:ListBucket"]
    resources = [var.media_bucket_arn]
  }

  statement {
    sid = "AnalysisQueueAccess"
    actions = [
      "sqs:SendMessage",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]
    resources = [var.queue_arn]
  }

  statement {
    sid       = "ReadOwnSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.database_secret_arn, var.openai_secret_arn]
  }
}

resource "aws_iam_role" "task" {
  for_each = merge({ api = {} }, var.workers)

  name               = "${local.name_prefix}-task-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = var.tags
}

resource "aws_iam_role_policy" "task" {
  for_each = aws_iam_role.task

  name   = "${local.name_prefix}-task-${each.key}-policy"
  role   = each.value.id
  policy = data.aws_iam_policy_document.task_permissions[each.key].json
}

# --- Servico da API ---

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task["api"].arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true
      portMappings = [
        { containerPort = 8000, protocol = "tcp" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "api"
        }
      }
      secrets = [
        { name = "DATABASE_CREDENTIALS", valueFrom = var.database_secret_arn },
        { name = "OPENAI_API_KEY", valueFrom = var.openai_secret_arn },
      ]
      environment = [
        # homologation/production sempre usam o adaptador de identidade
        # real (ESCOPO_PROJETO.md secao 5.2/6.10) - `Settings.
        # requires_real_identity_provider` tambem bloqueia o fallback
        # local mesmo que esta variavel seja alterada por engano.
        { name = "IDENTITY_PROVIDER", value = "COGNITO" },
        { name = "COGNITO_USER_POOL_ID", value = var.cognito_user_pool_id },
        { name = "COGNITO_CLIENT_ID", value = var.cognito_client_id },
        { name = "COGNITO_ISSUER_URL", value = var.cognito_issuer_url },
        { name = "ENVIRONMENT", value = var.environment },
      ]
    }
  ])

  tags = var.tags
}

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.ecs_security_group_id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name    = "api"
    container_port    = 8000
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  depends_on = [aws_lb_listener.api_http]

  tags = var.tags
}

# --- Servicos dos workers (um por processo - sem ALB, consomem a fila) ---

resource "aws_ecs_task_definition" "worker" {
  for_each = var.workers

  family                   = "${local.name_prefix}-worker-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task[each.key].arn

  container_definitions = jsonencode([
    {
      name      = "worker-${each.key}"
      image     = each.value.image
      essential = true
      command   = try(each.value.command, null)
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.workers[each.key].name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "worker-${each.key}"
        }
      }
      secrets = [
        { name = "DATABASE_CREDENTIALS", valueFrom = var.database_secret_arn },
        { name = "OPENAI_API_KEY", valueFrom = var.openai_secret_arn },
      ]
    }
  ])

  tags = var.tags
}

resource "aws_ecs_service" "worker" {
  for_each = var.workers

  name            = "${local.name_prefix}-worker-${each.key}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker[each.key].arn
  desired_count   = each.value.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.ecs_security_group_id]
  }

  tags = var.tags
}

data "aws_region" "current" {}
