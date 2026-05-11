#!/usr/bin/env bash
# MySQL バックアップ 共通設定ファイル
# このファイルを編集して環境に合わせてください

# ─── 接続設定 ───────────────────────────────────────────────────
MYSQL_USER="backup_user"
MYSQL_PASSWORD=""                     # 空の場合は ~/.my.cnf から読む
MYSQL_HOST="127.0.0.1"
MYSQL_PORT="3306"
MYSQL_SOCKET=""                       # 例: /var/run/mysqld/mysqld.sock

# ─── バックアップ先ディレクトリ ─────────────────────────────────
BACKUP_BASE_DIR="/var/backup/mysql"   # フルバックアップ出力先
BINLOG_BACKUP_DIR="/var/backup/mysql/binlog"  # バイナリログ出力先

# ─── 保持期間 (日数) ────────────────────────────────────────────
FULL_RETENTION_DAYS=7                 # フルバックアップの保持日数
BINLOG_RETENTION_DAYS=14             # バイナリログの保持日数

# ─── 圧縮設定 ───────────────────────────────────────────────────
COMPRESS=true                         # gzip 圧縮を有効にする
COMPRESS_LEVEL=6                      # gzip 圧縮レベル (1-9)

# ─── 通知設定 ───────────────────────────────────────────────────
SLACK_WEBHOOK_URL=""                  # Slack 通知先 Webhook URL (空で無効)
NOTIFY_ON_SUCCESS=false              # 成功時も通知するか
NOTIFY_ON_FAILURE=true               # 失敗時に通知するか

# ─── ログ設定 ───────────────────────────────────────────────────
LOG_DIR="/var/log/mysql_backup"
LOG_FILE="${LOG_DIR}/backup.log"
MAX_LOG_SIZE_MB=50                    # ログローテーションサイズ (MB)

# ─── mysqldump オプション ────────────────────────────────────────
# --single-transaction: InnoDB の一貫スナップショット
# --master-data=2    : binlog 位置をコメントとして記録 (GTID 使用時は不要)
# --flush-logs       : バックアップ前に binlog をフラッシュ・ローテーション
# --set-gtid-purged  : GTID 有効時は ON, 無効時は OFF
MYSQLDUMP_OPTS="--single-transaction --flush-logs --master-data=2 \
    --routines --triggers --events \
    --set-gtid-purged=OFF \
    --hex-blob --default-character-set=utf8mb4"

# ─── バックアップ対象データベース ───────────────────────────────
# 空の場合は --all-databases で全DB取得
# 複数指定する場合はスペース区切り: "db1 db2 db3"
TARGET_DATABASES=""

# ─── バイナリログ設定 ────────────────────────────────────────────
# MySQL サーバー上のバイナリログディレクトリ
MYSQL_BINLOG_DIR="/var/lib/mysql"     # サーバー上の binlog 配置場所
BINLOG_BASENAME="mysql-bin"          # binlog ファイルのベース名 (my.cnf の log_bin 値)
