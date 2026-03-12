#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/docker-compose.prod.yml"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env.prod}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-hfi-prod}"

DISK_USAGE_WARN_PCT="${DISK_USAGE_WARN_PCT:-85}"
MEMORY_AVAILABLE_WARN_MB="${MEMORY_AVAILABLE_WARN_MB:-200}"

log() {
  printf '[host-health] %s\n' "$*"
}

warn() {
  printf '[host-health] WARNING: %s\n' "$*" >&2
}

fail() {
  printf '[host-health] ERROR: %s\n' "$*" >&2
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

compose() {
  REPO_ROOT="$REPO_ROOT" \
  ENV_FILE_PATH="$ENV_FILE" \
  APP_VERSION="${APP_VERSION:-health-check}" \
  docker compose \
    --project-name "$PROJECT_NAME" \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    "$@"
}

check_disk_usage() {
  local target disk_pct
  target="${HOST_DATA_DIR:-/opt/hfi/data}"
  disk_pct="$(df -P "$target" | awk 'NR==2 {gsub("%", "", $5); print $5}')"

  if [[ -z "$disk_pct" ]]; then
    warn "Could not determine disk usage for ${target}"
    return 1
  fi

  if (( disk_pct >= DISK_USAGE_WARN_PCT )); then
    warn "Disk usage is ${disk_pct}% on ${target} (threshold ${DISK_USAGE_WARN_PCT}%)"
    return 1
  fi

  log "Disk usage OK: ${disk_pct}% on ${target}"
  return 0
}

check_memory() {
  if [[ ! -r /proc/meminfo ]]; then
    warn "Cannot read /proc/meminfo; skipping memory check"
    return 1
  fi

  local mem_available_kb mem_available_mb
  mem_available_kb="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
  mem_available_mb=$((mem_available_kb / 1024))

  if (( mem_available_mb <= MEMORY_AVAILABLE_WARN_MB )); then
    warn "Available memory is ${mem_available_mb}MB (threshold ${MEMORY_AVAILABLE_WARN_MB}MB)"
    return 1
  fi

  log "Memory OK: ${mem_available_mb}MB available"
  return 0
}

check_services() {
  local expected service running
  expected=(proxy api frontend processor telegram-bot)
  running="$(compose ps --status running --services || true)"

  local ok=0
  for service in "${expected[@]}"; do
    if grep -qx "$service" <<<"$running"; then
      log "Service running: ${service}"
    else
      warn "Service not running: ${service}"
      ok=1
    fi
  done

  return "$ok"
}

main() {
  require_bin docker
  require_bin df
  [[ -f "$COMPOSE_FILE" ]] || fail "Compose file not found: ${COMPOSE_FILE}"
  [[ -f "$ENV_FILE" ]] || fail "Environment file not found: ${ENV_FILE}"
  load_env_file

  local exit_code=0

  check_disk_usage || exit_code=1
  check_memory || exit_code=1
  check_services || exit_code=1

  if (( exit_code == 0 )); then
    log "Host checks passed"
  else
    warn "Host checks reported issues"
  fi

  exit "$exit_code"
}

main "$@"
