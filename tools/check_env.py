#!/usr/bin/env python3
"""Validate local env files and surface common worktree drift."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ENV_KEY_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}
REQUIRED_ROOT_KEYS = ("DASHBOARD_PASSWORD", "JWT_SECRET")
RECOMMENDED_ROOT_KEYS = (
    "API_BASE_URL",
    "FRONTEND_BASE_URL",
    "BRIEF_TIMES",
    "ALERT_CHECK_INTERVAL_MINUTES",
)
FRONTEND_KEYS = ("NEXT_PUBLIC_API_URL",)


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


def read_values(path: Path) -> dict[str, str]:
    return parse_env_text(path.read_text(encoding="utf-8")) if path.exists() else {}


def describe_path(path: Path) -> str:
    if path.is_symlink():
        return f"{path} -> {path.resolve(strict=False)}"
    return str(path)


def normalize_url(raw_url: str) -> tuple[str, str, int, str]:
    parsed = urlsplit(raw_url.strip())
    host = parsed.hostname or ""
    if host in LOOPBACK_HOSTS:
        host = "loopback"
    if parsed.port is not None:
        port = parsed.port
    elif parsed.scheme == "https":
        port = 443
    else:
        port = 80
    path = parsed.path.rstrip("/") or "/"
    return parsed.scheme, host, port, path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local root and frontend env files.")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="HFI repository root (defaults to this checkout).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).expanduser().resolve()
    root_path = project_root / ".env"
    frontend_path = project_root / "frontend" / ".env.local"

    issues: list[str] = []
    root_values = read_values(root_path)
    frontend_values = read_values(frontend_path)

    print(f"Root env: {describe_path(root_path)}")
    print(f"Frontend env: {describe_path(frontend_path)}")

    if not root_path.exists():
        issues.append(f"Missing root env file: {root_path}")
    if not frontend_path.exists():
        issues.append(f"Missing frontend env file: {frontend_path}")

    for key in REQUIRED_ROOT_KEYS:
        if not root_values.get(key, "").strip():
            issues.append(f"Missing required root key: {key}")

    for key in RECOMMENDED_ROOT_KEYS:
        if not root_values.get(key, "").strip():
            issues.append(f"Missing recommended root key: {key}")

    for key in FRONTEND_KEYS:
        if not frontend_values.get(key, "").strip():
            issues.append(f"Missing frontend key: {key}")

    api_base_url = root_values.get("API_BASE_URL", "").strip()
    frontend_api_url = frontend_values.get("NEXT_PUBLIC_API_URL", "").strip()
    if api_base_url and frontend_api_url and normalize_url(api_base_url) != normalize_url(frontend_api_url):
        issues.append(
            "API_BASE_URL and NEXT_PUBLIC_API_URL do not match after loopback normalization"
        )

    if issues:
        print("\nIssues:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("\nEnv check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
