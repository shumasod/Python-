#!/usr/bin/env bash
# ============================================================
# MariaDB バックアップバックエンド
# MySQL バックエンドを継承し、MariaDB 固有の差分を上書き
#
# 継承する関数 (mysql.sh から):
#   db_incremental_backup, db_restore_full, db_restore_incremental
#   db_check_slow_queries, db_check_unused_indexes, db_check_duplicate_indexes
# ============================================================

# MySQL バックエンドを継承
source "${SCRIPT_DIR}/backends/mysql.sh"

# ─── コマンド選択 (mariadb-dump / mariadb 優先) ───────────────
_mysql_dump_cmd() {
    command -v mariadb-dump &>/dev/null && echo "mariadb-dump" && return
    command -v mysqldump    &>/dev/null && echo "mysqldump"    && return
    echo "mysqldump"
}

_mariadb_client_cmd() {
    command -v mariadb &>/dev/null && echo "mariadb" && return
    echo "mysql"
}

# ─── フルバックアップ (mariadb-dump 優先) ─────────────────────
db_full_backup() {
    local backup_dir="$1" ts="$2"
    local dump_cmd; dump_cmd=$(_mysql_dump_cmd)
    log_info "使用ダンプコマンド: ${dump_cmd}"

    if [[ -z "${MYSQL_TARGET_DBS:-}" ]]; then
        local out_file="${backup_dir}/all_databases_${ts}.sql"
        log_info "全DBダンプ → ${out_file}"
        if [[ "${DRY_RUN:-false}" == "true" ]]; then
            log_info "[DRY-RUN] ${dump_cmd} --all-databases"
        else
            # shellcheck disable=SC2046,SC2086
            "${dump_cmd}" $(mysql_opts) ${MYSQLDUMP_OPTS} --all-databases \
                > "${out_file}" 2>> "${LOG_FILE}"
            log_info "ダンプ完了: $(du -sh "${out_file}" | cut -f1)"
        fi
    else
        for db in ${MYSQL_TARGET_DBS}; do
            local out_file="${backup_dir}/${db}_${ts}.sql"
            log_info "DBダンプ: ${db} → ${out_file}"
            if [[ "${DRY_RUN:-false}" == "true" ]]; then
                log_info "[DRY-RUN] ${dump_cmd} ${db}"
            else
                # shellcheck disable=SC2046,SC2086
                "${dump_cmd}" $(mysql_opts) ${MYSQLDUMP_OPTS} "${db}" \
                    > "${out_file}" 2>> "${LOG_FILE}"
                log_info "ダンプ完了: $(du -sh "${out_file}" | cut -f1)"
            fi
        done
    fi

    _mysql_save_binlog_position "${backup_dir}/${ts}.meta"

    if [[ "${COMPRESS}" == "true" ]]; then
        find "${backup_dir}" -name "*.sql" -type f | while read -r f; do
            compress_file "${f}"
        done
    fi
}

# ─── セットアップ案内 ─────────────────────────────────────────
db_setup_instructions() {
    cat <<'SQL'

  -- MariaDB に root で接続して以下を実行してください:
  CREATE USER IF NOT EXISTS 'backup_user'@'localhost'
      IDENTIFIED BY 'strong_password_here';

  GRANT SELECT, SHOW VIEW, TRIGGER, LOCK TABLES,
        PROCESS, RELOAD, REPLICATION CLIENT ON *.*
        TO 'backup_user'@'localhost';
  GRANT REPLICATION SLAVE ON *.* TO 'backup_user'@'localhost';
  GRANT EVENT ON *.* TO 'backup_user'@'localhost';

  -- MariaDB 10.5+ では BINLOG MONITOR 権限が必要:
  -- GRANT BINLOG MONITOR ON *.* TO 'backup_user'@'localhost';

  FLUSH PRIVILEGES;

  # /etc/mysql/mariadb.conf.d/50-server.cnf に追加:
  [mysqld]
  log_bin            = /var/lib/mysql/mysql-bin
  binlog_format      = ROW
  expire_logs_days   = 7
  max_binlog_size    = 100M
  server_id          = 1

SQL
}
