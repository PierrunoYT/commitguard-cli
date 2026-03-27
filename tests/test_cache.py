"""Tests for commitguard.cache."""

from __future__ import annotations

import json
from pathlib import Path

from commitguard.cache import (
    make_cache_key,
    read_cached_json,
    read_cached_text,
    staged_diff_fingerprint,
    write_cached_json,
    write_cached_text,
)


def test_make_cache_key_commit_vs_staged():
    k1 = make_cache_key(
        kind="text",
        model="m",
        focus="general",
        system_prompt="sys",
        commit_hex="abc",
    )
    k2 = make_cache_key(
        kind="text",
        model="m",
        focus="general",
        system_prompt="sys",
        staged_fingerprint="fp",
    )
    assert k1 != k2
    assert len(k1) == 64


def test_staged_diff_fingerprint_stable():
    assert staged_diff_fingerprint("diff") == staged_diff_fingerprint("diff")
    assert staged_diff_fingerprint("a") != staged_diff_fingerprint("b")


def test_roundtrip_text(tmp_path: Path) -> None:
    key = "k1"
    write_cached_text(str(tmp_path), key, "hello")
    assert read_cached_text(str(tmp_path), key) == "hello"
    assert (tmp_path / ".commitguard_cache" / "k1.txt").is_file()


def test_roundtrip_json(tmp_path: Path) -> None:
    key = "k2"
    payload = {"summary": "s", "findings": []}
    write_cached_json(str(tmp_path), key, payload)
    got = read_cached_json(str(tmp_path), key)
    assert got == payload
    raw = (tmp_path / ".commitguard_cache" / "k2.json").read_text(encoding="utf-8")
    assert json.loads(raw) == payload
