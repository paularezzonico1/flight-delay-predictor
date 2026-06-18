# RDS module: a single-AZ Postgres db.t3.micro that logs prediction traffic.
#
# Placed in PUBLIC subnets with publicly_accessible = true to avoid the cost of
# a NAT Gateway (see the network module's tradeoff note). Access is restricted to
# the app instances by the RDS security group, which only allows :5432 from the
# instance SG. log_min_duration_statement is set so slow queries surface in logs.

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-db-subnets"
  subnet_ids = var.subnet_ids
  tags       = merge(var.tags, { Name = "${var.name}-db-subnets" })
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.name}-pg16"
  family = "postgres16"

  # Log statements slower than this (ms) to support query-time investigation.
  parameter {
    name  = "log_min_duration_statement"
    value = "200"
  }
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name}-db"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.rds_sg_id]
  publicly_accessible    = true # public subnet; locked down by SG, not network.
  multi_az               = false

  parameter_group_name    = aws_db_parameter_group.this.name
  backup_retention_period = var.backup_retention_period
  skip_final_snapshot     = true
  deletion_protection     = false

  tags = merge(var.tags, { Name = "${var.name}-db" })
}
