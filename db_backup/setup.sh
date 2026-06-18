#!/usr/bin/env bash
# ============================================================
# データベースバックアップ セットアップスクリプト
#
# 使い方:
#   sudo DB_TYPE=mysql      ./setup.sh
#   sudo DB_TYPE=mariadb    ./setup.sh
#   sudo DB_TYPE=postgresql ./setup.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

echo "=== DB バックアップ セットアップ [DB_TYPE=${DB_TYPE}] ==="

# ─── ディレクトリ作成 ─────────────────────────────────────────
echo "[1/3] ディレクトリを作成..."
mkdir -p "${BACKUP_BASE_DIR}" "${INCREMENTAL_BACKUP_DIR}" "${LOG_DIR}"
[[ -n "${PG_WAL_DIR}" ]] && mkdir -p "${PG_WAL_DIR}"
chmod 750 "${BACKUP_BASE_DIR}" "${INCREMENTAL_BACKUP_DIR}" "${LOG_DIR}"
echo "  OK: ${BACKUP_BASE_DIR}"
echo "  OK: ${INCREMENTAL_BACKUP_DIR}"
echo "  OK: ${LOG_DIR}"
[[ -n "${PG_WAL_DIR}" ]] && echo "  OK: ${PG_WAL_DIR}"

# ─── 実行権限付与 ─────────────────────────────────────────────
echo "[2/3] スクリプトに実行権限を付与..."
chmod +x "${SCRIPT_DIR}"/*.sh "${SCRIPT_DIR}"/backends/*.sh
echo "  OK"

# ─── DB 種別ごとのセットアップ案内 ───────────────────────────
echo "[3/3] ${DB_TYPE} セットアップ情報:"
source "${SCRIPT_DIR}/backends/${DB_TYPE}.sh"
db_setup_instructions

# ─── 認証設定の案内 ───────────────────────────────────────────
case "${DB_TYPE}" in
    mysql|mariadb)
        echo "=== MySQL/MariaDB 認証設定 ==="
        if [[ -f "${HOME}/.my.cnf" ]]; then
            echo "  ~/.my.cnf が既に存在します"
        else
            cat <<'EOF'
  ~/.my.cnf を作成してください (chmod 600):

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
        ;;
    postgresql)
        echo "=== PostgreSQL 認証設定 ==="
        if [[ -f "${HOME}/.pgpass" ]]; then
            echo "  ~/.pgpass が既に存在します"
        else
            cat <<'EOF'
  ~/.pgpass を作成してください (chmod 600):

    echo "127.0.0.1:5432:*:backup_user:your_password_here" > ~/.pgpass
    chmod 600 ~/.pgpass

EOF
        fi
        ;;
esac

echo "=== セットアップ完了 ==="
echo "config.sh を編集して設定を確認後、以下で動作確認:"
echo "  DB_TYPE=${DB_TYPE} ./backup.sh --dry-run"
echo "  DB_TYPE=${DB_TYPE} ./incremental_backup.sh --dry-run"
