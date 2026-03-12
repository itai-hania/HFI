"""Tests for shared environment utility helpers."""

from pathlib import Path

import pytest

from common.env_utils import (
    SingleInstanceFileLock,
    ensure_no_duplicate_env_keys,
    find_duplicate_env_keys,
    require_env_vars,
)


def test_find_duplicate_env_keys_reports_key_and_lines(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "DASHBOARD_PASSWORD=one",
                "JWT_SECRET=abc",
                "DASHBOARD_PASSWORD=two",
                "OTHER=value",
                "JWT_SECRET=def",
            ]
        ),
        encoding="utf-8",
    )

    duplicates = find_duplicate_env_keys(env_path)
    as_map = {item.key: item.lines for item in duplicates}
    assert as_map["DASHBOARD_PASSWORD"] == (1, 3)
    assert as_map["JWT_SECRET"] == (2, 5)


def test_ensure_no_duplicate_env_keys_raises(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("A=1\nA=2\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        ensure_no_duplicate_env_keys(env_path)

    assert "A (lines 1, 2)" in str(exc.value)


def test_require_env_vars_raises_for_missing():
    with pytest.raises(RuntimeError) as exc:
        require_env_vars(["A", "B"], env={"A": "value"}, scope="api")
    assert "Missing required api environment variables: B" in str(exc.value)


def test_single_instance_file_lock_acquire_release(tmp_path: Path):
    lock_path = tmp_path / "runtime" / "test.lock"
    lock = SingleInstanceFileLock(lock_path)
    lock.acquire()
    lock.release()
