"""Shared environment and runtime lock helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from dotenv import load_dotenv

_DOTENV_KEY_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


@dataclass(frozen=True)
class DuplicateEnvKey:
    """Represents one duplicated key and the line numbers where it appears."""

    key: str
    lines: tuple[int, ...]


def _iter_dotenv_key_lines(dotenv_path: Path) -> Iterable[tuple[int, str]]:
    with dotenv_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = _DOTENV_KEY_RE.match(stripped)
            if match:
                yield line_number, match.group(1)


def find_duplicate_env_keys(dotenv_path: str | os.PathLike[str]) -> list[DuplicateEnvKey]:
    """Find duplicate key declarations in a dotenv file."""
    path = Path(dotenv_path)
    if not path.exists():
        return []

    seen: dict[str, list[int]] = {}
    for line_number, key in _iter_dotenv_key_lines(path):
        seen.setdefault(key, []).append(line_number)

    duplicates: list[DuplicateEnvKey] = []
    for key, lines in sorted(seen.items()):
        if len(lines) > 1:
            duplicates.append(DuplicateEnvKey(key=key, lines=tuple(lines)))
    return duplicates


def ensure_no_duplicate_env_keys(dotenv_path: str | os.PathLike[str]) -> None:
    """Raise a runtime error with key names and line numbers if duplicates exist."""
    path = Path(dotenv_path)
    duplicates = find_duplicate_env_keys(path)
    if not duplicates:
        return

    details = ", ".join(f"{item.key} (lines {', '.join(str(v) for v in item.lines)})" for item in duplicates)
    raise RuntimeError(f"Duplicate keys found in {path}: {details}")


def load_dotenv_checked(
    dotenv_path: str | os.PathLike[str] | None = None,
    *,
    override: bool = False,
) -> bool:
    """Load dotenv after duplicate-key validation."""
    path = Path(dotenv_path) if dotenv_path is not None else Path.cwd() / ".env"
    if path.exists():
        ensure_no_duplicate_env_keys(path)
        return load_dotenv(path, override=override)
    return load_dotenv(override=override)


def require_env_vars(
    required_keys: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    scope: str = "service",
) -> dict[str, str]:
    """Return validated env values or raise when required keys are missing."""
    source = env or os.environ
    missing = [key for key in required_keys if not str(source.get(key, "")).strip()]
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise RuntimeError(f"Missing required {scope} environment variables: {missing_str}")
    return {key: str(source[key]).strip() for key in required_keys}


class SingleInstanceFileLock:
    """Single-process file lock for local runtime guards."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+", encoding="utf-8")

        try:
            if os.name == "nt":
                import msvcrt

                self._handle.seek(0)
                self._handle.write("1")
                self._handle.flush()
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.release()
            raise RuntimeError(f"Cannot acquire lock: {self.path}") from exc

    def release(self) -> None:
        if self._handle is None:
            return

        try:
            if os.name == "nt":
                import msvcrt

                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "SingleInstanceFileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

