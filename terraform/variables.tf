# =============================================================
# 変数定義
# =============================================================

variable "project_name" {
  description = "プロジェクト名（リソース名のプレフィックスに使用）"
  type        = string
  default     = "rds-analyzer"
}

variable "environment" {
  description = "環境名（dev/staging/prod）"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment は dev/staging/prod のいずれかを指定してください"
  }
}

variable "aws_region" {
  description = "AWS リージョン"
  type        = string
  default     = "ap-northeast-1"
}

variable "api_lambda_memory_mb" {
  description = "Lambda 関数のメモリサイズ（MB）"
  type        = number
  default     = 512
}

variable "api_lambda_timeout_sec" {
  description = "Lambda 関数のタイムアウト（秒）"
  type        = number
  default     = 30
}

variable "collector_lambda_memory_mb" {
  description = "メトリクス収集 Lambda のメモリ（MB）"
  type        = number
  default     = 256
}

variable "collector_schedule_expression" {
  description = "メトリクス収集 Lambda の実行スケジュール（EventBridge）"
  type        = string
  default     = "rate(5 minutes)"
}

variable "dynamodb_billing_mode" {
  description = "DynamoDB 課金モード（PAY_PER_REQUEST / PROVISIONED）"
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "log_retention_days" {
  description = "CloudWatch Logs の保持期間（日数）"
  type        = number
  default     = 30
}

variable "vpc_id" {
  description = "VPC ID（Lambda を VPC 内に配置する場合）"
  type        = string
  default     = ""
}

variable "lambda_subnet_ids" {
  description = "Lambda 配置先サブネット ID リスト"
  type        = list(string)
  default     = []
}

variable "allowed_cidr_blocks" {
  description = "API Gateway へのアクセスを許可する CIDR ブロック"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "全リソースに付与する共通タグ"
  type        = map(string)
  default = {
    Project   = "rds-analyzer"
    ManagedBy = "terraform"
  }
}
