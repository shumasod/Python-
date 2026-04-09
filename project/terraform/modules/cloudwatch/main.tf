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
