output "endpoint" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "db_name" {
  value = aws_db_instance.this.db_name
}

# SQLAlchemy URL the app consumes as FDP_DATABASE_URL.
output "database_url" {
  value     = "postgresql+psycopg://${var.db_username}:${var.db_password}@${aws_db_instance.this.address}:${aws_db_instance.this.port}/${var.db_name}"
  sensitive = true
}
