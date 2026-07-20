#!/usr/bin/env bash
# ============================================================
# バックアップ一覧表示スクリプト
# 使用方法: DB_TYPE=mysql ./list_backups.sh [--full] [--incremental] [--json]
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/lib.sh"

show_full=true
show_incremental=true
output_json=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --full)          show_incremental=false ;;
        --incremental)   show_full=false ;;
        --json)          output_json=true ;;
        -h|--help)
            echo "使用方法: $0 [--full] [--incremental] [--json]"
            exit 0
            ;;
        *) echo "不明なオプション: $1"; exit 1 ;;
    esac
    shift
done

# ファイル情報を収集する関数
list_dir() {
    local dir="$1" label="$2"
    [[ ! -d "${dir}" ]] && return
    find "${dir}" \( -name "*.sql" -o -name "*.sql.gz" -o -name "*.dump" -o -name "*.bin.gz" \) -type f | sort | \
    while IFS= read -r f; do
        local fname; fname=$(basename "${f}")
        local size; size=$(du -sh "${f}" 2>/dev/null | cut -f1)
        local mtime; mtime=$(stat -c '%Y' "${f}" 2>/dev/null || stat -f '%m' "${f}" 2>/dev/null)
        local mtime_str; mtime_str=$(date -d "@${mtime}" '+%Y-%m-%d %H:%M' 2>/dev/null \
                           || date -r "${mtime}" '+%Y-%m-%d %H:%M' 2>/dev/null \
                           || echo "unknown")
        local age_days=$(( ( $(date +%s) - mtime ) / 86400 ))
        if [[ "${output_json}" == "true" ]]; then
            printf '{"type":"%s","file":"%s","size":"%s","modified":"%s","age_days":%d}\n' \
                "${label}" "${fname}" "${size}" "${mtime_str}" "${age_days}"
        else
            printf "  %-12s %-50s %6s  %s  (%d日前)\n" \
                "[${label}]" "${fname}" "${size}" "${mtime_str}" "${age_days}"
        fi
    done
}

if [[ "${output_json}" == "true" ]]; then
    echo "["
    first=true
    {
        [[ "${show_full}" == "true" ]] && list_dir "${FULL_BACKUP_DIR:-${BACKUP_BASE_DIR}/full}" "full"
        [[ "${show_incremental}" == "true" ]] && list_dir "${INCREMENTAL_BACKUP_DIR}" "incremental"
    } | while IFS= read -r line; do
        if [[ "${first}" == "true" ]]; then
            printf '%s' "${line}"; first=false
        else
            printf ',\n%s' "${line}"
        fi
    done
    echo ""
    echo "]"
else
    echo "============================================================"
    echo " バックアップ一覧  (DB_TYPE=${DB_TYPE:-未設定})"
    echo "============================================================"
    printf "  %-12s %-50s %6s  %-16s\n" "種別" "ファイル名" "サイズ" "更新日時"
    echo "  --------------------------------------------------------------------"
    [[ "${show_full}" == "true" ]] && list_dir "${FULL_BACKUP_DIR:-${BACKUP_BASE_DIR}/full}" "full"
    [[ "${show_incremental}" == "true" ]] && list_dir "${INCREMENTAL_BACKUP_DIR}" "incremental"
    echo "============================================================"
fi
