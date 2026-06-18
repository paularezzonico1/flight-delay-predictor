# Root composition: network -> rds -> compute -> monitoring.

module "network" {
  source              = "./modules/network"
  name                = var.name
  vpc_cidr            = var.vpc_cidr
  public_subnet_count = var.public_subnet_count
}

module "rds" {
  source         = "./modules/rds"
  name           = var.name
  subnet_ids     = module.network.public_subnet_ids
  rds_sg_id      = module.network.rds_sg_id
  instance_class = var.db_instance_class
  db_name        = var.db_name
  db_username    = var.db_username
  db_password    = var.db_password
}

module "compute" {
  source               = "./modules/compute"
  name                 = var.name
  region               = var.region
  vpc_id               = module.network.vpc_id
  subnet_ids           = module.network.public_subnet_ids
  alb_sg_id            = module.network.alb_sg_id
  instance_sg_id       = module.network.instance_sg_id
  ecr_repo_name        = var.ecr_repo_name
  image_uri            = var.image_uri
  instance_type        = var.instance_type
  min_size             = var.min_size
  max_size             = var.max_size
  desired_capacity     = var.desired_capacity
  database_url         = module.rds.database_url
  cloudwatch_namespace = var.cloudwatch_namespace
}

module "monitoring" {
  source                  = "./modules/monitoring"
  name                    = var.name
  region                  = var.region
  alb_arn_suffix          = module.compute.alb_arn_suffix
  target_group_arn_suffix = module.compute.target_group_arn_suffix
  cloudwatch_namespace    = var.cloudwatch_namespace
  alarm_email             = var.alarm_email
}
