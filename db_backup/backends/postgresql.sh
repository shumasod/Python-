#!/usr/bin/env bash
# ============================================================
# PostgreSQL バックアップバックエンド
#
# フルバックアップ:
#   - pg_dump (単一DB, custom/plain/directory/tar 形式)
#   - pg_dumpall (全DB, plain SQL)
#   - pg_basebackup (物理バックアップ、WAL ストリーミング)
#
# 差分バックアップ:
#   - WAL ファイルのコピー/アーカイブ
#   - pg_receivewal によるリアルタイム WAL ストリーミング
#
# PITR (ポイントインタイムリカバリ):
#   - pg_restore / psql でフルリストア後、WAL を適用
# ============================================================

# ─── フルバックアップ ─────────────────────────────────────────
db_full_backup() {
    local backup_dir="$1" ts="$2"
    pg_env

    if [[ -z "${PG_DATABASE:-}" ]]; then
        _pg_dumpall "${backup_dir}" "${ts}"
    else
        _pg_dump_single "${backup_dir}" "${ts}"
    fi

    # pg_basebackup (PG_WAL_DIR が設定されている場合のみ)
    if [[ -n "${PG_WAL_DIR}" ]]; then
        _pg_basebackup "${backup_dir}" "${ts}"
    fi

    _pg_save_meta "${backup_dir}/${ts}.meta"
}

_pg_dumpall() {
    local backup_dir="$1" ts="$2"
    local out_file="${backup_dir}/all_databases_${ts}.sql"
    log_info "全DBダンプ (pg_dumpall) → ${out_file}"
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_info "[DRY-RUN] pg_dumpall > ${out_file}"
        return 0
    fi
    # shellcheck disable=SC2086
    pg_dumpall -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
        ${PG_DUMP_OPTS} > "${out_file}" 2>> "${LOG_FILE}"
    log_info "ダンプ完了: $(du -sh "${out_file}" | cut -f1)"
    compress_file "${out_file}"
}

_pg_dump_single() {
    local backup_dir="$1" ts="$2"

    local ext
    case "${PG_DUMP_FORMAT}" in
        custom)    ext="dump" ;;
        directory) ext="dir"  ;;
        tar)       ext="tar"  ;;
        *)         ext="sql"  ;;
    esac

    local out_file="${backup_dir}/${PG_DATABASE}_${ts}.${ext}"
    log_info "DBダンプ (pg_dump -F${PG_DUMP_FORMAT:0:1}): ${PG_DATABASE} → ${out_file}"
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_info "[DRY-RUN] pg_dump -F ${PG_DUMP_FORMAT} ${PG_DATABASE}"
        return 0
    fi

    if [[ "${PG_DUMP_FORMAT}" == "directory" ]]; then
        # shellcheck disable=SC2086
        pg_dump -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
            ${PG_DUMP_OPTS} -F d -f "${out_file}" "${PG_DATABASE}" 2>> "${LOG_FILE}"
    else
        # shellcheck disable=SC2086
        pg_dump -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
            ${PG_DUMP_OPTS} -F "${PG_DUMP_FORMAT:0:1}" \
            "${PG_DATABASE}" > "${out_file}" 2>> "${LOG_FILE}"
        [[ "${PG_DUMP_FORMAT}" == "plain" ]] && compress_file "${out_file}"
    fi

    log_info "ダンプ完了: $(du -sh "${out_file}" | cut -f1)"
}

_pg_basebackup() {
    local backup_dir="$1" ts="$2"
    local base_dir="${backup_dir}/base_${ts}"
    log_info "pg_basebackup → ${base_dir}"
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_info "[DRY-RUN] pg_basebackup -D ${base_dir}"
        return 0
    fi
    # shellcheck disable=SC2086
    pg_basebackup -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
        ${PG_BASEBACKUP_OPTS} -D "${base_dir}" 2>> "${LOG_FILE}"
    log_info "pg_basebackup 完了: $(du -sh "${base_dir}" | cut -f1)"
}

_pg_save_meta() {
    local meta_file="$1"
    {
        echo "# PostgreSQL バックアップメタ情報"
        echo "# 生成日時: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "# ホスト: $(hostname)"
        echo ""
        psql -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" -Atc \
            "SELECT 'WAL_LSN=' || pg_current_wal_lsn() || chr(10) ||
                    'WAL_FILE=' || pg_walfile_name(pg_current_wal_lsn());" \
            2>/dev/null || true
    } > "${meta_file}"
    log_info "メタ情報を保存: ${meta_file}"
}

