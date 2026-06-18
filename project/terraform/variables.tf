# ============================================================
# 共通変数定義
# ============================================================

variable "project_name" {
  description = "プロジェクト名（リソース名のプレフィックスに使用）"
  type        = string
  default     = "boat-race-ai"
}

variable "environment" {
  description = "環境名（prod / staging / dev）"
  type        = string
  default     = "prod"
  validation {
    condition     = contains(["prod", "staging", "dev"], var.environment)
    error_message = "environment は prod / staging / dev のいずれかを指定してください。"
  }
}

variable "aws_region" {
  description = "デプロイするAWSリージョン"
  type        = string
  default     = "ap-northeast-1"  # 東京リージョン
}

# ---- ネットワーク ----

variable "vpc_cidr" {
  description = "VPC の CIDRブロック"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "使用するアベイラビリティーゾーン"
  type        = list(string)
  default     = ["ap-northeast-1a", "ap-northeast-1c"]
}

variable "public_subnet_cidrs" {
  description = "パブリックサブネットの CIDRブロックリスト"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "プライベートサブネットの CIDRブロックリスト"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

# ---- ECS ----

variable "ecs_cpu" {
  description = "ECS タスクの CPU ユニット (256=0.25vCPU 〜 4096=4vCPU)"
  type        = number
  default     = 512
}

variable "ecs_memory" {
  description = "ECS タスクのメモリ (MiB)"
  type        = number
  default     = 1024
}

variable "ecs_desired_count" {
  description = "ECS サービスの希望タスク数"
  type        = number
  default     = 2
}

variable "ecr_image_tag" {
  description = "デプロイする ECR イメージタグ"
  type        = string
  default     = "latest"
}

# ---- RDS ----

variable "db_instance_class" {
  description = "RDS インスタンスクラス（コスト最適化: t3.micro は無料枠対象）"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "データベース名"
  type        = string
  default     = "boatracedb"
}

variable "db_username" {
  description = "DBマスターユーザー名"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "db_password" {
  description = "DBマスターパスワード（Secrets Manager 推奨）"
  type        = string
  sensitive   = true
}

variable "db_allocated_storage" {
  description = "RDS ストレージ容量 (GiB)"
  type        = number
  default     = 20
}

# ---- S3 ----

variable "s3_data_retention_days" {
  description = "生データの S3 ライフサイクル保持日数（コスト最適化）"
  type        = number
  default     = 365
}

# ---- CloudWatch ----

variable "log_retention_days" {
  description = "CloudWatch Logs の保持日数"
  type        = number
  default     = 30
}

variable "alert_email" {
  description = "CloudWatch アラーム通知先メールアドレス（空文字で無効化）"
  type        = string
  default     = ""
}

# ---- タグ ----

variable "tags" {
  description = "全リソースに付与する共通タグ"
  type        = map(string)
  default = {
    Project   = "boat-race-ai"
    ManagedBy = "terraform"
  }
}
