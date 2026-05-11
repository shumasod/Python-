#!/usr/bin/env bash
# ============================================================
# MySQL バイナリログ差分バックアップスクリプト
#
# 機能:
#   - mysqlbinlog でバイナリログをリモートからストリーミング取得
#   - または サーバー上の binlog ファイルを直接コピー
#   - 前回取得した binlog ファイル名・位置から続きを取得
#   - gzip 圧縮 + 世代管理
#
# 実行方式:
#   MODE=stream  → mysqlbinlog --read-from-remote-server でストリーミング (推奨)
#   MODE=copy    → サーバーと同一ホスト上で binlog ファイルを直接コピー
#
# 使い方:
#   ./binlog_backup.sh [--mode stream|copy] [--dry-run]
#
# Cron 例 (15分ごとに差分取得):
#   */15 * * * * /path/to/mysql_backup/binlog_backup.sh >> /var/log/mysql_backup/binlog.log 2>&1
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

# ─── 引数処理 ────────────────────────────────────────────────────
MODE="stream"    # stream or copy
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)   MODE="$2"; shift ;;
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) log_warn "不明なオプション: $1" ;;
    esac
    shift
done

# ─── 状態ファイル (前回の取得位置を記録) ─────────────────────────
STATE_FILE="${BINLOG_BACKUP_DIR}/.last_binlog_state"

# ─── メイン処理 ──────────────────────────────────────────────────

main() {
    init_dirs
    log_info "========== binlog バックアップ開始 (mode=${MODE}) =========="

    check_mysql_connection || { notify_slack failure "MySQL 接続失敗 (binlog)"; exit 1; }

    case "${MODE}" in
        stream) _backup_stream ;;
        copy)   _backup_copy   ;;
        *)
            log_error "不明なモード: ${MODE} (stream または copy を指定)"
            exit 1 ;;
    esac

    # 古い binlog バックアップを削除
    purge_old_files "${BINLOG_BACKUP_DIR}" "${BINLOG_RETENTION_DAYS}" "*.sql.gz"
    purge_old_files "${BINLOG_BACKUP_DIR}" "${BINLOG_RETENTION_DAYS}" "*.bin.gz"

    log_info "========== binlog バックアップ完了 =========="
}

# ─── ストリーミング取得 (mysqlbinlog --read-from-remote-server) ───

_backup_stream() {
    # 現在の binlog ファイル名・位置を取得
    local current_file current_pos
    # shellcheck disable=SC2046
    current_file=$(mysql $(mysql_opts) -N -e "SHOW MASTER STATUS" | awk '{print $1}')
    # shellcheck disable=SC2046
    current_pos=$(mysql  $(mysql_opts) -N -e "SHOW MASTER STATUS" | awk '{print $2}')

    if [[ -z "${current_file}" ]]; then
        log_error "binlog が有効ではありません (log_bin=ON を確認してください)"
        exit 1
    fi

    # 前回の状態を読み込む
    local start_file start_pos
    if [[ -f "${STATE_FILE}" ]]; then
        start_file=$(grep '^BINLOG_FILE=' "${STATE_FILE}" | cut -d= -f2)
        start_pos=$(grep  '^BINLOG_POS='  "${STATE_FILE}" | cut -d= -f2)
        log_info "前回の取得位置: ${start_file}:${start_pos}"
    else
        # 初回: 現在の binlog から開始
        start_file="${current_file}"
        start_pos=4   # binlog の先頭位置 (magic bytes の後)
        log_info "初回実行: ${start_file}:${start_pos} から開始"
    fi

    local ts; ts=$(date '+%Y%m%d_%H%M%S')
    local out_file="${BINLOG_BACKUP_DIR}/binlog_${ts}.sql"

    log_info "ストリーミング取得: ${start_file}(pos=${start_pos}) → ${current_file}(pos=${current_pos})"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY-RUN] mysqlbinlog --read-from-remote-server \\"
        log_info "  --start-position=${start_pos} --stop-position=${current_pos} \\"
        log_info "  ${start_file} > ${out_file}"
    else
        # shellcheck disable=SC2046
        mysqlbinlog \
            $(mysql_opts) \
            --read-from-remote-server \
            --raw \
            --result-file="${BINLOG_BACKUP_DIR}/" \
            --start-position="${start_pos}" \
            "${start_file}" 2>> "${LOG_FILE}" || {
            # raw モード失敗時は SQL 形式にフォールバック
            log_warn "raw モード失敗。SQL 形式で再試行..."
            # shellcheck disable=SC2046
            mysqlbinlog \
                $(mysql_opts) \
                --read-from-remote-server \
                --start-position="${start_pos}" \
                --to-last-log \
                "${start_file}" \
                > "${out_file}" 2>> "${LOG_FILE}"

            _compress_file "${out_file}"
        }

        # 状態ファイルを更新
        _save_state "${current_file}" "${current_pos}"

        local size; size=$(du -sh "${BINLOG_BACKUP_DIR}/${start_file}"* 2>/dev/null | head -1 | cut -f1 || echo "?")
        log_info "ストリーミング取得完了"
    fi
}

