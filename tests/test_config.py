"""Tests for commitguard.config module."""

from __future__ import annotations

from pathlib import Path

import pytest

from commitguard.config import (
    discover_config_walk,
    load_config_file,
    load_pyproject_commitguard,
    load_resolved_config,
    load_standalone_rc,
    normalize_choice,
    resolve_repo_from_config,
)


def test_load_standalone_rc(tmp_path: Path) -> None:
    p = tmp_path / ".commitguardrc"
    p.write_text(
        'model = "openai/gpt-4o-mini"\nformat = "json"\n',
        encoding="utf-8",
    )
    cfg = load_standalone_rc(p)
    assert cfg["model"] == "openai/gpt-4o-mini"
    assert cfg["format"] == "json"


def test_load_pyproject_commitguard(tmp_path: Path) -> None:
    pp = tmp_path / "pyproject.toml"
    pp.write_text(
        '[project]\nname = "x"\n[tool.commitguard]\nformat = "json"\nrepo = "."\n',
        encoding="utf-8",
    )
    cfg = load_pyproject_commitguard(pp)
    assert cfg["format"] == "json"
    assert cfg["repo"] == "."


def test_discover_prefers_commitguardrc_over_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.commitguard]\nformat = "text"\n',
        encoding="utf-8",
    )
    (tmp_path / ".commitguardrc").write_text('format = "json"\n', encoding="utf-8")
    cfg, base = discover_config_walk(tmp_path)
    assert cfg["format"] == "json"
    assert base == tmp_path


def test_load_resolved_config_explicit(tmp_path: Path) -> None:
    f = tmp_path / "cg.toml"
    f.write_text('format = "json"\n', encoding="utf-8")
    cfg, base = load_resolved_config(f)
    assert cfg["format"] == "json"
    assert base == tmp_path


def test_normalize_choice_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid"):
        normalize_choice("nope", frozenset({"text", "json"}), "format")


def test_resolve_repo_from_config_relative(tmp_path: Path) -> None:
    sub = tmp_path / "repo"
    sub.mkdir()
    p = resolve_repo_from_config("repo", tmp_path)
    assert p == sub.resolve()


def test_load_config_file_pyproject_name(tmp_path: Path) -> None:
    pp = tmp_path / "pyproject.toml"
    pp.write_text('[tool.commitguard]\nmodel = "m"\n', encoding="utf-8")
    cfg = load_config_file(pp)
    assert cfg["model"] == "m"
