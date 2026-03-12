#!/usr/bin/env python3
"""Create shared env files and symlink the current worktree to them."""

from __future__ import annotations

import argparse
import filecmp
import secrets
import sys
import re
from pathlib import Path

ENV_KEY_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
DEFAULT_SHARED_DIR = Path.home() / ".config" / "hfi"


def parse_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ENV_KEY_RE.match(stripped)
        if match and match.group(1) not in values:
            values[match.group(1)] = match.group(2)
    return values


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def ensure_text_ends_with_newline(text: str) -> str:
    return text if not text or text.endswith("\n") else f"{text}\n"


def append_missing_values(path: Path, additions: list[tuple[str, str]]) -> None:
    if not additions:
        return

    original = ensure_text_ends_with_newline(read_text(path))
    lines = []
    if original:
        lines.append(original.rstrip("\n"))
        lines.append("")
    lines.append("# Added by tools/bootstrap_worktree_env.py to complete local runtime config")
    lines.extend(f"{key}={value}" for key, value in additions)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_shared_file(shared_path: Path, worktree_path: Path, fallback_text: str) -> str:
    shared_path.parent.mkdir(parents=True, exist_ok=True)

    if shared_path.exists():
        return "existing-shared"

    if worktree_path.is_symlink():
        worktree_path.unlink()
    if worktree_path.exists():
        worktree_path.replace(shared_path)
        return "moved-worktree-file"

    shared_path.write_text(ensure_text_ends_with_newline(fallback_text), encoding="utf-8")
    return "created-shared"


def link_worktree_file(worktree_path: Path, shared_path: Path) -> str:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if worktree_path.is_symlink():
        current_target = worktree_path.resolve(strict=False)
        if current_target == shared_path:
            return "already-linked"
        raise RuntimeError(
            f"{worktree_path} already points to {current_target}, expected {shared_path}"
        )

    if worktree_path.exists():
        if not filecmp.cmp(worktree_path, shared_path, shallow=False):
            raise RuntimeError(
                f"{worktree_path} differs from {shared_path}. Move or merge it before relinking."
            )
        worktree_path.unlink()

    worktree_path.symlink_to(shared_path)
    return "linked"


def build_root_additions(
    root_values: dict[str, str],
    example_values: dict[str, str],
    frontend_values: dict[str, str],
) -> list[tuple[str, str]]:
    additions: list[tuple[str, str]] = []

    if not root_values.get("JWT_SECRET", "").strip():
        additions.append(("JWT_SECRET", secrets.token_urlsafe(48)))

    if not root_values.get("API_BASE_URL", "").strip():
        api_base_url = frontend_values.get("NEXT_PUBLIC_API_URL") or example_values.get(
            "API_BASE_URL", "http://localhost:8000"
        )
        additions.append(("API_BASE_URL", api_base_url))

    if not root_values.get("FRONTEND_BASE_URL", "").strip():
        additions.append(("FRONTEND_BASE_URL", "http://localhost:3000"))

    for key in ("BRIEF_TIMES", "ALERT_CHECK_INTERVAL_MINUTES"):
        if not root_values.get(key, "").strip() and example_values.get(key, "").strip():
            additions.append((key, example_values[key]))

    return additions


def build_frontend_additions(
    frontend_values: dict[str, str],
    root_values: dict[str, str],
    example_values: dict[str, str],
) -> list[tuple[str, str]]:
    if frontend_values.get("NEXT_PUBLIC_API_URL", "").strip():
        return []

    api_base_url = root_values.get("API_BASE_URL") or example_values.get(
        "NEXT_PUBLIC_API_URL", "http://localhost:8000"
    )
    return [("NEXT_PUBLIC_API_URL", api_base_url)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed ~/.config/hfi shared env files and symlink this worktree to them."
    )
    parser.add_argument(
        "--shared-dir",
        default=str(DEFAULT_SHARED_DIR),
        help="Directory that stores the shared env files (default: ~/.config/hfi).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    frontend_dir = project_root / "frontend"
    shared_dir = Path(args.shared_dir).expanduser()

    root_worktree_path = project_root / ".env"
    frontend_worktree_path = frontend_dir / ".env.local"
    root_shared_path = shared_dir / "root.env"
    frontend_shared_path = shared_dir / "frontend.env.local"
    root_example_path = project_root / ".env.example"
    frontend_example_path = frontend_dir / ".env.local.example"

    root_seed_text = read_text(root_worktree_path) or read_text(root_example_path)
    frontend_seed_text = read_text(frontend_worktree_path) or read_text(frontend_example_path)

    root_action = ensure_shared_file(root_shared_path, root_worktree_path, root_seed_text)
    frontend_action = ensure_shared_file(frontend_shared_path, frontend_worktree_path, frontend_seed_text)

    example_values = parse_env_text(read_text(root_example_path))
    root_values = parse_env_text(read_text(root_shared_path))
    frontend_values = parse_env_text(read_text(frontend_shared_path))

    root_additions = build_root_additions(root_values, example_values, frontend_values)
    append_missing_values(root_shared_path, root_additions)

    root_values = parse_env_text(read_text(root_shared_path))
    frontend_additions = build_frontend_additions(frontend_values, root_values, example_values)
    append_missing_values(frontend_shared_path, frontend_additions)

    root_link_action = link_worktree_file(root_worktree_path, root_shared_path)
    frontend_link_action = link_worktree_file(frontend_worktree_path, frontend_shared_path)

    print(f"Shared root env: {root_shared_path} ({root_action})")
    print(f"Shared frontend env: {frontend_shared_path} ({frontend_action})")
    print(f"Worktree .env: {root_worktree_path} ({root_link_action})")
    print(f"Worktree frontend/.env.local: {frontend_worktree_path} ({frontend_link_action})")
    print("Run `python3 tools/check_env.py` to verify required keys and URL alignment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
