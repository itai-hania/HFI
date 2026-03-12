#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env.prod}"

log() {
  printf '[backup] %s\n' "$*"
}

fail() {
  printf '[backup] ERROR: %s\n' "$*" >&2
  exit 1
}

require_bin() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

load_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
}

delete_old_blob_backups() {
  local retention_days="$1"
  local auth_args=(--account-name "$AZURE_STORAGE_ACCOUNT")

  if [[ -n "${AZURE_STORAGE_SAS_TOKEN:-}" ]]; then
    auth_args+=(--sas-token "$AZURE_STORAGE_SAS_TOKEN")
  else
    auth_args+=(--auth-mode login)
  fi

  local list_file
  list_file="$(mktemp)"
  az storage blob list \
    "${auth_args[@]}" \
    --container-name "$AZURE_STORAGE_CONTAINER" \
    --prefix "hfi-db-" \
    --num-results "*" \
    -o json > "$list_file"

  while IFS= read -r blob_name; do
    [[ -n "$blob_name" ]] || continue
    az storage blob delete \
      "${auth_args[@]}" \
      --container-name "$AZURE_STORAGE_CONTAINER" \
      --name "$blob_name" >/dev/null
    log "Deleted expired blob backup: ${blob_name}"
  done < <(
    python3 - "$list_file" "$retention_days" <<'PY'
import datetime as dt
import json
import sys

items_path = sys.argv[1]
retention_days = int(sys.argv[2])
cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=retention_days)

with open(items_path, "r", encoding="utf-8") as handle:
    items = json.load(handle)

for item in items:
    name = item.get("name")
    modified = item.get("properties", {}).get("lastModified")
    if not name or not modified:
      continue
    last_modified = dt.datetime.fromisoformat(modified.replace("Z", "+00:00"))
    if last_modified < cutoff:
      print(name)
PY
  )

  rm -f "$list_file"
}

main() {
  require_bin python3
  require_bin gzip
  load_env_file

  local data_dir db_path backup_dir retention_days
  data_dir="${HOST_DATA_DIR:-/opt/hfi/data}"
  db_path="${DB_PATH:-${data_dir}/hfi.db}"
  backup_dir="${BACKUP_DIR:-${data_dir}/backups}"
  retention_days="${BACKUP_RETENTION_DAYS:-30}"

  [[ -f "$db_path" ]] || fail "Database file not found: ${db_path}"

  mkdir -p "$backup_dir"

  local timestamp raw_backup gz_backup
  timestamp="$(date -u +%Y%m%d-%H%M%S)"
  raw_backup="${backup_dir}/hfi-db-${timestamp}.sqlite3"
  gz_backup="${raw_backup}.gz"

  python3 - "$db_path" "$raw_backup" <<'PY'
import sqlite3
import sys

source_db = sys.argv[1]
backup_db = sys.argv[2]

src = sqlite3.connect(source_db)
dst = sqlite3.connect(backup_db)
with dst:
    src.backup(dst)
src.close()
dst.close()
PY

  gzip -f "$raw_backup"
  log "Created local backup: ${gz_backup}"

  find "$backup_dir" -type f -name 'hfi-db-*.sqlite3.gz' -mtime "+${retention_days}" -delete

  if [[ -n "${AZURE_STORAGE_ACCOUNT:-}" && -n "${AZURE_STORAGE_CONTAINER:-}" ]]; then
    require_bin az

    local auth_args=(--account-name "$AZURE_STORAGE_ACCOUNT")
    if [[ -n "${AZURE_STORAGE_SAS_TOKEN:-}" ]]; then
      auth_args+=(--sas-token "$AZURE_STORAGE_SAS_TOKEN")
    else
      auth_args+=(--auth-mode login)
    fi

    az storage blob upload \
      "${auth_args[@]}" \
      --container-name "$AZURE_STORAGE_CONTAINER" \
      --name "$(basename "$gz_backup")" \
      --file "$gz_backup" \
      --overwrite true >/dev/null

    log "Uploaded backup to Azure Blob: $(basename "$gz_backup")"

    if [[ "${AZURE_BLOB_RETENTION_DAYS:-0}" =~ ^[0-9]+$ ]] && (( AZURE_BLOB_RETENTION_DAYS > 0 )); then
      delete_old_blob_backups "$AZURE_BLOB_RETENTION_DAYS"
    fi
  else
    log "Azure Blob upload skipped (AZURE_STORAGE_ACCOUNT/AZURE_STORAGE_CONTAINER not set)"
  fi
}

main "$@"
