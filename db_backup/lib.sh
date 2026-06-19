#!/usr/bin/env bash
# ============================================================
# 共有ライブラリ (全バックエンド共通)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

LOG_FILE="${LOG_DIR}/backup_$(date '+%Y%m%d').log"

# ─── ログ関数 ─────────────────────────────────────────────────
log_info()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]  $*" | tee -a "${LOG_FILE}"; }
log_warn()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN]  $*" | tee -a "${LOG_FILE}" >&2; }
log_error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" | tee -a "${LOG_FILE}" >&2; }

# ─── ディレクトリ初期化 ───────────────────────────────────────
init_dirs() {
    mkdir -p "${BACKUP_BASE_DIR}" "${INCREMENTAL_BACKUP_DIR}" "${LOG_DIR}"
    [[ -n "${PG_WAL_DIR}" ]] && mkdir -p "${PG_WAL_DIR}"
}

# ─── DB 接続確認 (バックエンドに委譲) ─────────────────────────
check_db_connection() {
    case "${DB_TYPE}" in
        mysql|mariadb) _check_mysql_connection ;;
        postgresql)    _check_pg_connection    ;;
        *) log_error "不明な DB_TYPE: ${DB_TYPE} (mysql|mariadb|postgresql)"; return 1 ;;
    esac
}

_check_mysql_connection() {
    local cmd="mysql"
    [[ "${DB_TYPE}" == "mariadb" ]] && command -v mariadb &>/dev/null && cmd="mariadb"
    # shellcheck disable=SC2046
    if ! ${cmd} $(mysql_opts) -e "SELECT 1" &>/dev/null; then
        log_error "MySQL/MariaDB 接続失敗 (host=${MYSQL_HOST}:${MYSQL_PORT} user=${MYSQL_USER})"
        return 1
    fi
    log_info "MySQL/MariaDB 接続OK (host=${MYSQL_HOST}:${MYSQL_PORT})"
}

_check_pg_connection() {
    if ! pg_isready -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" -q; then
        log_error "PostgreSQL 接続失敗 (host=${PG_HOST}:${PG_PORT} user=${PG_USER})"
        return 1
    fi
    log_info "PostgreSQL 接続OK (host=${PG_HOST}:${PG_PORT})"
}

# ─── MySQL/MariaDB 接続オプション ─────────────────────────────
mysql_opts() {
    if [[ -n "${MYSQL_SOCKET}" ]]; then
        printf -- '-S %s -u %s' "${MYSQL_SOCKET}" "${MYSQL_USER}"
    else
        printf -- '-h %s -P %s -u %s' "${MYSQL_HOST}" "${MYSQL_PORT}" "${MYSQL_USER}"
    fi
}

# ─── PostgreSQL 環境変数設定 ──────────────────────────────────
pg_env() {
    export PGHOST="${PG_HOST}"
    export PGPORT="${PG_PORT}"
    export PGUSER="${PG_USER}"
}

# ─── ファイル圧縮 ─────────────────────────────────────────────
compress_file() {
    local f="$1"
    [[ "${COMPRESS}" != "true" || ! -f "${f}" ]] && return 0
    gzip -"${COMPRESS_LEVEL}" "${f}"
    log_info "圧縮完了: ${f}.gz"
}

# ─── バックアップ整合性検証 ───────────────────────────────────
verify_backup_files() {
    local dir="$1"
    local pattern="${2:-*.sql.gz}"
    local failed=0
    local checked=0

    log_info "バックアップ整合性検証: ${dir}/${pattern}"

    while IFS= read -r f; do
        if gzip -t "${f}" 2>/dev/null; then
            log_info "  OK: $(basename "${f}")"
        else
            log_error "  NG (破損): $(basename "${f}")"
            (( failed++ ))
        fi
        (( checked++ ))
    done < <(find "${dir}" -maxdepth 1 -name "${pattern}" -newer "${dir}/.last_verified" 2>/dev/null \
              || find "${dir}" -maxdepth 1 -name "${pattern}" | sort | tail -5)

    if [[ ${failed} -gt 0 ]]; then
        log_error "整合性検証失敗: ${failed}/${checked} ファイルが破損しています"
        return 1
    fi

    log_info "整合性検証完了: ${checked} ファイル全て正常"
    touch "${dir}/.last_verified" 2>/dev/null || true
    return 0
}

# ─── 世代管理 ─────────────────────────────────────────────────
purge_old_files() {
    local dir="$1" days="$2" pattern="$3"
    find "${dir}" -maxdepth 1 -name "${pattern}" -mtime "+${days}" -exec rm -rf {} \; 2>/dev/null || true
    log_info "古いファイル削除: ${dir}/${pattern} (${days}日以前)"
}

# ─── Slack 通知 ───────────────────────────────────────────────
notify_slack() {
    local status="$1" message="$2"
    [[ -z "${SLACK_WEBHOOK_URL}" ]] && return 0

    local color="good"
    [[ "${status}" == "failure" ]] && color="danger"
    [[ "${status}" == "warning" ]] && color="warning"

    local payload
    payload=$(printf '{"channel":"%s","username":"%s","attachments":[{"color":"%s","text":"[%s][%s] %s"}]}' \
        "${SLACK_CHANNEL}" "${SLACK_USERNAME}" "${color}" "$(hostname)" "${DB_TYPE}" "${message}")
    curl -s -X POST -H 'Content-type: application/json' \
        --data "${payload}" "${SLACK_WEBHOOK_URL}" &>/dev/null || true
}
