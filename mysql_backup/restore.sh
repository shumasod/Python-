#!/usr/bin/env bash
# ============================================================
# MySQL リストアスクリプト
#
# 機能:
#   1. フルバックアップ (mysqldump) をリストア
#   2. 指定した日時までの binlog を適用 (ポイントインタイムリカバリ)
#
# 使い方:
#   # フルリストアのみ
#   ./restore.sh --full /var/backup/mysql/20240101_020000/all_databases_20240101_020000.sql.gz
#
#   # フル + binlog でポイントインタイムリカバリ
#   ./restore.sh --full /path/to/dump.sql.gz \
#                --binlog-dir /var/backup/mysql/binlog \
#                --stop-datetime "2024-01-01 10:30:00"
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

# ─── 引数処理 ────────────────────────────────────────────────────
FULL_DUMP=""
BINLOG_DIR=""
STOP_DATETIME=""
START_DATETIME=""
DRY_RUN=false
TARGET_DB=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --full)           FULL_DUMP="$2";         shift ;;
        --binlog-dir)     BINLOG_DIR="$2";         shift ;;
        --stop-datetime)  STOP_DATETIME="$2";      shift ;;
        --start-datetime) START_DATETIME="$2";     shift ;;
        --db)             TARGET_DB="$2";           shift ;;
        --dry-run)        DRY_RUN=true ;;
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

    if [[ -z "${FULL_DUMP}" ]]; then
        log_error "--full オプションでダンプファイルを指定してください"
        exit 1
    fi

    if [[ ! -f "${FULL_DUMP}" ]]; then
        log_error "ダンプファイルが見つかりません: ${FULL_DUMP}"
        exit 1
    fi

    log_info "========== MySQL リストア開始 =========="
    log_warn "!!! 実行前にデータベースのバックアップが取れていることを確認してください !!!"

    check_mysql_connection

    # ─── Step 1: フルリストア ─────────────────────────────────────
    log_info "Step 1: フルダンプからリストア: ${FULL_DUMP}"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY-RUN] zcat ${FULL_DUMP} | mysql ..."
    else
        if [[ "${FULL_DUMP}" == *.gz ]]; then
            # shellcheck disable=SC2046
            zcat "${FULL_DUMP}" | mysql $(mysql_opts) 2>> "${LOG_FILE}"
        else
            # shellcheck disable=SC2046
            mysql $(mysql_opts) < "${FULL_DUMP}" 2>> "${LOG_FILE}"
        fi
        log_info "フルリストア完了"
    fi

    # ─── Step 2: binlog 適用 ──────────────────────────────────────
    if [[ -z "${BINLOG_DIR}" ]]; then
        log_info "binlog ディレクトリの指定なし。フルリストアのみ完了。"
        return 0
    fi

    log_info "Step 2: binlog を適用してポイントインタイムリカバリ"
    log_info "  binlog ディレクトリ: ${BINLOG_DIR}"
    [[ -n "${START_DATETIME}" ]] && log_info "  開始日時: ${START_DATETIME}"
    [[ -n "${STOP_DATETIME}"  ]] && log_info "  終了日時: ${STOP_DATETIME}"

    _apply_binlogs

    log_info "========== リストア完了 =========="
}

# ─── binlog 適用 ──────────────────────────────────────────────────

_apply_binlogs() {
    # binlog ディレクトリ内の .sql.gz または生 binlog を昇順で処理
    local mysqlbinlog_opts=()
    [[ -n "${START_DATETIME}" ]] && mysqlbinlog_opts+=(--start-datetime="${START_DATETIME}")
    [[ -n "${STOP_DATETIME}"  ]] && mysqlbinlog_opts+=(--stop-datetime="${STOP_DATETIME}")
    [[ -n "${TARGET_DB}"      ]] && mysqlbinlog_opts+=(--database="${TARGET_DB}")

    local binlog_files=()
    while IFS= read -r f; do
        binlog_files+=("$f")
    done < <(find "${BINLOG_DIR}" -name "*.sql.gz" -o -name "*.bin.gz" | sort)

    if [[ ${#binlog_files[@]} -eq 0 ]]; then
        log_warn "適用する binlog ファイルが見つかりません: ${BINLOG_DIR}"
        return 0
    fi

    log_info "適用する binlog: ${#binlog_files[@]} ファイル"

    for binlog_gz in "${binlog_files[@]}"; do
        log_info "  適用: ${binlog_gz}"
        if [[ "${DRY_RUN}" == "true" ]]; then
            log_info "  [DRY-RUN] zcat ${binlog_gz} | mysqlbinlog ... | mysql"
            continue
        fi
        # shellcheck disable=SC2046,SC2086
        zcat "${binlog_gz}" | mysqlbinlog "${mysqlbinlog_opts[@]+"${mysqlbinlog_opts[@]}"}" - \
            | mysql $(mysql_opts) 2>> "${LOG_FILE}"
    done

    log_info "binlog 適用完了"
}

trap 'log_error "リストア中に異常終了 (line ${LINENO})"' ERR

main "$@"
