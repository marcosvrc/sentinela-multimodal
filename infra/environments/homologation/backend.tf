# Estado remoto com locking (ESCOPO_PROJETO.md secao 6.3: "Terraform com
# modulos, estados remotos, locking e ambientes separados").
#
# O bucket de state e a tabela de lock sao provisionados manualmente uma
# unica vez, fora deste Terraform (problema da "galinha e do ovo" de estado
# remoto), com versionamento e SSE-KMS habilitados. Substitua os valores de
# `bucket`/`dynamodb_table` pelos recursos reais antes do primeiro `init`.
terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "sentinelhealth-terraform-state-homologation"
    key            = "homologation/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "sentinelhealth-terraform-locks-homologation"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}
