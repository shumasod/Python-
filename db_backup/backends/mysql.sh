#!/usr/bin/env bash
# ============================================================
# MySQL バックアップバックエンド
# MariaDB バックエンドはこのファイルを継承して差分を上書きする
# ============================================================

# ─── フルバックアップ ─────────────────────────────────────────
db_full_backup() {
    local backup_dir="$1" ts="$2"

    if [[ -z "${MYSQL_TARGET_DBS:-}" ]]; then
        local out_file="${backup_dir}/all_databases_${ts}.sql"
        _mysql_dump_all "${out_file}"
    else
        for db in ${MYSQL_TARGET_DBS}; do
            _mysql_dump_single "${db}" "${backup_dir}/${db}_${ts}.sql"
        done
    fi

    _mysql_save_binlog_position "${backup_dir}/${ts}.meta"

    if [[ "${COMPRESS}" == "true" ]]; then
        find "${backup_dir}" -name "*.sql" -type f | while read -r f; do
            compress_file "${f}"
        done
    fi
}

_mysql_dump_cmd() { echo "mysqldump"; }

_mysql_dump_all() {
    local out_file="$1"
    log_info "全DBダンプ → ${out_file}"
    [[ "${DRY_RUN:-false}" == "true" ]] && { log_info "[DRY-RUN] $(_mysql_dump_cmd) --all-databases"; return 0; }
    # shellcheck disable=SC2046,SC2086
    "$(_mysql_dump_cmd)" $(mysql_opts) ${MYSQLDUMP_OPTS} --all-databases \
        > "${out_file}" 2>> "${LOG_FILE}"
    log_info "ダンプ完了: $(du -sh "${out_file}" | cut -f1)"
}

_mysql_dump_single() {
    local db="$1" out_file="$2"
    log_info "DBダンプ: ${db} → ${out_file}"
    [[ "${DRY_RUN:-false}" == "true" ]] && { log_info "[DRY-RUN] $(_mysql_dump_cmd) ${db}"; return 0; }
    # shellcheck disable=SC2046,SC2086
    "$(_mysql_dump_cmd)" $(mysql_opts) ${MYSQLDUMP_OPTS} "${db}" \
        > "${out_file}" 2>> "${LOG_FILE}"
    log_info "ダンプ完了: $(du -sh "${out_file}" | cut -f1)"
}

_mysql_save_binlog_position() {
    local meta_file="$1"
    # shellcheck disable=SC2046
    local status; status=$(mysql $(mysql_opts) -N -e "SHOW MASTER STATUS" 2>/dev/null || echo "")
    {
        echo "# バックアップ取得時点の binlog 位置"
        echo "# 生成日時: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "# ホスト: $(hostname)"
        echo ""
        echo "${status}"
    } > "${meta_file}"
    log_info "binlog 位置を保存: ${meta_file}"
}

# ─── 差分バックアップ (binlog) ────────────────────────────────
_MYSQL_STATE_FILE="${INCREMENTAL_BACKUP_DIR}/.last_mysql_state"

db_incremental_backup() {
    case "${BINLOG_BACKUP_MODE:-stream}" in
        stream) _mysql_backup_stream ;;
        copy)   _mysql_backup_copy   ;;
        *) log_error "不明なモード: ${BINLOG_BACKUP_MODE} (stream|copy)"; return 1 ;;
    esac

    purge_old_files "${INCREMENTAL_BACKUP_DIR}" "${INCREMENTAL_RETENTION_DAYS}" "*.sql.gz"
    purge_old_files "${INCREMENTAL_BACKUP_DIR}" "${INCREMENTAL_RETENTION_DAYS}" "*.bin.gz"
}

