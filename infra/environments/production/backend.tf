# Estado remoto com locking (ESCOPO_PROJETO.md secao 6.3). Ver comentario
# equivalente em environments/homologation/backend.tf - mesma logica, bucket
# e tabela de lock proprios de production.
terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "sentinelhealth-terraform-state-production"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "sentinelhealth-terraform-locks-production"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}
