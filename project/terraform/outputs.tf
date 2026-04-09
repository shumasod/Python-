# ============================================================
# 出力値定義
# ============================================================

output "api_endpoint" {
  description = "ECS ALB エンドポイント URL"
  value       = "http://${module.ecs.alb_dns_name}/api/v1"
}

output "ecr_repository_url" {
  description = "ECR リポジトリ URL（docker push に使用）"
  value       = module.ecr.repository_url
}

output "s3_data_bucket" {
  description = "学習データ保存用 S3 バケット名"
  value       = module.s3.data_bucket_name
}

output "rds_endpoint" {
  description = "RDS エンドポイント（アプリから接続）"
  value       = module.rds.db_endpoint
  sensitive   = true  # エンドポイントは機密扱い
}

output "cloudwatch_log_group" {
  description = "ECS アプリログの CloudWatch ロググループ名"
  value       = module.cloudwatch.api_log_group_name
}

output "vpc_id" {
  description = "作成した VPC の ID"
  value       = aws_vpc.main.id
}