# ─── ファイルコピー (同一ホスト上) ──────────────────────────────

_backup_copy() {
    if [[ ! -d "${MYSQL_BINLOG_DIR}" ]]; then
        log_error "binlog ディレクトリが見つかりません: ${MYSQL_BINLOG_DIR}"
        exit 1
    fi

    # 前回コピーした最後のファイルを記録
    local last_copied=""
    if [[ -f "${STATE_FILE}" ]]; then
        last_copied=$(grep '^BINLOG_FILE=' "${STATE_FILE}" | cut -d= -f2)
    fi

    # インデックスファイルから binlog 一覧を取得
    local index_file="${MYSQL_BINLOG_DIR}/${BINLOG_BASENAME}.index"
    if [[ ! -f "${index_file}" ]]; then
        log_error "binlog インデックスが見つかりません: ${index_file}"
        exit 1
    fi

    local copied=0
    while IFS= read -r binlog_path; do
        local binlog_file; binlog_file=$(basename "${binlog_path}")

        # 前回コピー済みより古いファイルはスキップ
        if [[ -n "${last_copied}" && "${binlog_file}" < "${last_copied}" ]]; then
            continue
        fi
        # 現在アクティブなファイルはまだ書き込み中のため後で取得
        # shellcheck disable=SC2046
        local current_active
        current_active=$(mysql $(mysql_opts) -N -e "SHOW MASTER STATUS" | awk '{print $1}')
        if [[ "${binlog_file}" == "${current_active}" ]]; then
            log_info "アクティブ binlog はスキップ (次回以降に取得): ${binlog_file}"
            continue
        fi

        local src="${MYSQL_BINLOG_DIR}/${binlog_file}"
        local dst="${BINLOG_BACKUP_DIR}/${binlog_file}.gz"

        if [[ -f "${dst}" ]]; then
            log_info "スキップ (取得済み): ${binlog_file}"
            last_copied="${binlog_file}"
            continue
        fi

        log_info "コピー: ${src} → ${dst}"
        if [[ "${DRY_RUN}" == "false" ]]; then
            # mysqlbinlog で SQL 形式に変換してから圧縮
            mysqlbinlog "${src}" | gzip -"${COMPRESS_LEVEL}" > "${dst}"
            log_info "  コピー完了: $(du -sh "${dst}" | cut -f1)"
        else
            log_info "[DRY-RUN] mysqlbinlog ${src} | gzip > ${dst}"
        fi

        last_copied="${binlog_file}"
        (( copied++ ))

    done < "${index_file}"

    if [[ -n "${last_copied}" ]]; then
        _save_state "${last_copied}" "0"
    fi

    log_info "コピー完了: ${copied} ファイル"
}

# ─── 状態ファイル保存 ─────────────────────────────────────────────

_save_state() {
    local binlog_file="$1"
    local binlog_pos="$2"
    {
        echo "BINLOG_FILE=${binlog_file}"
        echo "BINLOG_POS=${binlog_pos}"
        echo "LAST_BACKUP=$(date '+%Y-%m-%d %H:%M:%S')"
    } > "${STATE_FILE}"
    log_info "状態を保存: ${binlog_file}:${binlog_pos}"
}

# ─── ファイル圧縮 ────────────────────────────────────────────────

_compress_file() {
    local f="$1"
    [[ "${COMPRESS}" != "true" ]] && return 0
    [[ ! -f "${f}" ]] && return 0
    gzip -"${COMPRESS_LEVEL}" "${f}"
    log_info "圧縮完了: ${f}.gz"
}

# ─── エラーハンドラー ────────────────────────────────────────────

trap 'log_error "スクリプト異常終了 (line ${LINENO})"; notify_slack failure "binlog バックアップ失敗 (line ${LINENO})"' ERR

main "$@"
