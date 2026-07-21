/**
 * Amazon Cognito User Pool exclusivo do projeto (ADR 0007), usado como
 * provedor OIDC. Papeis (UserRole) e institution_id NAO vivem em atributos
 * customizados do Cognito - continuam resolvidos pelo backend a partir de
 * `app.identity` (PostgreSQL), evitando duas fontes de verdade para
 * autorizacao (ver app/core/security.py::get_current_user).
 */

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

data "aws_region" "current" {}

resource "aws_cognito_user_pool" "this" {
  name = "${local.name_prefix}-users"

  mfa_configuration = var.mfa_configuration

  dynamic "software_token_mfa_configuration" {
    for_each = var.mfa_configuration == "OFF" ? [] : [1]
    content {
      enabled = true
    }
  }

  password_policy {
    minimum_length                  = 12
    require_lowercase               = true
    require_uppercase               = true
    require_numbers                 = true
    require_symbols                 = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-users"
  })
}

resource "aws_cognito_user_pool_client" "frontend" {
  name         = "${local.name_prefix}-frontend"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = false

  allowed_oauth_flows                 = ["code"]
  allowed_oauth_scopes                = ["openid", "email", "profile"]
  allowed_oauth_flows_user_pool_client = true

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  supported_identity_providers = ["COGNITO"]

  prevent_user_existence_errors = "ENABLED"

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 12

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "hours"
  }
}

resource "aws_cognito_user_pool_domain" "this" {
  domain       = "${local.name_prefix}-auth"
  user_pool_id = aws_cognito_user_pool.this.id
}
