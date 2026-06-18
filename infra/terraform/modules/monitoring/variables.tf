variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "alb_arn_suffix" {
  type        = string
  description = "ALB ARN suffix (app/<name>/<id>) for ALB metric dimensions."
}

variable "target_group_arn_suffix" {
  type = string
}

variable "cloudwatch_namespace" {
  type    = string
  default = "FlightDelayPredictor"
}

variable "alarm_email" {
  type        = string
  default     = ""
  description = "Optional email subscribed to alarm notifications."
}

variable "tags" {
  type    = map(string)
  default = {}
}
