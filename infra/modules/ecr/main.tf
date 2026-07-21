/**
 * Registro de imagens (ESCOPO_PROJETO.md secao 6.3: "Amazon ECR com imagens
 * identificadas pelo commit"). Um repositorio por imagem logica (api,
 * worker) - a imagem do worker de visao computacional (OpenPose/YOLO, ADR
 * 0006) usa um repositorio proprio por ser maior e ter dependencias
 * distintas dos workers CPU genericos.
 */

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

resource "aws_ecr_repository" "this" {
  for_each = toset(var.repository_names)

  name                 = "${local.name_prefix}-${each.value}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-${each.value}"
  })
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = aws_ecr_repository.this

  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Mantem apenas as N imagens mais recentes"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.image_retention_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
