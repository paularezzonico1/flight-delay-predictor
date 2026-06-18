variable "name" {
  type        = string
  description = "Name prefix for tagged resources."
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "public_subnet_count" {
  type    = number
  default = 2
}

variable "tags" {
  type    = map(string)
  default = {}
}
