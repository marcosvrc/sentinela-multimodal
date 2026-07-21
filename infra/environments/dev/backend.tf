# Estado remoto com locking, reaproveitando o MESMO bucket/tabela ja
# provisionados manualmente para homologation (ver comentario em
# environments/homologation/backend.tf) - nao criamos um novo bucket de
# state so para este ambiente dev; usamos uma `key` (prefixo) diferente
# dentro do bucket existente para nao colidir com o state de homologation.
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
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "sentinelhealth-terraform-locks-homologation"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
  # Sem `profile` fixo aqui de proposito - defina a credencial via
  # `AWS_PROFILE=fase4` no ambiente antes de rodar `terraform`, no mesmo
  # padrao usado pelos comandos `aws` documentados no README deste
  # diretorio.
}
