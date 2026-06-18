variable "name" {
  type    = string
  default = "fdp"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "public_subnet_count" {
  type    = number
  default = 2
}

# --- RDS ---
variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
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
  type        = string
  sensitive   = true
  description = "RDS master password. Supply via TF_VAR_db_password or a secrets manager — do not commit."
}

# --- Compute ---
variable "ecr_repo_name" {
  type    = string
  default = "flight-delay-predictor"
}

variable "image_uri" {
  type        = string
  description = "ECR image URI the ASG runs. Pushed by CI before apply."
}

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "min_size" {
  type    = number
  default = 2
}

variable "max_size" {
  type    = number
  default = 6
}

variable "desired_capacity" {
  type    = number
  default = 2
}

# --- Observability ---
variable "cloudwatch_namespace" {
  type    = string
  default = "FlightDelayPredictor"
}

variable "alarm_email" {
  type    = string
  default = ""
}
