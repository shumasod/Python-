#!/usr/bin/env bash
# ============================================================
# データベース差分バックアップスクリプト
#
# MySQL/MariaDB: binlog ストリーミング取得またはファイルコピー
# PostgreSQL:   WAL ファイルのアーカイブ / pg_receivewal
#
# 使い方:
#   DB_TYPE=mysql      ./incremental_backup.sh [--mode stream|copy] [--dry-run]
#   DB_TYPE=mariadb    ./incremental_backup.sh [--mode stream|copy] [--dry-run]
#   DB_TYPE=postgresql ./incremental_backup.sh [--dry-run]
#
# Cron 例 (15分ごと):
#   */15 * * * * DB_TYPE=mysql /path/to/db_backup/incremental_backup.sh \
#                    >> /var/log/db_backup/incremental_cron.log 2>&1
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

# ─── 引数処理 ─────────────────────────────────────────────────
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)    BINLOG_BACKUP_MODE="$2"; shift ;;
        --dry-run) DRY_RUN=true ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) log_warn "不明なオプション: $1" ;;
    esac
    shift
done

# ─── バックエンドロード ───────────────────────────────────────
source "${SCRIPT_DIR}/backends/${DB_TYPE}.sh"

# ─── メイン処理 ──────────────────────────────────────────────
main() {
    init_dirs
    log_info "========== 差分バックアップ開始 [DB_TYPE=${DB_TYPE}] =========="

    check_db_connection || { notify_slack failure "DB 接続失敗 (差分バックアップ)"; exit 1; }

    db_incremental_backup

    log_info "========== 差分バックアップ完了 =========="
    notify_slack success "差分バックアップ完了 [${DB_TYPE}]"
}

trap 'log_error "異常終了 (line ${LINENO})"; notify_slack failure "差分バックアップ失敗 [${DB_TYPE}] (line ${LINENO})"' ERR

main "$@"
