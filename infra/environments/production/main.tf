module "kms" {
  source       = "../../modules/kms"
  project_name = var.project_name
  environment  = var.environment
  tags         = var.tags
}

module "network" {
  source              = "../../modules/network"
  project_name        = var.project_name
  environment         = var.environment
  vpc_cidr            = var.vpc_cidr
  availability_zones  = var.availability_zones
  single_nat_gateway  = var.single_nat_gateway
  tags                = var.tags
}

module "storage" {
  source       = "../../modules/storage"
  project_name = var.project_name
  environment  = var.environment
  kms_key_arn  = module.kms.key_arn
  tags         = var.tags
}

module "queue" {
  source       = "../../modules/queue"
  project_name = var.project_name
  environment  = var.environment
  kms_key_arn  = module.kms.key_arn
  tags         = var.tags
}

module "database" {
  source                 = "../../modules/database"
  project_name           = var.project_name
  environment            = var.environment
  private_subnet_ids     = module.network.private_subnet_ids
  security_group_id      = module.network.rds_security_group_id
  kms_key_arn             = module.kms.key_arn
  instance_class          = var.db_instance_class
  allocated_storage_gb    = var.db_allocated_storage_gb
  multi_az                = var.db_multi_az
  backup_retention_days   = var.db_backup_retention_days
  deletion_protection     = var.db_deletion_protection
  tags                    = var.tags
}

module "identity" {
  source             = "../../modules/identity"
  project_name       = var.project_name
  environment        = var.environment
  callback_urls      = var.cognito_callback_urls
  logout_urls        = var.cognito_logout_urls
  mfa_configuration  = var.cognito_mfa_configuration
  tags               = var.tags
}

module "secrets" {
  source       = "../../modules/secrets"
  project_name = var.project_name
  environment  = var.environment
  kms_key_arn  = module.kms.key_arn
  tags         = var.tags
}

module "ecr" {
  source       = "../../modules/ecr"
  project_name = var.project_name
  environment  = var.environment
  tags         = var.tags
}

module "ecs" {
  source                 = "../../modules/ecs"
  project_name           = var.project_name
  environment            = var.environment
  vpc_id                 = module.network.vpc_id
  public_subnet_ids      = module.network.public_subnet_ids
  private_subnet_ids     = module.network.private_subnet_ids
  alb_security_group_id  = module.network.alb_security_group_id
  ecs_security_group_id  = module.network.ecs_security_group_id
  api_image               = var.api_image
  api_desired_count       = var.api_desired_count
  workers                 = var.workers
  database_secret_arn     = module.database.master_user_secret_arn
  openai_secret_arn       = module.secrets.openai_api_key_secret_arn
  media_bucket_arn        = module.storage.bucket_arn
  queue_arn               = module.queue.queue_arn
  dlq_arn                 = module.queue.dlq_arn
  kms_key_arn             = module.kms.key_arn
  log_retention_days      = var.log_retention_days
  cognito_user_pool_id    = module.identity.user_pool_id
  cognito_client_id       = module.identity.user_pool_client_id
  cognito_issuer_url      = module.identity.issuer_url
  tags                    = var.tags
}
