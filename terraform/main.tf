# =============================================================
# RDS Cost & Performance Analyzer - Terraform 構成
#
# 設計意図:
# - API Gateway + Lambda で FastAPI をサーバーレス実行
# - EventBridge で 5 分間隔のメトリクス収集を自動化
# - DynamoDB でメトリクス・設定データを永続化
# - IAM ロールは最小権限原則に基づいて設定
# - CloudWatch Logs でログを集約管理
# =============================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # 本番運用では S3 バックエンドを使用すること
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "rds-analyzer/terraform.tfstate"
  #   region = "ap-northeast-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(var.tags, {
      Environment = var.environment
    })
  }
}

# =============================================================
# ローカル変数
# =============================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# =============================================================
# DynamoDB テーブル
# =============================================================

# RDS インスタンス設定テーブル
resource "aws_dynamodb_table" "rds_instances" {
  name         = "${local.name_prefix}-instances"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "instance_id"

  attribute {
    name = "instance_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${local.name_prefix}-instances"
  }
}

# メトリクステーブル（TTL 付き）
resource "aws_dynamodb_table" "metrics" {
  name         = "${local.name_prefix}-metrics"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "instance_id"
  range_key    = "timestamp"

  attribute {
    name = "instance_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  # 90 日後に自動削除（コスト削減）
  ttl {
    attribute_name = "ttl_epoch"
    enabled        = true
  }

  # インスタンスIDでのクエリ最適化
  global_secondary_index {
    name            = "instance_id-index"
    hash_key        = "instance_id"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${local.name_prefix}-metrics"
  }
}

# コストテーブル
resource "aws_dynamodb_table" "costs" {
  name         = "${local.name_prefix}-costs"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "instance_id"
  range_key    = "month"

  attribute {
    name = "instance_id"
    type = "S"
  }

  attribute {
    name = "month"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${local.name_prefix}-costs"
  }
}

# =============================================================
# IAM ロール: Lambda 実行ロール（API サーバー用）
# =============================================================

resource "aws_iam_role" "api_lambda_role" {
  name = "${local.name_prefix}-api-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "api_lambda_policy" {
  name = "${local.name_prefix}-api-lambda-policy"
  role = aws_iam_role.api_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # CloudWatch Logs 書き込み
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        # DynamoDB アクセス（最小権限: 必要なテーブルのみ）
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = [
          aws_dynamodb_table.rds_instances.arn,
          aws_dynamodb_table.metrics.arn,
          aws_dynamodb_table.costs.arn,
          "${aws_dynamodb_table.metrics.arn}/index/*",
        ]
      },
    ]
  })
}

# VPC 内での実行が必要な場合
resource "aws_iam_role_policy_attachment" "api_lambda_vpc" {
  count      = length(var.lambda_subnet_ids) > 0 ? 1 : 0
  role       = aws_iam_role.api_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# =============================================================
# IAM ロール: Lambda 実行ロール（メトリクス収集用）
# =============================================================

resource "aws_iam_role" "collector_lambda_role" {
  name = "${local.name_prefix}-collector-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "collector_lambda_policy" {
  name = "${local.name_prefix}-collector-lambda-policy"
  role = aws_iam_role.collector_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        # CloudWatch メトリクス取得（読み取りのみ）
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
        ]
        Resource = "*"
      },
      {
        # RDS インスタンス情報取得（読み取りのみ）
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
          "rds:DescribeDBClusters",
          "rds:ListTagsForResource",
        ]
        Resource = "*"
      },
    ]
  })
}

# =============================================================
# Lambda 関数: API サーバー
# =============================================================

# Lambda デプロイパッケージ（実際の実装では CI/CD でビルド）
data "archive_file" "api_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../rds_analyzer"
  output_path = "${path.module}/.build/api_lambda.zip"
  excludes    = ["__pycache__", "*.pyc", "sample_data"]
}

