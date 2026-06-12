#!/usr/bin/env bash
# ============================================================
# データベース インデックスヘルスチェックスクリプト
# 対応DB: MySQL / MariaDB / PostgreSQL
#
# 機能:
#   - フルスキャン・非効率クエリをDBの統計情報から抽出
#   - カバリングインデックス候補のクエリパターンをレポート
#   - 未使用インデックスの検出
#
# 使い方:
#   DB_TYPE=mysql      ./index_check.sh [--top N] [--dry-run]
#   DB_TYPE=postgresql ./index_check.sh [--top N] [--threshold RATIO]
#
# 前提:
#   MySQL/MariaDB: performance_schema が有効 (performance_schema=ON)
#   PostgreSQL:    pg_stat_statements 拡張がインストール済み
#                  (CREATE EXTENSION pg_stat_statements;)
#
# Cron 例 (毎日 03:00 にレポート生成):
#   0 3 * * * DB_TYPE=mysql /path/to/db_backup/index_check.sh \
#       >> /var/log/db_backup/index_check.log 2>&1
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

# ─── 引数処理 ─────────────────────────────────────────────────
TOP_N=20
SCAN_RATIO_THRESHOLD=10   # rows_examined / rows_returned の閾値
DRY_RUN=false
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --top)       TOP_N="$2";               shift ;;
        --threshold) SCAN_RATIO_THRESHOLD="$2"; shift ;;
        --output)    OUTPUT_FILE="$2";          shift ;;
        --dry-run)   DRY_RUN=true ;;
        -h|--help)   grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) log_warn "不明なオプション: $1" ;;
    esac
    shift
done

# ─── バックエンドロード ───────────────────────────────────────
source "${SCRIPT_DIR}/backends/${DB_TYPE}.sh"

# ─── メイン処理 ──────────────────────────────────────────────
main() {
    init_dirs
    log_info "========== インデックスヘルスチェック開始 [DB_TYPE=${DB_TYPE}] =========="
    log_info "スキャン比率閾値: ${SCAN_RATIO_THRESHOLD}:1 / 上位: ${TOP_N} 件"

    check_db_connection || { log_error "DB 接続失敗"; exit 1; }

    local ts; ts=$(date '+%Y%m%d_%H%M%S')
    local report_file="${LOG_DIR}/index_check_${ts}.txt"
    [[ -n "${OUTPUT_FILE}" ]] && report_file="${OUTPUT_FILE}"

    {
        echo "========================================"
        echo "  DB インデックスヘルスチェックレポート"
        echo "  生成日時: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "  DB_TYPE: ${DB_TYPE}"
        echo "  ホスト: $(hostname)"
        echo "========================================"
        echo ""

        db_check_slow_queries
        echo ""
        db_check_unused_indexes
        echo ""
        db_check_duplicate_indexes
    } | tee "${report_file}"

    log_info "レポート保存: ${report_file}"
    log_info "========== インデックスヘルスチェック完了 =========="
}

trap 'log_error "異常終了 (line ${LINENO})"' ERR

main "$@"
