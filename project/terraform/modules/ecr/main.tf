# ============================================================
# ECR モジュール（Docker イメージ管理）
# ============================================================

resource "aws_ecr_repository" "app" {
  name                 = "${var.project_name}-api"
  image_tag_mutability = "MUTABLE"  # latest タグの上書きを許可

  # イメージスキャン（脆弱性検知）を push 時に自動実行
  image_scanning_configuration {
    scan_on_push = true
  }

  # 保管時の暗号化（KMS or AES256）
  encryption_configuration {
    encryption_type = "AES256"
  }
}

# ライフサイクルポリシー（古いイメージを自動削除してコスト最適化）
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        # latest 以外の untagged イメージを7日後に削除
        rulePriority = 1
        description  = "untaggedイメージを7日後に削除"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = { type = "expire" }
      },
      {
        # latest 以外のタグ付きイメージを最新10件のみ保持
        rulePriority = 2
        description  = "最新10件以外のイメージを削除"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = { type = "expire" }
      },
    ]
  })
}