resource "aws_lambda_function" "api" {
  filename         = data.archive_file.api_lambda_zip.output_path
  function_name    = "${local.name_prefix}-api"
  role             = aws_iam_role.api_lambda_role.arn
  handler          = "main.handler"  # Mangum アダプター使用
  runtime          = "python3.12"
  memory_size      = var.api_lambda_memory_mb
  timeout          = var.api_lambda_timeout_sec
  source_code_hash = data.archive_file.api_lambda_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_INSTANCES_TABLE = aws_dynamodb_table.rds_instances.name
      DYNAMODB_METRICS_TABLE   = aws_dynamodb_table.metrics.name
      DYNAMODB_COSTS_TABLE     = aws_dynamodb_table.costs.name
      AWS_REGION_NAME          = var.aws_region
      LOG_LEVEL                = var.environment == "prod" ? "WARNING" : "INFO"
    }
  }

  # VPC 設定（オプション）
  dynamic "vpc_config" {
    for_each = length(var.lambda_subnet_ids) > 0 ? [1] : []
    content {
      subnet_ids         = var.lambda_subnet_ids
      security_group_ids = [aws_security_group.lambda[0].id]
    }
  }

  tags = {
    Name = "${local.name_prefix}-api"
  }
}

resource "aws_cloudwatch_log_group" "api_lambda" {
  name              = "/aws/lambda/${aws_lambda_function.api.function_name}"
  retention_in_days = var.log_retention_days
}

# =============================================================
# Lambda 関数: メトリクス収集
# =============================================================

data "archive_file" "collector_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../rds_analyzer/collectors"
  output_path = "${path.module}/.build/collector_lambda.zip"
  excludes    = ["__pycache__", "*.pyc"]
}

resource "aws_lambda_function" "collector" {
  filename         = data.archive_file.collector_lambda_zip.output_path
  function_name    = "${local.name_prefix}-collector"
  role             = aws_iam_role.collector_lambda_role.arn
  handler          = "lambda_handler.lambda_handler"
  runtime          = "python3.12"
  memory_size      = var.collector_lambda_memory_mb
  timeout          = 120  # 収集に時間がかかる場合があるため長めに設定
  source_code_hash = data.archive_file.collector_lambda_zip.output_base64sha256

  environment {
    variables = {
      API_ENDPOINT             = "https://${aws_api_gateway_rest_api.main.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
      REGION                   = var.aws_region
      COLLECTION_PERIOD_HOURS  = "1"
      LOG_LEVEL                = "INFO"
    }
  }

  tags = {
    Name = "${local.name_prefix}-collector"
  }
}

resource "aws_cloudwatch_log_group" "collector_lambda" {
  name              = "/aws/lambda/${aws_lambda_function.collector.function_name}"
  retention_in_days = var.log_retention_days
}

# =============================================================
# EventBridge: 5 分間隔でコレクターを起動
# =============================================================

resource "aws_cloudwatch_event_rule" "collector_schedule" {
  name                = "${local.name_prefix}-collector-schedule"
  description         = "RDS メトリクス収集を ${var.collector_schedule_expression} で実行"
  schedule_expression = var.collector_schedule_expression
}

resource "aws_cloudwatch_event_target" "collector_target" {
  rule      = aws_cloudwatch_event_rule.collector_schedule.name
  target_id = "CollectorLambda"
  arn       = aws_lambda_function.collector.arn
}

resource "aws_lambda_permission" "eventbridge_collector" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.collector_schedule.arn
}

# =============================================================
# API Gateway: REST API
# =============================================================

resource "aws_api_gateway_rest_api" "main" {
  name        = "${local.name_prefix}-api"
  description = "RDS Cost & Performance Analyzer API"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name = "${local.name_prefix}-api"
  }
}

# プロキシリソース（FastAPI に全リクエストを転送）
resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy_any" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "proxy_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy_any.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api.invoke_arn
}

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  depends_on = [
    aws_api_gateway_integration.proxy_lambda,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.environment

  # アクセスログを有効化
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      responseLength = "$context.responseLength"
    })
  }

  tags = {
    Name = "${local.name_prefix}-stage"
  }
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${local.name_prefix}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# =============================================================
# セキュリティグループ（VPC 使用時のみ）
# =============================================================

resource "aws_security_group" "lambda" {
  count       = length(var.lambda_subnet_ids) > 0 ? 1 : 0
  name        = "${local.name_prefix}-lambda-sg"
  description = "Lambda 関数用セキュリティグループ"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "全アウトバウンドトラフィックを許可（AWS API 通信用）"
  }

  tags = {
    Name = "${local.name_prefix}-lambda-sg"
  }
}
