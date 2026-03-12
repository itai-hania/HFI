#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/docker-compose.prod.yml"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env.prod}"
STATE_DIR="${STATE_DIR_OVERRIDE:-${REPO_ROOT}/deploy/state}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-hfi-prod}"

log() {
  printf '[deploy] %s\n' "$*"
}

fail() {
  printf '[deploy] ERROR: %s\n' "$*" >&2
  exit 1
}

require_bin() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

validate_env_permissions() {
  local perms
  if perms="$(stat -c '%a' "$ENV_FILE" 2>/dev/null)"; then
    if [[ "$perms" != "600" ]]; then
      fail "${ENV_FILE} must have permissions 600 (current: ${perms})"
    fi
    return
  fi

  if perms="$(stat -f '%Lp' "$ENV_FILE" 2>/dev/null)"; then
    if [[ "$perms" != "600" ]]; then
      fail "${ENV_FILE} must have permissions 600 (current: ${perms})"
    fi
  fi
}

load_env_file() {
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

require_env_keys() {
  local missing=()
  local key
  for key in "$@"; do
    if [[ -z "${!key:-}" ]]; then
      missing+=("$key")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    fail "Missing required environment variables in ${ENV_FILE}: ${missing[*]}"
  fi
}

compose() {
  REPO_ROOT="$REPO_ROOT" \
  ENV_FILE_PATH="$ENV_FILE" \
  APP_VERSION="$APP_VERSION" \
  docker compose \
    --project-name "$PROJECT_NAME" \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    "$@"
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local max_attempts="${3:-60}"
  local sleep_seconds="${4:-2}"
  local attempt=1

  while (( attempt <= max_attempts )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "Ready: ${label}"
      return 0
    fi
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done

  fail "Timed out waiting for ${label} (${url})"
}

fetch_api_health_payload() {
  compose exec -T api \
    python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read().decode())"
}

validate_api_health() {
  local payload
  payload="$(fetch_api_health_payload)"

  python3 - "$payload" "$APP_VERSION" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
expected_version = sys.argv[2]

status = payload.get("status")
if status != "healthy":
    raise SystemExit(f"API health status is not healthy: {status!r}")

build_version = payload.get("build_version")
if build_version != expected_version:
    raise SystemExit(
        f"build_version mismatch: got {build_version!r}, expected {expected_version!r}"
    )
PY
}

wait_for_api_health() {
  local max_attempts="${1:-60}"
  local sleep_seconds="${2:-2}"
  local attempt=1

  while (( attempt <= max_attempts )); do
    if validate_api_health >/dev/null 2>&1; then
      log "Ready: API service health"
      return 0
    fi
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done

  fail "Timed out waiting for API service health"
}

check_telegram_bot_running() {
  local max_attempts="${1:-45}"
  local sleep_seconds="${2:-2}"
  local attempt=1
  local running_services

  while (( attempt <= max_attempts )); do
    running_services="$(compose ps --status running --services || true)"
    if grep -qx "telegram-bot" <<<"$running_services"; then
      log "Ready: telegram-bot running"
      return 0
    fi
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done

  compose logs --tail 120 telegram-bot || true
  fail "telegram-bot is not running"
}

main() {
  require_bin docker
  require_bin curl
  require_bin python3

  [[ -f "$COMPOSE_FILE" ]] || fail "Compose file not found: ${COMPOSE_FILE}"
  [[ -f "$ENV_FILE" ]] || fail "Environment file not found: ${ENV_FILE}"

  validate_env_permissions
  load_env_file
  require_env_keys \
    ENVIRONMENT \
    DASHBOARD_PASSWORD \
    JWT_SECRET \
    OPENAI_API_KEY \
    TELEGRAM_BOT_TOKEN \
    TELEGRAM_CHAT_ID \
    API_BASE_URL \
    FRONTEND_BASE_URL \
    CORS_ORIGINS

  if [[ "${ENVIRONMENT}" != "production" ]]; then
    fail "ENVIRONMENT must be set to production in ${ENV_FILE}"
  fi

  if [[ -z "${APP_VERSION:-}" ]]; then
    APP_VERSION="$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD 2>/dev/null || date -u +%Y%m%d%H%M%S)"
  fi
  export APP_VERSION

  mkdir -p "$STATE_DIR"
  mkdir -p "${HOST_DATA_DIR:-/opt/hfi/data}"

  local current_sha_file previous_sha_file release_history_file
  current_sha_file="${STATE_DIR}/current_successful_sha"
  previous_sha_file="${STATE_DIR}/previous_successful_sha"
  release_history_file="${STATE_DIR}/release_history.log"

  if [[ -f "$current_sha_file" ]]; then
    cp "$current_sha_file" "$previous_sha_file"
  fi

  log "Deploying build ${APP_VERSION}"
  compose up -d --build --remove-orphans

  # Reload proxy so Caddyfile updates are always picked up across deploys.
  compose up -d --no-deps --force-recreate proxy

  wait_for_http "http://127.0.0.1/" "frontend via proxy"
  wait_for_api_health
  check_telegram_bot_running

  printf '%s\n' "$APP_VERSION" > "$current_sha_file"
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$APP_VERSION" >> "$release_history_file"

  if [[ "${CLEANUP_OLD_IMAGES:-1}" == "1" ]]; then
    docker image prune -f --filter "until=168h" >/dev/null 2>&1 || true
  fi

  log "Deployment completed successfully"
}

main "$@"
