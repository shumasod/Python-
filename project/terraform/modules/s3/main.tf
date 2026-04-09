# ============================================================
# S3 モジュール（データ保存）
# ============================================================

resource "aws_s3_bucket" "data" {
  bucket = "${var.project_name}-data-${var.environment}"
}

# パブリックアクセスを完全ブロック（セキュリティ必須設定）
resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 保管時の暗号化（AES256）
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# バージョニング（学習データの誤削除対策）
resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ライフサイクルルール（コスト最適化）
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "raw-data-transition"
    status = "Enabled"
    filter { prefix = "raw/" }

    # 30日後に S3 Standard → S3 Standard-IA に移行（コスト削減）
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    # 90日後に Glacier に移行
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    # 指定日数後に完全削除
    expiration {
      days = var.data_retention_days
    }
  }

  rule {
    id     = "model-artifacts"
    status = "Enabled"
    filter { prefix = "models/" }

    # モデルファイルは古いバージョンを90日後に削除
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# バケットポリシー（ECS タスクロールからのみアクセス可能）
resource "aws_s3_bucket_policy" "data" {
  bucket = aws_s3_bucket.data.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowECSTaskAccess"
        Effect = "Allow"
        Principal = {
          AWS = var.ecs_task_role_arn
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*",
        ]
      },
      {
        # HTTPS のみアクセスを許可（HTTP は拒否）
        Sid       = "DenyNonHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = ["${aws_s3_bucket.data.arn}/*"]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      },
    ]
  })
}
