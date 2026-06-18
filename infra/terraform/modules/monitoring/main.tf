# Monitoring module: SNS alarm topic, CloudWatch alarms, and a dashboard.
#
# Covers both ALB-level metrics (5xx, p95 latency, unhealthy hosts) and the
# application's custom metrics (prediction latency, cache hit/miss) published to
# var.cloudwatch_namespace by app/metrics.py.

resource "aws_sns_topic" "alarms" {
  name = "${var.name}-alarms"
  tags = var.tags
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "high_5xx" {
  alarm_name          = "${var.name}-alb-5xx"
  alarm_description   = "Elevated 5xx responses from the API targets."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  dimensions          = { LoadBalancer = var.alb_arn_suffix }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "high_latency" {
  alarm_name          = "${var.name}-alb-p95-latency"
  alarm_description   = "p95 target response time above 100 ms SLO."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  dimensions          = { LoadBalancer = var.alb_arn_suffix }
  extended_statistic  = "p95"
  period              = 60
  evaluation_periods  = 5
  threshold           = 0.1
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "unhealthy_hosts" {
  alarm_name        = "${var.name}-unhealthy-hosts"
  alarm_description = "One or more targets failing health checks."
  namespace         = "AWS/ApplicationELB"
  metric_name       = "UnHealthyHostCount"
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

# Custom-metric alarm: app-reported prediction latency p99 above target.
resource "aws_cloudwatch_metric_alarm" "prediction_latency" {
  alarm_name          = "${var.name}-prediction-latency-p99"
  alarm_description   = "Application p99 prediction latency above 50 ms."
  namespace           = var.cloudwatch_namespace
  metric_name         = "PredictionLatency"
  extended_statistic  = "p99"
  period              = 60
  evaluation_periods  = 5
  threshold           = 50
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = var.name

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6,
        properties = {
          title   = "Request count",
          region  = var.region,
          stat    = "Sum",
          metrics = [["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix]]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6,
        properties = {
          title   = "ALB p95 latency (s)",
          region  = var.region,
          metrics = [["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { stat = "p95" }]]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6,
        properties = {
          title  = "Prediction latency (app, ms)",
          region = var.region,
          metrics = [
            [var.cloudwatch_namespace, "PredictionLatency", { stat = "p50" }],
            ["...", { stat = "p99" }]
          ]
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6,
        properties = {
          title  = "Cache hits vs misses",
          region = var.region,
          stat   = "Sum",
          metrics = [
            [var.cloudwatch_namespace, "CacheHit"],
            [var.cloudwatch_namespace, "CacheMiss"]
          ]
        }
      }
    ]
  })
}
