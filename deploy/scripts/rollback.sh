#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env.prod}"
STATE_DIR="${STATE_DIR_OVERRIDE:-${REPO_ROOT}/deploy/state}"
TARGET_SHA="${1:-}"

log() {
  printf '[rollback] %s\n' "$*"
}

fail() {
  printf '[rollback] ERROR: %s\n' "$*" >&2
  exit 1
}

require_bin() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

resolve_target_sha() {
  if [[ -n "$TARGET_SHA" ]]; then
    printf '%s\n' "$TARGET_SHA"
    return
  fi

  local previous_sha_file
  previous_sha_file="${STATE_DIR}/previous_successful_sha"

  [[ -f "$previous_sha_file" ]] || fail "No rollback target provided and ${previous_sha_file} was not found"

  TARGET_SHA="$(tr -d '[:space:]' < "$previous_sha_file")"
  [[ -n "$TARGET_SHA" ]] || fail "Rollback target in ${previous_sha_file} is empty"
  printf '%s\n' "$TARGET_SHA"
}

main() {
  require_bin git
  require_bin docker

  [[ -f "$ENV_FILE" ]] || fail "Environment file not found: ${ENV_FILE}"

  local target
  target="$(resolve_target_sha)"

  if ! git -C "$REPO_ROOT" cat-file -e "${target}^{commit}" 2>/dev/null; then
    log "Fetching remote refs to locate ${target}"
    git -C "$REPO_ROOT" fetch --all --prune
  fi

  git -C "$REPO_ROOT" cat-file -e "${target}^{commit}" 2>/dev/null || fail "Commit not found: ${target}"

  local tmp_worktree
  tmp_worktree="$(mktemp -d "${TMPDIR:-/tmp}/hfi-rollback.XXXXXX")"

  cleanup() {
    git -C "$REPO_ROOT" worktree remove --force "$tmp_worktree" >/dev/null 2>&1 || rm -rf "$tmp_worktree"
  }
  trap cleanup EXIT

  git -C "$REPO_ROOT" worktree add --detach "$tmp_worktree" "$target" >/dev/null

  log "Deploying rollback target ${target}"
  STATE_DIR_OVERRIDE="$STATE_DIR" \
  ENV_FILE="$ENV_FILE" \
  APP_VERSION="$target" \
  CLEANUP_OLD_IMAGES=0 \
  bash "$tmp_worktree/deploy/scripts/deploy.sh"

  log "Rollback completed: ${target}"
}

main "$@"
