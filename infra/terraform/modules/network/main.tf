# Network module: VPC, public subnets, internet gateway, and security groups.
#
# COST-VS-BEST-PRACTICE TRADEOFF (deliberate, demo only):
# RDS is placed in PUBLIC subnets rather than private subnets behind a NAT
# Gateway. A NAT Gateway costs ~$32/mo + data processing; for a portfolio demo
# that is disproportionate. Instead the database is locked down at the security
# group layer: the RDS SG accepts :5432 ONLY from the instance SG, so the
# database is not reachable from the internet despite living in a public subnet.
# In production you would use private subnets + NAT (or VPC endpoints). This is
# documented in the README's architecture section.

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = "${var.name}-vpc" })
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = merge(var.tags, { Name = "${var.name}-igw" })
}

resource "aws_subnet" "public" {
  count                   = var.public_subnet_count
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags                    = merge(var.tags, { Name = "${var.name}-public-${count.index}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = merge(var.tags, { Name = "${var.name}-public-rt" })
}

resource "aws_route_table_association" "public" {
  count          = var.public_subnet_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# --- Security groups ---------------------------------------------------------

# Public ingress to the ALB on port 80.
resource "aws_security_group" "alb" {
  name        = "${var.name}-alb-sg"
  description = "Public HTTP ingress to the ALB."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.tags, { Name = "${var.name}-alb-sg" })
}

# App instances: accept :8000 only from the ALB. Redis (:6379) runs as a
# container bound to the instance itself, so no ingress rule is needed for it.
resource "aws_security_group" "instance" {
  name        = "${var.name}-instance-sg"
  description = "App traffic from the ALB only."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "App port from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.tags, { Name = "${var.name}-instance-sg" })
}

# RDS: accept :5432 ONLY from the instance SG. This is what makes a public-subnet
# database safe — there is no path from the internet to the DB port.
resource "aws_security_group" "rds" {
  name        = "${var.name}-rds-sg"
  description = "Postgres from app instances only."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Postgres from app instances"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.instance.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.tags, { Name = "${var.name}-rds-sg" })
}
