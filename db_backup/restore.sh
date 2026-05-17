#!/usr/bin/env bash
# ============================================================
# データベースリストアスクリプト
# 対応DB: MySQL / MariaDB / PostgreSQL
#
# 使い方:
#   # フルリストアのみ
#   DB_TYPE=mysql ./restore.sh \
#       --full /var/backup/db/full/20240101_020000/all_databases_20240101_020000.sql.gz
#
#   DB_TYPE=postgresql ./restore.sh \
#       --full /var/backup/db/full/20240101_020000/mydb_20240101_020000.dump
#
#   # フル + 差分 でポイントインタイムリカバリ (PITR)
#   DB_TYPE=mysql ./restore.sh \
#       --full /path/to/dump.sql.gz \
#       --incremental-dir /var/backup/db/incremental \
#       --stop-datetime "2024-01-01 10:30:00"
#
#   DB_TYPE=postgresql ./restore.sh \
#       --full /path/to/dump.sql.gz \
#       --incremental-dir /var/backup/db/wal \
#       --stop-datetime "2024-01-01 10:30:00"
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

# ─── 引数処理 ─────────────────────────────────────────────────
FULL_DUMP=""
INCREMENTAL_DIR=""
STOP_DATETIME=""
START_DATETIME=""
DRY_RUN=false
TARGET_DB=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --full)             FULL_DUMP="$2";         shift ;;
        --incremental-dir)  INCREMENTAL_DIR="$2";   shift ;;
        --stop-datetime)    STOP_DATETIME="$2";     shift ;;
        --start-datetime)   START_DATETIME="$2";    shift ;;
        --db)               TARGET_DB="$2";          shift ;;
        --dry-run)          DRY_RUN=true ;;
        -h|--help)  grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) log_warn "不明なオプション: $1" ;;
    esac
    shift
done

# ─── バックエンドロード ───────────────────────────────────────
source "${SCRIPT_DIR}/backends/${DB_TYPE}.sh"

# ─── メイン処理 ──────────────────────────────────────────────
main() {
    init_dirs

    if [[ -z "${FULL_DUMP}" ]]; then
        log_error "--full オプションでダンプファイルを指定してください"
        exit 1
    fi
    if [[ ! -e "${FULL_DUMP}" ]]; then
        log_error "ダンプファイルが見つかりません: ${FULL_DUMP}"
        exit 1
    fi

    log_info "========== リストア開始 [DB_TYPE=${DB_TYPE}] =========="
    log_warn "!!! 実行前に現在のデータベースのバックアップが取れていることを確認してください !!!"

    check_db_connection

    log_info "Step 1: フルリストア"
    db_restore_full "${FULL_DUMP}"

    if [[ -n "${INCREMENTAL_DIR}" ]]; then
        log_info "Step 2: 差分適用 (PITR)"
        [[ -z "${STOP_DATETIME}" ]] && log_warn "--stop-datetime 未指定: 全差分を適用します"
        db_restore_incremental \
            "${INCREMENTAL_DIR}" \
            "${STOP_DATETIME}" \
            "${START_DATETIME}" \
            "${TARGET_DB}"
    else
        log_info "差分ディレクトリの指定なし。フルリストアのみ完了。"
    fi

    log_info "========== リストア完了 =========="
}

trap 'log_error "リストア中に異常終了 (line ${LINENO})"' ERR

main "$@"
