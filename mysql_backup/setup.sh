#!/usr/bin/env bash
# ============================================================
# セットアップスクリプト
# MySQL バックアップ用ユーザー作成、ディレクトリ作成、権限設定を行う
#
# 使い方:
#   sudo ./setup.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

echo "=== MySQL バックアップセットアップ ==="

# ─── ディレクトリ作成 ─────────────────────────────────────────────
echo "[1/4] ディレクトリを作成..."
mkdir -p "${BACKUP_BASE_DIR}" "${BINLOG_BACKUP_DIR}" "${LOG_DIR}"
chmod 750 "${BACKUP_BASE_DIR}" "${BINLOG_BACKUP_DIR}" "${LOG_DIR}"
echo "  OK: ${BACKUP_BASE_DIR}"
echo "  OK: ${BINLOG_BACKUP_DIR}"
echo "  OK: ${LOG_DIR}"

# ─── スクリプトに実行権限付与 ────────────────────────────────────
echo "[2/4] スクリプトに実行権限を付与..."
chmod +x "${SCRIPT_DIR}"/*.sh
echo "  OK"

# ─── .my.cnf の作成案内 ──────────────────────────────────────────
echo "[3/4] MySQL 認証設定..."

if [[ -f "${HOME}/.my.cnf" ]]; then
    echo "  ~/.my.cnf が既に存在します"
else
    echo "  ~/.my.cnf を作成してください:"
    cat <<'EOF'

    cat > ~/.my.cnf << 'MYCNF'
[client]
user=backup_user
password=your_password_here
host=127.0.0.1
port=3306
MYCNF
    chmod 600 ~/.my.cnf

EOF
fi

# ─── MySQL バックアップユーザー作成 SQL を表示 ────────────────────
echo "[4/4] MySQL バックアップユーザー作成 SQL:"
cat <<'SQL'

  -- MySQL に root で接続して以下を実行してください:
  CREATE USER IF NOT EXISTS 'backup_user'@'localhost'
      IDENTIFIED BY 'strong_password_here';

  -- フルバックアップに必要な権限
  GRANT SELECT, SHOW VIEW, TRIGGER, LOCK TABLES,
        PROCESS, RELOAD, REPLICATION CLIENT ON *.*
        TO 'backup_user'@'localhost';

  -- binlog (REPLICATION SLAVE) のストリーミング取得に必要
  GRANT REPLICATION SLAVE ON *.* TO 'backup_user'@'localhost';

  -- Event バックアップに必要
  GRANT EVENT ON *.* TO 'backup_user'@'localhost';

  FLUSH PRIVILEGES;

SQL

# ─── my.cnf binlog 設定の確認 ────────────────────────────────────
echo "=== my.cnf の binlog 設定確認 ==="
cat <<'EOF'
  # /etc/mysql/mysql.conf.d/mysqld.cnf または /etc/my.cnf に以下が必要です:

  [mysqld]
  log_bin            = /var/lib/mysql/mysql-bin
  binlog_format      = ROW          # ROW 形式推奨 (Point-in-time recovery に必要)
  expire_logs_days   = 7            # サーバー上の binlog 保持日数
  max_binlog_size    = 100M
  server_id          = 1            # レプリケーション構成の場合はユニークな値を設定

  # GTID を使用する場合 (推奨):
  # gtid_mode          = ON
  # enforce_gtid_consistency = ON

EOF

echo "=== セットアップ完了 ==="
echo "config.sh を編集して設定を確認後、以下で動作確認してください:"
echo "  ./backup.sh --dry-run"
echo "  ./binlog_backup.sh --dry-run"
