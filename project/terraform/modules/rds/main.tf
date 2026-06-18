# ============================================================
# RDS モジュール（PostgreSQL）
# ============================================================

# DB サブネットグループ（プライベートサブネット配置）
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "${var.project_name}-db-subnet-group" }
}

# DB セキュリティグループ（ECS からの5432ポートのみ許可）
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "RDS セキュリティグループ: ECS からのみアクセス許可"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.ecs_sg_id]
    description     = "ECS タスクからの PostgreSQL アクセス"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-rds-sg" }
}

# RDS パラメータグループ（UTF-8設定）
resource "aws_db_parameter_group" "main" {
  name   = "${var.project_name}-pg15"
  family = "postgres15"

  parameter {
    name  = "client_encoding"
    value = "UTF8"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }
}

# RDS インスタンス本体
resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-db"

  # エンジン設定
  engine         = "postgres"
  engine_version = "15.5"
  instance_class = var.db_instance_class

  # ストレージ設定（gp3 は gp2 より最大20%コスト削減）
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_allocated_storage * 2  # オートスケーリング上限
  storage_type          = "gp3"
  storage_encrypted     = true  # 保管時暗号化（セキュリティ必須）

  # 認証情報
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  # ネットワーク設定
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false  # インターネットからのアクセスを禁止

  # バックアップ設定
  backup_retention_period = 7     # 7日間自動バックアップ
  backup_window           = "03:00-04:00"  # JST 12:00-13:00（深夜）
  maintenance_window      = "Mon:04:00-Mon:05:00"

  # 本番では削除保護を有効化
  deletion_protection = var.deletion_protection

  # マルチAZ（本番では true、コスト最適化のため開発では false）
  multi_az = var.multi_az

  # スナップショット削除時の自動取得（コスト考慮: 無効化可）
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.project_name}-db-final-snapshot"

  parameter_group_name = aws_db_parameter_group.main.name

  tags = { Name = "${var.project_name}-db" }
}
