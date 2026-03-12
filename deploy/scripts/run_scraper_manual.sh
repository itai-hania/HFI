#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/docker-compose.prod.yml"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env.prod}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-hfi-prod}"
STATE_DIR="${STATE_DIR_OVERRIDE:-${REPO_ROOT}/deploy/state}"

log() {
  printf '[scraper] %s\n' "$*"
}

fail() {
  printf '[scraper] ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -f "$COMPOSE_FILE" ]] || fail "Compose file not found: ${COMPOSE_FILE}"
[[ -f "$ENV_FILE" ]] || fail "Environment file not found: ${ENV_FILE}"

if [[ -z "${APP_VERSION:-}" ]]; then
  if [[ -f "${STATE_DIR}/current_successful_sha" ]]; then
    APP_VERSION="$(tr -d '[:space:]' < "${STATE_DIR}/current_successful_sha")"
  else
    APP_VERSION="$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD 2>/dev/null || date -u +%Y%m%d%H%M%S)"
  fi
fi
export APP_VERSION

if [[ $# -eq 0 ]]; then
  set -- python -m scraper.main
fi

log "Running scraper manually: $*"
REPO_ROOT="$REPO_ROOT" \
ENV_FILE_PATH="$ENV_FILE" \
APP_VERSION="$APP_VERSION" \
docker compose \
  --project-name "$PROJECT_NAME" \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  --profile manual \
  run --rm scraper "$@"
