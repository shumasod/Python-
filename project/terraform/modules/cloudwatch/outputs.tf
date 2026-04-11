output "api_log_group_name"     { value = aws_cloudwatch_log_group.api.name }
output "scraper_log_group_name" { value = aws_cloudwatch_log_group.scraper.name }
output "sns_topic_arn"          { value = aws_sns_topic.alerts.arn }
output "dashboard_name"         { value = aws_cloudwatch_dashboard.main.dashboard_name }
