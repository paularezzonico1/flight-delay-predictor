output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "alb_sg_id" {
  value = aws_security_group.alb.id
}

output "instance_sg_id" {
  value = aws_security_group.instance.id
}

output "rds_sg_id" {
  value = aws_security_group.rds.id
}
