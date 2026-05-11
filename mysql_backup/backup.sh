#!/usr/bin/env bash
# ============================================================
# MySQL フルバックアップスクリプト (mysqldump + binlog 位置記録)
#
# 機能:
#   - mysqldump でフルバックアップを取得
#   - --master-data=2 で binlog ファイル名・位置をコメントとして記録
#   - --flush-logs でバックアップ前に binlog をローテーション
#   - gzip 圧縮
#   - 取得後に binlog 差分バックアップも実行 (オプション)
#   - 古いバックアップの自動削除
#
# 使い方:
#   ./backup.sh [--no-binlog] [--db データベース名] [--dry-run]
#
# Cron 例 (毎日 2:00 に実行):
#   0 2 * * * /path/to/mysql_backup/backup.sh >> /var/log/mysql_backup/cron.log 2>&1
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

# ─── 引数処理 ────────────────────────────────────────────────────
RUN_BINLOG_AFTER=true
DRY_RUN=false
OVERRIDE_DB=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-binlog)  RUN_BINLOG_AFTER=false ;;
        --db)         OVERRIDE_DB="$2"; shift ;;
        --dry-run)    DRY_RUN=true ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) log_warn "不明なオプション: $1" ;;
    esac
    shift
done

# ─── メイン処理 ──────────────────────────────────────────────────

main() {
    init_dirs
    log_info "========== フルバックアップ開始 =========="

    check_mysql_connection || { notify_slack failure "MySQL 接続失敗"; exit 1; }

    local ts; ts=$(date '+%Y%m%d_%H%M%S')
    local backup_dir="${BACKUP_BASE_DIR}/${ts}"
    mkdir -p "${backup_dir}"

    # バックアップ対象 DB を決定
    local target_dbs
    if [[ -n "${OVERRIDE_DB}" ]]; then
        target_dbs="${OVERRIDE_DB}"
    elif [[ -n "${TARGET_DATABASES}" ]]; then
        target_dbs="${TARGET_DATABASES}"
    else
        target_dbs=""  # 空 = --all-databases
    fi

    local dump_file
    if [[ -z "${target_dbs}" ]]; then
        dump_file="${backup_dir}/all_databases_${ts}.sql"
        _run_dump_all "${dump_file}"
    else
        for db in ${target_dbs}; do
            dump_file="${backup_dir}/${db}_${ts}.sql"
            _run_dump_single "${db}" "${dump_file}"
        done
    fi

    # binlog 位置をメタファイルに保存
    _save_binlog_position "${backup_dir}/${ts}.meta"

    # 圧縮
    if [[ "${COMPRESS}" == "true" ]]; then
        _compress_dir "${backup_dir}"
    fi

    # 世代管理
    purge_old_files "${BACKUP_BASE_DIR}" "${FULL_RETENTION_DAYS}" "*"

    log_info "フルバックアップ完了: ${backup_dir}"
    log_info "=========================================="

    # binlog 差分バックアップを続けて実行
    if [[ "${RUN_BINLOG_AFTER}" == "true" ]]; then
        log_info "binlog バックアップを続けて実行します..."
        "${SCRIPT_DIR}/binlog_backup.sh" || log_warn "binlog バックアップで警告が発生しました"
    fi

    notify_slack success "フルバックアップ完了\nDir: ${backup_dir}"
}

# ─── 全DB ダンプ ──────────────────────────────────────────────────

_run_dump_all() {
    local out_file="$1"
    log_info "全データベースダンプ開始 → ${out_file}"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY-RUN] mysqldump --all-databases ${MYSQLDUMP_OPTS}"
        return 0
    fi

    # shellcheck disable=SC2046,SC2086
    mysqldump $(mysql_opts) \
        ${MYSQLDUMP_OPTS} \
        --all-databases \
        > "${out_file}" 2>> "${LOG_FILE}"

    local size; size=$(du -sh "${out_file}" | cut -f1)
    log_info "ダンプ完了: ${out_file} (${size})"
}

# ─── 単一DB ダンプ ────────────────────────────────────────────────

_run_dump_single() {
    local db="$1"
    local out_file="$2"
    log_info "データベースダンプ開始: ${db} → ${out_file}"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY-RUN] mysqldump ${db} ${MYSQLDUMP_OPTS}"
        return 0
    fi

    # shellcheck disable=SC2046,SC2086
    mysqldump $(mysql_opts) \
        ${MYSQLDUMP_OPTS} \
        "${db}" \
        > "${out_file}" 2>> "${LOG_FILE}"

    local size; size=$(du -sh "${out_file}" | cut -f1)
    log_info "ダンプ完了: ${out_file} (${size})"
}

# ─── binlog 位置保存 ──────────────────────────────────────────────

_save_binlog_position() {
    local meta_file="$1"
    local status; status=$(get_binlog_status)

    {
        echo "# バックアップ取得時点の binlog 位置"
        echo "# 生成日時: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "# ホスト: $(hostname)"
        echo ""
        echo "${status}"
    } > "${meta_file}"

    log_info "binlog 位置を保存: ${meta_file}"
    log_info "$(grep -E 'File|Position|Executed_Gtid_Set' "${meta_file}" | head -5)"
}

# ─── ディレクトリ圧縮 ────────────────────────────────────────────

_compress_dir() {
    local dir="$1"
    log_info "圧縮中: ${dir}/*.sql"

    find "${dir}" -name "*.sql" -type f | while read -r f; do
        gzip -"${COMPRESS_LEVEL}" "${f}"
        log_info "  圧縮完了: ${f}.gz"
    done
}

# ─── エラーハンドラー ────────────────────────────────────────────

trap 'log_error "スクリプト異常終了 (line ${LINENO})"; notify_slack failure "フルバックアップ失敗 (line ${LINENO})"' ERR

main "$@"
