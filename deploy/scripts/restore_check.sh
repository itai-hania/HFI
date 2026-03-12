#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/docker-compose.prod.yml"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env.prod}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-hfi-prod}"
BACKUP_FILE="${1:-}"

log() {
  printf '[restore-check] %s\n' "$*"
}

fail() {
  printf '[restore-check] ERROR: %s\n' "$*" >&2
  exit 1
}

require_bin() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

load_env_file() {
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

resolve_backup_file() {
  if [[ -n "$BACKUP_FILE" ]]; then
    [[ -f "$BACKUP_FILE" ]] || fail "Backup file not found: ${BACKUP_FILE}"
    printf '%s\n' "$BACKUP_FILE"
    return
  fi

  local data_dir backup_dir latest
  data_dir="${HOST_DATA_DIR:-/opt/hfi/data}"
  backup_dir="${BACKUP_DIR:-${data_dir}/backups}"

  latest="$(ls -1t "${backup_dir}"/hfi-db-*.sqlite3.gz 2>/dev/null | head -n 1 || true)"
  [[ -n "$latest" ]] || fail "No backup files found under ${backup_dir}"

  printf '%s\n' "$latest"
}

main() {
  require_bin python3
  require_bin gunzip
  require_bin docker

  [[ -f "$COMPOSE_FILE" ]] || fail "Compose file not found: ${COMPOSE_FILE}"
  [[ -f "$ENV_FILE" ]] || fail "Environment file not found: ${ENV_FILE}"
  load_env_file

  local chosen_backup tmp_dir restored_db
  chosen_backup="$(resolve_backup_file)"
  tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/hfi-restore-check.XXXXXX")"
  restored_db="${tmp_dir}/restored.db"

  trap 'rm -rf "$tmp_dir"' EXIT

  gunzip -c "$chosen_backup" > "$restored_db"
  log "Restored backup into temporary DB: ${restored_db}"

  python3 - "$restored_db" <<'PY'
import sqlite3
import sys

path = sys.argv[1]
required_tables = {"tweets", "trends", "threads"}

conn = sqlite3.connect(path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = {row[0] for row in cur.fetchall()}
missing = required_tables - tables
if missing:
    raise SystemExit(f"Missing required tables: {sorted(missing)}")

cur.execute("SELECT COUNT(*) FROM tweets")
tweet_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM trends")
trend_count = cur.fetchone()[0]

print(f"restore_ok tweets={tweet_count} trends={trend_count}")
conn.close()
PY

  REPO_ROOT="$REPO_ROOT" \
  ENV_FILE_PATH="$ENV_FILE" \
  APP_VERSION="${APP_VERSION:-restore-check}" \
  docker compose \
    --project-name "$PROJECT_NAME" \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    run --rm \
    -e DATABASE_URL=sqlite:////restore/restored.db \
    -v "${tmp_dir}:/restore:ro" \
    api \
    python -c "from common.models import health_check; data = health_check(); assert data.get('status') == 'healthy'; print(data)"

  log "Restore validation completed successfully using ${chosen_backup}"
}

main "$@"
