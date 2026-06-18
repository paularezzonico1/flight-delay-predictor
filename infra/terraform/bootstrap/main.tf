# Remote-state backend bootstrap.
#
# Apply this ONCE, before the main stack, with a local backend. It provisions
# the S3 bucket (state storage, versioned + encrypted) and the DynamoDB table
# (state locking) that the root module's backend.tf then points at.
#
#   cd infra/terraform/bootstrap
#   terraform init && terraform apply
#
# Chicken-and-egg: the bucket/table that hold remote state cannot themselves be
# stored in remote state, so this small root keeps its own local state.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "state_bucket_name" {
  type        = string
  description = "Globally-unique S3 bucket name for Terraform state."
}

variable "lock_table_name" {
  type    = string
  default = "fdp-terraform-locks"
}

resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket_name

  # Refuse accidental destroys of the bucket that holds all state.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "locks" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

output "state_bucket" {
  value = aws_s3_bucket.state.id
}

output "lock_table" {
  value = aws_dynamodb_table.locks.name
}
