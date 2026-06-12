# =============================================================
# マルチアカウント収集用 IAM リソース
#
# 設計意図:
# - 管理アカウントの Lambda が AssumeRole で各アカウントにアクセス
# - 被管理アカウント側に ReadOnly ロールを作成
# - Organizations の ListAccounts で自動検出もサポート
# =============================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

variable "management_account_id" {
  description = "管理アカウント（Lambda が動くアカウント）のアカウント ID"
  type        = string
}

variable "role_name" {
  description = "被管理アカウントに作成するロール名"
  type        = string
  default     = "RDSAnalyzerReadOnly"
}

variable "external_id" {
  description = "AssumeRole の ExternalId（セキュリティ強化用）"
  type        = string
  default     = ""
}

variable "tags" {
  description = "共通タグ"
  type        = map(string)
  default     = {}
}

# =============================================================
# 被管理アカウント側に作成するロール
# （各被管理アカウントの Terraform で実行する）
# =============================================================

resource "aws_iam_role" "rds_analyzer_reader" {
  name        = var.role_name
  description = "RDS Analyzer が AssumeRole して CloudWatch / RDS 情報を読み取るロール"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.management_account_id}:root"
        }
        Action = "sts:AssumeRole"
        Condition = var.external_id != "" ? {
          StringEquals = {
            "sts:ExternalId" = var.external_id
          }
        } : {}
      }
    ]
  })

  tags = merge(var.tags, {
    ManagedBy = "terraform"
    Purpose   = "rds-analyzer-cross-account"
  })
}

resource "aws_iam_role_policy" "rds_analyzer_reader" {
  name = "${var.role_name}-policy"
  role = aws_iam_role.rds_analyzer_reader.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchReadOnly"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
        ]
        Resource = "*"
      },
      {
        Sid    = "RDSDescribeOnly"
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
          "rds:DescribeDBClusters",
          "rds:DescribeDBSnapshots",
          "rds:ListTagsForResource",
        ]
        Resource = "*"
      },
      {
        Sid    = "CostExplorerReadOnly"
        Effect = "Allow"
        Action = [
          "ce:GetCostAndUsage",
          "ce:GetCostForecast",
        ]
        Resource = "*"
      },
    ]
  })
}

# =============================================================
# 管理アカウント側: Lambda に AssumeRole 権限を付与
# （管理アカウントの Terraform で実行する）
# =============================================================

variable "lambda_role_arn" {
  description = "管理アカウントの Lambda 実行ロール ARN"
  type        = string
  default     = ""
}

variable "target_account_ids" {
  description = "AssumeRole 先のアカウント ID リスト"
  type        = list(string)
  default     = []
}

resource "aws_iam_role_policy" "assume_reader_roles" {
  count = var.lambda_role_arn != "" && length(var.target_account_ids) > 0 ? 1 : 0
  name  = "AssumeRDSAnalyzerReaderRoles"
  role  = element(split("/", var.lambda_role_arn), length(split("/", var.lambda_role_arn)) - 1)

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAssumeReaderRoles"
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Resource = [
          for account_id in var.target_account_ids :
          "arn:aws:iam::${account_id}:role/${var.role_name}"
        ]
      }
    ]
  })
}

# Organizations の ListAccounts 権限（オプション）
resource "aws_iam_role_policy" "list_accounts" {
  count = var.lambda_role_arn != "" ? 1 : 0
  name  = "AllowOrganizationsListAccounts"
  role  = element(split("/", var.lambda_role_arn), length(split("/", var.lambda_role_arn)) - 1)

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "OrganizationsListAccounts"
        Effect = "Allow"
        Action = [
          "organizations:ListAccounts",
          "organizations:DescribeAccount",
        ]
        Resource = "*"
      }
    ]
  })
}

# =============================================================
# Outputs
# =============================================================

output "reader_role_arn" {
  description = "被管理アカウントの ReadOnly ロール ARN"
  value       = aws_iam_role.rds_analyzer_reader.arn
}

output "reader_role_name" {
  description = "被管理アカウントの ReadOnly ロール名"
  value       = aws_iam_role.rds_analyzer_reader.name
}
