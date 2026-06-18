#!/usr/bin/env bash
# ============================================================
# データベースフルバックアップスクリプト
# 対応DB: MySQL / MariaDB / PostgreSQL
#
# 使い方:
#   DB_TYPE=mysql      ./backup.sh [--dry-run]
#   DB_TYPE=mariadb    ./backup.sh [--dry-run]
#   DB_TYPE=postgresql ./backup.sh [--dry-run]
#
#   ./backup.sh --db myapp                # 単一DB
#   ./backup.sh --no-incremental          # フルのみ (差分スキップ)
#
# Cron 例 (毎日 02:00):
#   0 2 * * * DB_TYPE=mysql /path/to/db_backup/backup.sh >> /var/log/db_backup/cron.log 2>&1
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

# ─── 引数処理 ─────────────────────────────────────────────────
RUN_INCREMENTAL_AFTER=true
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-incremental) RUN_INCREMENTAL_AFTER=false ;;
        --db)
            MYSQL_TARGET_DBS="$2"
            PG_DATABASE="$2"
            shift ;;
        --dry-run)  DRY_RUN=true ;;
        -h|--help)  grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) log_warn "不明なオプション: $1" ;;
    esac
    shift
done

# ─── バックエンドロード ───────────────────────────────────────
backend="${SCRIPT_DIR}/backends/${DB_TYPE}.sh"
if [[ ! -f "${backend}" ]]; then
    log_error "バックエンドが見つかりません: ${backend}"
    log_error "DB_TYPE に mysql / mariadb / postgresql を指定してください"
    exit 1
fi
source "${backend}"

# ─── メイン処理 ──────────────────────────────────────────────
main() {
    init_dirs
    log_info "========== フルバックアップ開始 [DB_TYPE=${DB_TYPE}] =========="

    check_db_connection || { notify_slack failure "DB 接続失敗 (${DB_TYPE})"; exit 1; }

    local ts; ts=$(date '+%Y%m%d_%H%M%S')
    local backup_dir="${BACKUP_BASE_DIR}/${ts}"
    mkdir -p "${backup_dir}"

    db_full_backup "${backup_dir}" "${ts}"

    purge_old_files "${BACKUP_BASE_DIR}" "${FULL_RETENTION_DAYS}" "*"

    log_info "フルバックアップ完了: ${backup_dir}"
    log_info "=========================================="

    if [[ "${RUN_INCREMENTAL_AFTER}" == "true" ]]; then
        log_info "差分バックアップを続けて実行..."
        "${SCRIPT_DIR}/incremental_backup.sh" \
            || log_warn "差分バックアップで警告が発生しました"
    fi

    notify_slack success "フルバックアップ完了 [${DB_TYPE}]\nDir: ${backup_dir}"
}

trap 'log_error "異常終了 (line ${LINENO})"; notify_slack failure "フルバックアップ失敗 [${DB_TYPE}] (line ${LINENO})"' ERR

main "$@"
