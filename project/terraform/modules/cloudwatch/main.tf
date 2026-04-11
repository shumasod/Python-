# ============================================================
# CloudWatch モジュール（ログ・アラーム）
# ============================================================

# ECS アプリログ用ロググループ
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}/api"
  retention_in_days = var.log_retention_days  # 保持期間（コスト最適化: 30日）
  tags              = { Name = "${var.project_name}-api-logs" }
}

# ECS スクレイパー用ロググループ
resource "aws_cloudwatch_log_group" "scraper" {
  name              = "/ecs/${var.project_name}/scraper"
  retention_in_days = var.log_retention_days
}

# ---- SNS トピック（アラーム通知先）----

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
  tags = { Name = "${var.project_name}-alerts" }
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ---- アラーム定義 ----

# ECS タスク数が 0 になったらアラート（サービス停止検知）
resource "aws_cloudwatch_metric_alarm" "ecs_running_tasks" {
  alarm_name          = "${var.project_name}-ecs-no-running-tasks"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  alarm_description   = "ECS タスクが起動していません"
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    ClusterName = "${var.project_name}-cluster"
    ServiceName = "${var.project_name}-api-service"
  }
}

# API の 5xx エラーレートが 5% を超えたらアラート
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.project_name}-api-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "API サーバーで 5xx エラーが多発しています"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
}

# ALB P95 レイテンシが 2秒を超えたらアラート
resource "aws_cloudwatch_metric_alarm" "api_latency_p95" {
  alarm_name          = "${var.project_name}-api-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  extended_statistic  = "p95"
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  threshold           = 2.0
  alarm_description   = "API P95 レイテンシが 2秒を超えています"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
}

# RDS CPU 使用率が 80% を超えたらアラート
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.project_name}-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU 使用率が高くなっています"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = var.rds_identifier
  }
}

# RDS 空きストレージが 5GB 未満になったらアラート
resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  alarm_name          = "${var.project_name}-rds-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Minimum"
  threshold           = 5368709120  # 5 GB in bytes
  alarm_description   = "RDS 空きストレージが 5GB 未満です"
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = var.rds_identifier
  }
}

# ECS CPU 使用率が 85% を超えたらアラート（スケールアウト前の警告）
resource "aws_cloudwatch_metric_alarm" "ecs_cpu" {
  alarm_name          = "${var.project_name}-ecs-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "ECS CPU 使用率が高くなっています"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ClusterName = "${var.project_name}-cluster"
    ServiceName = "${var.project_name}-api-service"
  }
}

# ---- CloudWatch Log Metric Filters ----

# エラーログのメトリクスフィルター
resource "aws_cloudwatch_log_metric_filter" "error_count" {
  name           = "${var.project_name}-error-count"
  log_group_name = aws_cloudwatch_log_group.api.name
  pattern        = "[timestamp, level=\"ERROR\", ...]"

  metric_transformation {
    name          = "ErrorCount"
    namespace     = "${var.project_name}/Application"
    value         = "1"
    default_value = "0"
  }
}

# ドリフトアラートのメトリクスフィルター
resource "aws_cloudwatch_log_metric_filter" "drift_alert" {
  name           = "${var.project_name}-drift-alert"
  log_group_name = aws_cloudwatch_log_group.api.name
  pattern        = "ドリフトアラート"

  metric_transformation {
    name          = "DriftAlertCount"
    namespace     = "${var.project_name}/Application"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "drift_detected" {
  alarm_name          = "${var.project_name}-model-drift-detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DriftAlertCount"
  namespace           = "${var.project_name}/Application"
  period              = 3600
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "モデルドリフトが検知されました。再学習を検討してください。"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# ---- CloudWatch Dashboard ----

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x = 0; y = 0; width = 12; height = 6
        properties = {
          title  = "ECS 実行タスク数"
          period = 60
          metrics = [[
            "ECS/ContainerInsights", "RunningTaskCount",
            "ClusterName", "${var.project_name}-cluster",
            "ServiceName", "${var.project_name}-api-service",
          ]]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x = 12; y = 0; width = 12; height = 6
        properties = {
          title  = "API レイテンシ P95 (秒)"
          period = 60
          metrics = [[
            "AWS/ApplicationELB", "TargetResponseTime",
            "LoadBalancer", var.alb_arn_suffix,
            { stat = "p95" }
          ]]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x = 0; y = 6; width = 12; height = 6
        properties = {
          title  = "API 5xx エラー数"
          period = 60
          metrics = [[
            "AWS/ApplicationELB", "HTTPCode_Target_5XX_Count",
            "LoadBalancer", var.alb_arn_suffix,
            { stat = "Sum" }
          ]]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x = 12; y = 6; width = 12; height = 6
        properties = {
          title  = "アプリエラー数"
          period = 300
          metrics = [[
            "${var.project_name}/Application", "ErrorCount",
            { stat = "Sum" }
          ]]
          view = "timeSeries"
        }
      },
      {
        type   = "log"
        x = 0; y = 12; width = 24; height = 8
        properties = {
          title   = "API エラーログ（直近）"
          query   = "fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 50"
          logGroupNames = ["/ecs/${var.project_name}/api"]
          view    = "table"
        }
      },
    ]
  })
}


# ECS アプリログ用ロググループ
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}/api"
  retention_in_days = var.log_retention_days  # 保持期間（コスト最適化: 30日）
  tags              = { Name = "${var.project_name}-api-logs" }
}

# ECS スクレイパー用ロググループ
resource "aws_cloudwatch_log_group" "scraper" {
  name              = "/ecs/${var.project_name}/scraper"
  retention_in_days = var.log_retention_days
}

# ---- アラーム定義 ----

# ECS タスク数が 0 になったらアラート（サービス停止検知）
resource "aws_cloudwatch_metric_alarm" "ecs_running_tasks" {
  alarm_name          = "${var.project_name}-ecs-no-running-tasks"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  alarm_description   = "ECS タスクが起動していません"
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = "${var.project_name}-cluster"
    ServiceName = "${var.project_name}-api-service"
  }

  # SNS トピック ARN を設定すればメール通知可能
  # alarm_actions = [aws_sns_topic.alerts.arn]
}

# API の 5xx エラーレートが 5% を超えたらアラート
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.project_name}-api-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "API サーバーで 5xx エラーが多発しています"
  treat_missing_data  = "notBreaching"
}

# ---- CloudWatch Dashboard ----

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title  = "ECS 実行タスク数"
          period = 300
          metrics = [[
            "ECS/ContainerInsights", "RunningTaskCount",
            "ClusterName", "${var.project_name}-cluster",
          ]]
        }
      },
      {
        type = "log"
        properties = {
          title   = "API エラーログ"
          query   = "fields @timestamp, @message | filter @message like /ERROR/"
          logGroupNames = ["/ecs/${var.project_name}/api"]
        }
      },
    ]
  })
}
