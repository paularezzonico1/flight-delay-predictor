variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "alb_sg_id" {
  type = string
}

variable "instance_sg_id" {
  type = string
}

variable "region" {
  type = string
}

variable "ecr_repo_name" {
  type    = string
  default = "flight-delay-predictor"
}

variable "image_uri" {
  type        = string
  description = "Full ECR image URI the launch template pulls and runs."
}

variable "database_url" {
  type      = string
  sensitive = true
  default   = ""
}

variable "cloudwatch_namespace" {
  type    = string
  default = "FlightDelayPredictor"
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

variable "cpu_target" {
  type    = number
  default = 50
}

variable "request_target" {
  type    = number
  default = 1000
}

variable "tags" {
  type    = map(string)
  default = {}
}