_mysql_backup_stream() {
    # shellcheck disable=SC2046
    local current_file; current_file=$(mysql $(mysql_opts) -N -e "SHOW MASTER STATUS" | awk '{print $1}')
    # shellcheck disable=SC2046
    local current_pos;  current_pos=$(mysql  $(mysql_opts) -N -e "SHOW MASTER STATUS" | awk '{print $2}')

    if [[ -z "${current_file}" ]]; then
        log_error "binlog が無効 (my.cnf で log_bin=ON を確認してください)"
        return 1
    fi

    local start_file start_pos
    if [[ -f "${_MYSQL_STATE_FILE}" ]]; then
        start_file=$(grep '^BINLOG_FILE=' "${_MYSQL_STATE_FILE}" | cut -d= -f2)
        start_pos=$(grep  '^BINLOG_POS='  "${_MYSQL_STATE_FILE}" | cut -d= -f2)
        log_info "前回の取得位置: ${start_file}:${start_pos}"
    else
        start_file="${current_file}"
        start_pos=4
        log_info "初回実行: ${start_file}:${start_pos} から開始"
    fi

    local ts; ts=$(date '+%Y%m%d_%H%M%S')
    local out_file="${INCREMENTAL_BACKUP_DIR}/binlog_${ts}.sql"

    log_info "binlog ストリーミング: ${start_file}(pos=${start_pos}) → ${current_file}(pos=${current_pos})"
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_info "[DRY-RUN] mysqlbinlog --read-from-remote-server --start-position=${start_pos} ${start_file}"
        return 0
    fi

    # shellcheck disable=SC2046
    mysqlbinlog $(mysql_opts) --read-from-remote-server --raw \
        --result-file="${INCREMENTAL_BACKUP_DIR}/" \
        --start-position="${start_pos}" \
        "${start_file}" 2>> "${LOG_FILE}" || {
        log_warn "raw モード失敗。SQL 形式で再試行..."
        # shellcheck disable=SC2046
        mysqlbinlog $(mysql_opts) --read-from-remote-server \
            --start-position="${start_pos}" --to-last-log \
            "${start_file}" > "${out_file}" 2>> "${LOG_FILE}"
        compress_file "${out_file}"
    }

    _mysql_save_state "${current_file}" "${current_pos}"
    log_info "ストリーミング取得完了"
}

_mysql_backup_copy() {
    [[ ! -d "${MYSQL_BINLOG_DIR}" ]] && { log_error "binlog ディレクトリが見つかりません: ${MYSQL_BINLOG_DIR}"; return 1; }

    local index_file="${MYSQL_BINLOG_DIR}/${BINLOG_BASENAME}.index"
    [[ ! -f "${index_file}" ]] && { log_error "binlog インデックスが見つかりません: ${index_file}"; return 1; }

    local last_copied=""
    [[ -f "${_MYSQL_STATE_FILE}" ]] && last_copied=$(grep '^BINLOG_FILE=' "${_MYSQL_STATE_FILE}" | cut -d= -f2)

    # shellcheck disable=SC2046
    local current_active; current_active=$(mysql $(mysql_opts) -N -e "SHOW MASTER STATUS" | awk '{print $1}')
    local copied=0

    while IFS= read -r binlog_path; do
        local binlog_file; binlog_file=$(basename "${binlog_path}")
        [[ -n "${last_copied}" && "${binlog_file}" < "${last_copied}" ]] && continue
        [[ "${binlog_file}" == "${current_active}" ]] && {
            log_info "アクティブ binlog はスキップ: ${binlog_file}"; continue
        }

        local dst="${INCREMENTAL_BACKUP_DIR}/${binlog_file}.gz"
        if [[ -f "${dst}" ]]; then
            log_info "取得済みスキップ: ${binlog_file}"
            last_copied="${binlog_file}"
            continue
        fi

        log_info "コピー: ${MYSQL_BINLOG_DIR}/${binlog_file} → ${dst}"
        if [[ "${DRY_RUN:-false}" == "false" ]]; then
            mysqlbinlog "${MYSQL_BINLOG_DIR}/${binlog_file}" | gzip -"${COMPRESS_LEVEL}" > "${dst}"
        fi
        last_copied="${binlog_file}"
        (( copied++ ))
    done < "${index_file}"

    [[ -n "${last_copied}" ]] && _mysql_save_state "${last_copied}" "0"
    log_info "コピー完了: ${copied} ファイル"
}

