#!/usr/bin/env bash
# 共通ライブラリ (backup.sh / binlog_backup.sh から source して使用)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# ─── ログ関数 ────────────────────────────────────────────────────

_log() {
    local level="$1"; shift
    local ts; ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "${ts} [${level}] $*" | tee -a "${LOG_FILE}"
}
log_info()  { _log INFO  "$@"; }
log_warn()  { _log WARN  "$@"; }
log_error() { _log ERROR "$@"; }

# ─── 初期化 ──────────────────────────────────────────────────────

init_dirs() {
    mkdir -p "${BACKUP_BASE_DIR}" "${BINLOG_BACKUP_DIR}" "${LOG_DIR}"
    # ログローテーション
    if [[ -f "${LOG_FILE}" ]]; then
        local size_mb; size_mb=$(du -m "${LOG_FILE}" | cut -f1)
        if (( size_mb >= MAX_LOG_SIZE_MB )); then
            mv "${LOG_FILE}" "${LOG_FILE}.$(date +%Y%m%d%H%M%S).old"
            log_info "ログファイルをローテーションしました"
        fi
    fi
}

# ─── MySQL 接続オプション生成 ─────────────────────────────────────

mysql_opts() {
    local opts=()
    opts+=(-u "${MYSQL_USER}")
    [[ -n "${MYSQL_PASSWORD}" ]] && opts+=(-p"${MYSQL_PASSWORD}")
    [[ -n "${MYSQL_SOCKET}"   ]] && opts+=(--socket="${MYSQL_SOCKET}") \
                                 || opts+=(-h "${MYSQL_HOST}" -P "${MYSQL_PORT}")
    printf '%s ' "${opts[@]}"
}

# ─── MySQL 疎通確認 ───────────────────────────────────────────────

check_mysql_connection() {
    log_info "MySQL 接続確認中..."
    # shellcheck disable=SC2046
    if ! mysql $(mysql_opts) -e "SELECT 1;" &>/dev/null; then
        log_error "MySQL に接続できません。設定を確認してください。"
        return 1
    fi
    log_info "MySQL 接続 OK"
}

# ─── 現在の binlog 位置取得 ──────────────────────────────────────

get_binlog_status() {
    # shellcheck disable=SC2046
    mysql $(mysql_opts) -e "SHOW MASTER STATUS\G" 2>/dev/null
}

# ─── Slack 通知 ──────────────────────────────────────────────────

notify_slack() {
    local status="$1"   # "success" or "failure"
    local message="$2"

    [[ -z "${SLACK_WEBHOOK_URL}" ]] && return 0
    [[ "${status}" == "success" && "${NOTIFY_ON_SUCCESS}" == "false" ]] && return 0
    [[ "${status}" == "failure" && "${NOTIFY_ON_FAILURE}" == "false" ]] && return 0

    local emoji=":white_check_mark:"
    [[ "${status}" == "failure" ]] && emoji=":x:"

    local payload
    payload=$(cat <<EOF
{
  "text": "${emoji} *MySQL Backup ${status^^}*\nHost: $(hostname)\n${message}"
}
EOF
    )
    curl -s -X POST -H 'Content-type: application/json' \
        --data "${payload}" "${SLACK_WEBHOOK_URL}" &>/dev/null || true
}

# ─── 古いファイル削除 ────────────────────────────────────────────

purge_old_files() {
    local dir="$1"
    local days="$2"
    local pattern="${3:-*.sql.gz}"

    log_info "古いバックアップを削除: ${dir} (${days}日以上)"
    find "${dir}" -maxdepth 1 -name "${pattern}" \
        -mtime "+${days}" -type f -delete -print \
        | while read -r f; do log_info "  削除: ${f}"; done
}
