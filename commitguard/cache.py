"""On-disk cache for analysis results under ``.commitguard_cache/`` in the repository."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def cache_root(repo_path: str) -> Path:
    """Return ``<repo>/.commitguard_cache``."""
    return Path(repo_path) / ".commitguard_cache"


def make_cache_key(
    *,
    kind: str,
    model: str,
    focus: str,
    system_prompt: str,
    commit_hex: str | None = None,
    staged_fingerprint: str | None = None,
) -> str:
    """
    Stable SHA-256 hex digest used as the cache filename stem.

    *kind* must be ``\"text\"`` or ``\"json\"``.
    For commits, pass *commit_hex*; for staged changes, pass *staged_fingerprint* (hash of diff + index).
    """
    parts = [kind, model, focus, system_prompt]
    if commit_hex is not None:
        parts.append(f"commit:{commit_hex}")
    elif staged_fingerprint is not None:
        parts.append(f"staged:{staged_fingerprint}")
    else:
        raise ValueError("Either commit_hex or staged_fingerprint is required")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def staged_diff_fingerprint(diff: str) -> str:
    """Short fingerprint of staged diff for cache keys."""
    return hashlib.sha256(diff.encode("utf-8")).hexdigest()


def read_cached_text(repo_path: str, key: str) -> str | None:
    path = cache_root(repo_path) / f"{key}.txt"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return None


def write_cached_text(repo_path: str, key: str, content: str) -> None:
    path = cache_root(repo_path) / f"{key}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_cached_json(repo_path: str, key: str) -> dict | None:
    path = cache_root(repo_path) / f"{key}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def write_cached_json(repo_path: str, key: str, content: dict) -> None:
    path = cache_root(repo_path) / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, sort_keys=True), encoding="utf-8")