_mysql_save_state() {
    {
        echo "BINLOG_FILE=$1"
        echo "BINLOG_POS=$2"
        echo "LAST_BACKUP=$(date '+%Y-%m-%d %H:%M:%S')"
    } > "${_MYSQL_STATE_FILE}"
    log_info "状態を保存: $1:$2"
}

# ─── リストア ─────────────────────────────────────────────────
db_restore_full() {
    local dump_file="$1"
    log_info "フルリストア: ${dump_file}"
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_info "[DRY-RUN] zcat ${dump_file} | mysql ..."
        return 0
    fi

    if [[ "${dump_file}" == *.gz ]]; then
        # shellcheck disable=SC2046
        zcat "${dump_file}" | mysql $(mysql_opts) 2>> "${LOG_FILE}"
    else
        # shellcheck disable=SC2046
        mysql $(mysql_opts) < "${dump_file}" 2>> "${LOG_FILE}"
    fi
    log_info "フルリストア完了"
}

db_restore_incremental() {
    local incremental_dir="$1" stop_datetime="${2:-}" start_datetime="${3:-}" target_db="${4:-}"

    local opts=()
    [[ -n "${start_datetime}" ]] && opts+=(--start-datetime="${start_datetime}")
    [[ -n "${stop_datetime}"  ]] && opts+=(--stop-datetime="${stop_datetime}")
    [[ -n "${target_db}"      ]] && opts+=(--database="${target_db}")

    local files=()
    while IFS= read -r f; do files+=("$f"); done \
        < <(find "${incremental_dir}" \( -name "*.sql.gz" -o -name "*.bin.gz" \) | sort)

    if [[ ${#files[@]} -eq 0 ]]; then
        log_warn "適用する binlog ファイルが見つかりません: ${incremental_dir}"
        return 0
    fi

    log_info "適用する binlog: ${#files[@]} ファイル"
    for f in "${files[@]}"; do
        log_info "  適用: ${f}"
        if [[ "${DRY_RUN:-false}" == "true" ]]; then
            log_info "  [DRY-RUN] zcat ${f} | mysqlbinlog ... | mysql"
            continue
        fi
        # shellcheck disable=SC2046
        zcat "${f}" | mysqlbinlog "${opts[@]+"${opts[@]}"}" - \
            | mysql $(mysql_opts) 2>> "${LOG_FILE}"
    done
    log_info "binlog 適用完了"
}

# ─── インデックスヘルスチェック ──────────────────────────────

db_check_slow_queries() {
    echo "=== フルスキャン / 非効率クエリ TOP ${TOP_N:-20} ==="
    echo "(スキャン比率 rows_examined / rows_sent >= ${SCAN_RATIO_THRESHOLD:-10})"
    echo ""

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        echo "[DRY-RUN] performance_schema.events_statements_summary_by_digest を参照"
        return 0
    fi

    # performance_schema が有効かチェック
    # shellcheck disable=SC2046
    local ps_enabled
    ps_enabled=$(mysql $(mysql_opts) -N -e \
        "SELECT @@performance_schema" 2>/dev/null || echo "0")
    if [[ "${ps_enabled}" != "1" ]]; then
        echo "  ⚠ performance_schema が無効です。my.cnf で performance_schema=ON を設定してください。"
        return 0
    fi

    # shellcheck disable=SC2046
    mysql $(mysql_opts) --table -e "
SELECT
    SUBSTR(DIGEST_TEXT, 1, 80)                         AS query_pattern,
    COUNT_STAR                                         AS exec_count,
    ROUND(ROWS_EXAMINED_AVG / NULLIF(ROWS_SENT_AVG, 0), 0) AS scan_ratio,
    ROUND(ROWS_EXAMINED_AVG, 0)                        AS avg_rows_examined,
    ROUND(ROWS_SENT_AVG, 0)                            AS avg_rows_returned,
    ROUND(AVG_TIMER_WAIT / 1e9, 2)                     AS avg_latency_ms,
    SCHEMA_NAME                                        AS db_name
FROM performance_schema.events_statements_summary_by_digest
WHERE ROWS_EXAMINED_AVG / NULLIF(ROWS_SENT_AVG, 0) >= ${SCAN_RATIO_THRESHOLD:-10}
  AND COUNT_STAR >= 5
  AND SCHEMA_NAME IS NOT NULL
  AND SCHEMA_NAME NOT IN ('performance_schema', 'information_schema', 'mysql', 'sys')
ORDER BY scan_ratio DESC, COUNT_STAR DESC
LIMIT ${TOP_N:-20};
" 2>/dev/null || echo "  ⚠ クエリ取得失敗 (権限不足の可能性)"
}

db_check_unused_indexes() {
    echo "=== 未使用インデックス ==="
    echo "(サーバー起動後に一度も使われていないインデックス)"
    echo ""

    [[ "${DRY_RUN:-false}" == "true" ]] && {
        echo "[DRY-RUN] performance_schema.table_io_waits_summary_by_index_usage を参照"
        return 0
    }

    # shellcheck disable=SC2046
    mysql $(mysql_opts) --table -e "
SELECT
    OBJECT_SCHEMA  AS db_name,
    OBJECT_NAME    AS table_name,
    INDEX_NAME     AS index_name,
    COUNT_FETCH    AS fetch_count
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE INDEX_NAME IS NOT NULL
  AND INDEX_NAME != 'PRIMARY'
  AND COUNT_FETCH = 0
  AND OBJECT_SCHEMA NOT IN ('performance_schema', 'information_schema', 'mysql', 'sys')
ORDER BY OBJECT_SCHEMA, OBJECT_NAME, INDEX_NAME
LIMIT ${TOP_N:-20};
" 2>/dev/null || echo "  ⚠ 未使用インデックス取得失敗"
}

db_check_duplicate_indexes() {
    echo "=== 重複インデックス候補 ==="
    echo "(同じテーブルに同一先頭カラムを持つインデックスが存在する場合)"
    echo ""

    [[ "${DRY_RUN:-false}" == "true" ]] && {
        echo "[DRY-RUN] information_schema.STATISTICS を参照"
        return 0
    }

    # shellcheck disable=SC2046
    mysql $(mysql_opts) --table -e "
SELECT
    s1.TABLE_SCHEMA  AS db_name,
    s1.TABLE_NAME    AS table_name,
    s1.INDEX_NAME    AS index_1,
    s2.INDEX_NAME    AS index_2,
    s1.COLUMN_NAME   AS first_column
FROM information_schema.STATISTICS s1
JOIN information_schema.STATISTICS s2
  ON  s1.TABLE_SCHEMA = s2.TABLE_SCHEMA
  AND s1.TABLE_NAME   = s2.TABLE_NAME
  AND s1.COLUMN_NAME  = s2.COLUMN_NAME
  AND s1.SEQ_IN_INDEX = 1
  AND s2.SEQ_IN_INDEX = 1
  AND s1.INDEX_NAME  <  s2.INDEX_NAME
WHERE s1.TABLE_SCHEMA NOT IN ('performance_schema', 'information_schema', 'mysql', 'sys')
ORDER BY s1.TABLE_SCHEMA, s1.TABLE_NAME
LIMIT ${TOP_N:-20};
" 2>/dev/null || echo "  ⚠ 重複インデックス取得失敗"
}

# ─── セットアップ案内 ─────────────────────────────────────────
db_setup_instructions() {
    cat <<'SQL'

  -- MySQL に root で接続して以下を実行してください:
  CREATE USER IF NOT EXISTS 'backup_user'@'localhost'
      IDENTIFIED BY 'strong_password_here';

  GRANT SELECT, SHOW VIEW, TRIGGER, LOCK TABLES,
        PROCESS, RELOAD, REPLICATION CLIENT ON *.*
        TO 'backup_user'@'localhost';
  GRANT REPLICATION SLAVE ON *.* TO 'backup_user'@'localhost';
  GRANT EVENT ON *.* TO 'backup_user'@'localhost';
  FLUSH PRIVILEGES;

  # /etc/mysql/mysql.conf.d/mysqld.cnf に追加:
  [mysqld]
  log_bin            = /var/lib/mysql/mysql-bin
  binlog_format      = ROW
  expire_logs_days   = 7
  max_binlog_size    = 100M
  server_id          = 1

SQL
}
