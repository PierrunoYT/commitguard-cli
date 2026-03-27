"""Load CommitGuard settings from `.commitguardrc` or `[tool.commitguard]` in pyproject.toml."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ALLOWED_KEYS = frozenset(
    {
        "model",
        "repo",
        "format",
        "severity",
        "fail_on",
        "focus",
        "prompt_file",
        "no_cache",
    }
)


def _load_toml_file(path: Path) -> dict[str, Any]:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[no-redef,import-untyped]

    with path.open("rb") as f:
        return tomllib.load(f)


def _pick_allowed(flat: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in flat.items() if k in ALLOWED_KEYS}


def load_pyproject_commitguard(path: Path) -> dict[str, Any]:
    """Return options from ``[tool.commitguard]`` in *path*, if present."""
    data = _load_toml_file(path)
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return {}
    section = tool.get("commitguard")
    if not isinstance(section, dict):
        return {}
    return _pick_allowed(section)


def load_standalone_rc(path: Path) -> dict[str, Any]:
    """Load a standalone ``.commitguardrc`` TOML file (top-level keys only)."""
    data = _load_toml_file(path)
    return _pick_allowed(data)


def load_config_file(path: Path) -> dict[str, Any]:
    """Load config from *path* (``pyproject.toml`` or ``.commitguardrc``)."""
    if path.name == "pyproject.toml":
        return load_pyproject_commitguard(path)
    return load_standalone_rc(path)


def discover_config_walk(start: Path | None = None) -> tuple[dict[str, Any], Path | None]:
    """
    Walk upward from *start* (default: cwd) for ``.commitguardrc`` or ``pyproject.toml``.
    Returns ``({}, None)`` when nothing is found.
    """
    base = Path(start or ".").resolve()
    for directory in [base, *base.parents]:
        rc = directory / ".commitguardrc"
        if rc.is_file():
            return load_config_file(rc), rc.parent
        pp = directory / "pyproject.toml"
        if pp.is_file():
            section = load_pyproject_commitguard(pp)
            if section:
                return section, pp.parent
    return {}, None


def load_resolved_config(
    explicit_path: Path | None,
    walk_start: Path | None = None,
) -> tuple[dict[str, Any], Path | None]:
    """
    Config resolution order:

    1. *explicit_path* if given (``--config``)
    2. ``COMMITGUARD_CONFIG`` environment variable
    3. Walk from *walk_start* or cwd
    """
    if explicit_path is not None:
        return load_config_file(explicit_path), explicit_path.parent
    env_path = os.environ.get("COMMITGUARD_CONFIG")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.is_file():
            return load_config_file(p), p.parent
    return discover_config_walk(walk_start)


def resolve_path_from_config(path_str: str, base_dir: Path | None) -> Path:
    """Resolve a path from config: relative paths are relative to *base_dir*."""
    p = Path(path_str).expanduser()
    if p.is_absolute():
        return p.resolve()
    root = base_dir if base_dir is not None else Path.cwd()
    return (root / p).resolve()


def resolve_repo_from_config(repo_str: str, base_dir: Path | None) -> Path:
    """Resolve ``repo`` from config: relative paths are relative to *base_dir* (config dir)."""
    return resolve_path_from_config(repo_str, base_dir)


def normalize_choice(
    value: Any,
    allowed: frozenset[str],
    key: str,
) -> str:
    if value is None:
        raise ValueError(f"Missing value for {key}")
    s = str(value).strip().lower()
    if s not in allowed:
        raise ValueError(f"Invalid {key!r}: {value!r} (expected one of {sorted(allowed)})")
    return s