# ─── 差分バックアップ (WAL アーカイブ) ───────────────────────
db_incremental_backup() {
    if [[ -z "${PG_WAL_DIR}" ]]; then
        log_warn "PG_WAL_DIR が未設定。WAL バックアップをスキップします。"
        log_warn "  postgresql.conf の archive_command でアーカイブするか、PG_WAL_DIR を設定してください。"
        return 0
    fi

    pg_env
    log_info "WAL アーカイブ取得開始 → ${PG_WAL_DIR}"

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_info "[DRY-RUN] WAL ファイルをコピー + pg_switch_wal()"
        return 0
    fi

    # WAL セグメントをスイッチして完成した WAL ファイルを生成
    psql -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
        -c "SELECT pg_switch_wal();" 2>> "${LOG_FILE}" || true

    # pg_data_dir/pg_wal 配下の完了済み WAL をコピー
    if [[ -n "${PG_DATA_DIR}" && -d "${PG_DATA_DIR}/pg_wal" ]]; then
        _pg_copy_wal_files
    fi

    # pg_receivewal が設定されていれば起動確認
    _pg_ensure_receivewal

    purge_old_files "${PG_WAL_DIR}" "${INCREMENTAL_RETENTION_DAYS}" "*.gz"
    log_info "WAL アーカイブ完了"
}

_pg_copy_wal_files() {
    local copied=0
    while IFS= read -r wal_file; do
        local dst="${PG_WAL_DIR}/$(basename "${wal_file}").gz"
        [[ -f "${dst}" ]] && continue
        gzip -c"${COMPRESS_LEVEL}" "${wal_file}" > "${dst}"
        (( copied++ ))
    done < <(find "${PG_DATA_DIR}/pg_wal" -maxdepth 1 -type f \
                  -not -name "*.partial" -not -name "archive_status" | sort)
    log_info "WAL ファイルコピー: ${copied} ファイル"
}

_pg_ensure_receivewal() {
    # pg_receivewal がインストールされていて、かつ未起動の場合のみ起動
    command -v pg_receivewal &>/dev/null || return 0
    pgrep -f "pg_receivewal.*${PG_WAL_DIR}" &>/dev/null && return 0

    log_info "pg_receivewal をバックグラウンドで起動..."
    pg_receivewal -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
        --directory="${PG_WAL_DIR}" \
        --create-slot --slot="backup_receivewal" \
        >> "${LOG_FILE}" 2>&1 &
    log_info "pg_receivewal 起動 (PID=$!)"
}

# ─── リストア ─────────────────────────────────────────────────
db_restore_full() {
    local dump_file="$1"
    pg_env
    log_info "フルリストア: ${dump_file}"

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_info "[DRY-RUN] pg_restore / psql < ${dump_file}"
        return 0
    fi

    if [[ "${dump_file}" == *.dump ]]; then
        # custom 形式 → pg_restore
        local db="${PG_DATABASE:-postgres}"
        pg_restore --no-password -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
            -d "${db}" "${dump_file}" 2>> "${LOG_FILE}"

    elif [[ "${dump_file}" == *.sql.gz ]]; then
        zcat "${dump_file}" | psql --no-password \
            -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" 2>> "${LOG_FILE}"

    elif [[ "${dump_file}" == *.sql ]]; then
        psql --no-password -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
            < "${dump_file}" 2>> "${LOG_FILE}"

    elif [[ "${dump_file}" == *.tar ]]; then
        local db="${PG_DATABASE:-postgres}"
        pg_restore --no-password -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
            -d "${db}" -Ft "${dump_file}" 2>> "${LOG_FILE}"

    elif [[ -d "${dump_file}" ]]; then
        # directory 形式 → pg_restore -Fd
        local db="${PG_DATABASE:-postgres}"
        pg_restore --no-password -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
            -d "${db}" -Fd "${dump_file}" 2>> "${LOG_FILE}"

    else
        log_error "不明なバックアップ形式: ${dump_file}"
        return 1
    fi

    log_info "フルリストア完了"
}

db_restore_incremental() {
    local wal_dir="$1" stop_datetime="${2:-}" start_datetime="${3:-}" target_db="${4:-}"
    pg_env

    log_info "PostgreSQL PITR 設定を適用します"
    log_warn "!!! PostgreSQL を停止してから実行してください !!!"

    cat <<EOF

  # postgresql.conf に以下を追記 (または postgresql.auto.conf):
  restore_command = 'gunzip -c ${wal_dir}/%f.gz > %p 2>/dev/null'
  recovery_target_time = '${stop_datetime}'
  recovery_target_action = 'promote'

  # 次に recovery.signal を作成して PostgreSQL を起動:
  touch \${PGDATA}/recovery.signal
  systemctl start postgresql

EOF

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_info "[DRY-RUN] PITR 設定のみ表示"
        return 0
    fi

    if [[ -z "${PG_DATA_DIR}" || ! -d "${PG_DATA_DIR}" ]]; then
        log_warn "PG_DATA_DIR が未設定のため自動設定をスキップ。上記を手動で設定してください。"
        return 0
    fi

    # postgresql.auto.conf に設定を追記 (postgresql.conf より優先される)
    local conf_file="${PG_DATA_DIR}/postgresql.auto.conf"
    cat >> "${conf_file}" <<EOF

# PITR 設定 ($(date '+%Y-%m-%d %H:%M:%S') by db_backup/restore.sh)
restore_command = 'gunzip -c ${wal_dir}/%f.gz > %p 2>/dev/null'
recovery_target_time = '${stop_datetime}'
recovery_target_action = 'promote'
EOF

    touch "${PG_DATA_DIR}/recovery.signal"
    log_info "recovery.signal を作成しました: ${PG_DATA_DIR}/recovery.signal"
    log_info "PostgreSQL を起動するとリカバリが開始されます"
}

