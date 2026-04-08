# =============================================================
# Terraform 出力値
# =============================================================

output "api_endpoint" {
  description = "API Gateway エンドポイント URL"
  value       = "https://${aws_api_gateway_rest_api.main.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
}

output "api_lambda_function_name" {
  description = "API Lambda 関数名"
  value       = aws_lambda_function.api.function_name
}

output "collector_lambda_function_name" {
  description = "コレクター Lambda 関数名"
  value       = aws_lambda_function.collector.function_name
}

output "dynamodb_instances_table" {
  description = "RDS インスタンス設定テーブル名"
  value       = aws_dynamodb_table.rds_instances.name
}

output "dynamodb_metrics_table" {
  description = "メトリクステーブル名"
  value       = aws_dynamodb_table.metrics.name
}

output "dynamodb_costs_table" {
  description = "コストテーブル名"
  value       = aws_dynamodb_table.costs.name
}

output "swagger_ui_url" {
  description = "Swagger UI URL（API ドキュメント）"
  value       = "https://${aws_api_gateway_rest_api.main.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/docs"
}
