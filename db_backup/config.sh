#!/usr/bin/env bash
# ============================================================
# データベースバックアップ共通設定
# 対応DB: mysql | mariadb | postgresql
#
# 環境変数で上書き可能:
#   DB_TYPE=postgresql ./backup.sh
#   DB_TYPE=mariadb    ./backup.sh --dry-run
# ============================================================

# ─── データベース種別 ─────────────────────────────────────────
DB_TYPE="${DB_TYPE:-mysql}"          # mysql | mariadb | postgresql

# ─── MySQL / MariaDB 接続設定 ─────────────────────────────────
MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-backup_user}"
MYSQL_SOCKET=""                      # 例: /var/run/mysqld/mysqld.sock

# バックアップ対象DB (空 = 全DB、スペース区切りで複数指定可)
MYSQL_TARGET_DBS=""

MYSQLDUMP_OPTS="--single-transaction --flush-logs --master-data=2 \
--routines --triggers --events --set-gtid-purged=OFF \
--hex-blob --default-character-set=utf8mb4"

# binlog 設定 (MySQL/MariaDB のみ)
MYSQL_BINLOG_DIR="/var/lib/mysql"
BINLOG_BASENAME="mysql-bin"
BINLOG_BACKUP_MODE="stream"          # stream | copy

# ─── PostgreSQL 接続設定 ──────────────────────────────────────
PG_HOST="${PG_HOST:-127.0.0.1}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-backup_user}"
PG_DATABASE=""                       # 空 = pg_dumpall で全DB
PG_DUMP_FORMAT="custom"              # custom | plain | directory | tar
PG_DUMP_OPTS="--no-password --lock-wait-timeout=60s"

# WAL アーカイブ設定 (空 = WAL バックアップ無効)
PG_WAL_DIR="/var/backup/db/wal"
PG_DATA_DIR="/var/lib/postgresql/data"
PG_BASEBACKUP_OPTS="--checkpoint=fast --wal-method=stream"

# ─── バックアップ先ディレクトリ ───────────────────────────────
BACKUP_BASE_DIR="/var/backup/db/full"
INCREMENTAL_BACKUP_DIR="/var/backup/db/incremental"
LOG_DIR="/var/log/db_backup"

# ─── 保持日数 ─────────────────────────────────────────────────
FULL_RETENTION_DAYS=7
INCREMENTAL_RETENTION_DAYS=3

# 件数ベースの保持（設定時は日数ベースより優先）
# RETENTION_COUNT=10  # デフォルト未設定（空=無効）
RETENTION_COUNT="${RETENTION_COUNT:-}"

# ─── 圧縮設定 ─────────────────────────────────────────────────
COMPRESS=true
COMPRESS_LEVEL=6

# ─── Slack 通知 ───────────────────────────────────────────────
SLACK_WEBHOOK_URL=""
SLACK_CHANNEL="#db-backup"
SLACK_USERNAME="DB Backup Bot"