# ─── インデックスヘルスチェック ──────────────────────────────

db_check_slow_queries() {
    echo "=== フルスキャン / 非効率クエリ TOP ${TOP_N:-20} ==="
    echo "(pg_stat_statements による実行統計)"
    echo ""

    pg_env

    [[ "${DRY_RUN:-false}" == "true" ]] && {
        echo "[DRY-RUN] pg_stat_statements を参照"
        return 0
    }

    # pg_stat_statements が有効かチェック
    local ext_count
    ext_count=$(psql -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" -Atc \
        "SELECT count(*) FROM pg_extension WHERE extname = 'pg_stat_statements';" \
        2>/dev/null || echo "0")
    if [[ "${ext_count}" == "0" ]]; then
        echo "  ⚠ pg_stat_statements が無効です。以下で有効化してください:"
        echo "    CREATE EXTENSION pg_stat_statements;"
        echo "    # postgresql.conf: shared_preload_libraries = 'pg_stat_statements'"
        return 0
    fi

    psql -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
        --pset="border=2" -c "
SELECT
    LEFT(query, 80)                                      AS query_pattern,
    calls                                                AS exec_count,
    ROUND((total_exec_time / calls)::numeric, 2)         AS avg_latency_ms,
    ROUND((rows / NULLIF(calls, 0))::numeric, 0)         AS avg_rows_returned,
    ROUND((shared_blks_read / NULLIF(calls, 0))::numeric, 0) AS avg_blks_read,
    dbid::text                                           AS db
FROM pg_stat_statements
WHERE calls >= 5
  AND query NOT LIKE '%pg_%'
  AND query NOT LIKE '%information_schema%'
ORDER BY avg_latency_ms DESC
LIMIT ${TOP_N:-20};
" 2>/dev/null || echo "  ⚠ クエリ取得失敗 (権限不足の可能性)"
}

db_check_unused_indexes() {
    echo "=== 未使用インデックス ==="
    echo "(pg_stat_user_indexes による参照ゼロのインデックス)"
    echo ""

    pg_env
    [[ "${DRY_RUN:-false}" == "true" ]] && {
        echo "[DRY-RUN] pg_stat_user_indexes を参照"
        return 0
    }

    psql -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
        --pset="border=2" -c "
SELECT
    schemaname                   AS schema_name,
    relname                      AS table_name,
    indexrelname                 AS index_name,
    idx_scan                     AS scan_count,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT ${TOP_N:-20};
" 2>/dev/null || echo "  ⚠ 未使用インデックス取得失敗"
}

db_check_duplicate_indexes() {
    echo "=== 重複インデックス候補 ==="
    echo "(pg_indexes による同一テーブルの類似インデックス)"
    echo ""

    pg_env
    [[ "${DRY_RUN:-false}" == "true" ]] && {
        echo "[DRY-RUN] pg_indexes を参照"
        return 0
    }

    psql -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
        --pset="border=2" -c "
SELECT
    ix1.schemaname    AS schema_name,
    ix1.tablename     AS table_name,
    ix1.indexname     AS index_1,
    ix2.indexname     AS index_2,
    ix1.indexdef      AS index_1_def
FROM pg_indexes ix1
JOIN pg_indexes ix2
  ON  ix1.tablename  = ix2.tablename
  AND ix1.schemaname = ix2.schemaname
  AND ix1.indexname  < ix2.indexname
  AND ix1.indexdef   LIKE ix2.indexdef || '%'
WHERE ix1.schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY ix1.tablename
LIMIT ${TOP_N:-20};
" 2>/dev/null || echo "  ⚠ 重複インデックス取得失敗"
}

# ─── セットアップ案内 ─────────────────────────────────────────
db_setup_instructions() {
    cat <<'SQL'

  -- psql に接続して以下を実行してください:
  CREATE USER backup_user WITH PASSWORD 'strong_password_here' REPLICATION;

  -- 全DBアクセス (pg_dumpall 用):
  -- ※ pg_hba.conf で backup_user を trust または md5 で許可してください

  -- 特定DBのみ (pg_dump 用):
  GRANT CONNECT ON DATABASE your_db TO backup_user;
  GRANT USAGE ON SCHEMA public TO backup_user;
  GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_user;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public
      GRANT SELECT ON TABLES TO backup_user;

  # ~/.pgpass を作成 (chmod 600):
  #   127.0.0.1:5432:*:backup_user:strong_password_here

  # postgresql.conf に追加 (WAL アーカイブ用):
  wal_level                = replica
  archive_mode             = on
  archive_command          = 'gzip -c %p > /var/backup/db/wal/%f.gz'
  max_wal_senders          = 3
  wal_keep_size            = 1GB

  # pg_hba.conf に追加 (レプリケーション接続用):
  #   host  replication  backup_user  127.0.0.1/32  md5

SQL
}
