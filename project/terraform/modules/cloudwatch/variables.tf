variable "project_name"       { type = string }
variable "log_retention_days" { type = number; default = 30 }

variable "alert_email" {
  type        = string
  description = "アラート通知先メールアドレス（空文字で無効化）"
  default     = ""
}

variable "alb_arn_suffix" {
  type        = string
  description = "ALB の ARN サフィックス（CloudWatch メトリクスの dimensions に使用）"
  default     = ""
}

variable "rds_identifier" {
  type        = string
  description = "RDS インスタンス識別子"
  default     = ""
}
