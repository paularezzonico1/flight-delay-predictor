variable "name" {
  type = string
}

variable "subnet_ids" {
  type        = list(string)
  description = "Public subnets for the DB subnet group (see tradeoff note)."
}

variable "rds_sg_id" {
  type = string
}

variable "instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "engine_version" {
  type    = string
  default = "16.3"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "max_allocated_storage" {
  type    = number
  default = 50
}

variable "db_name" {
  type    = string
  default = "fdp"
}

variable "db_username" {
  type    = string
  default = "fdp"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "backup_retention_period" {
  type    = number
  default = 1
}

variable "tags" {
  type    = map(string)
  default = {}
}
