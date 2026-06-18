output "api_url" {
  description = "Public ALB endpoint for the API."
  value       = module.compute.api_url
}

output "ecr_repository_url" {
  value = module.compute.ecr_repository_url
}

output "asg_name" {
  value = module.compute.asg_name
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "dashboard_name" {
  value = module.monitoring.dashboard_name
}

output "alarm_topic_arn" {
  value = module.monitoring.alarm_topic_arn
}
