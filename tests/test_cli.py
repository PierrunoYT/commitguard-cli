"""Tests for commitguard.cli module."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from commitguard.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_repo(tmp_path):
    """Create a minimal directory that looks like a git repo."""
    (tmp_path / ".git").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# Version / help
# ---------------------------------------------------------------------------


def test_main_version(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "CommitGuard" in result.output


def test_main_no_command(runner):
    result = runner.invoke(main, [])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# analyze command — missing API key
# ---------------------------------------------------------------------------


def test_analyze_missing_api_key(runner, fake_repo):
    env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(fake_repo)],
        env=env,
    )
    assert result.exit_code != 0
    assert "API key" in result.output


# ---------------------------------------------------------------------------
# analyze command — invalid repo path
# ---------------------------------------------------------------------------


def test_analyze_invalid_repo(runner, tmp_path):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(tmp_path)],
        env=env,
    )
    assert result.exit_code != 0
    assert "Not a Git repository" in result.output


# ---------------------------------------------------------------------------
# analyze command — count < 1
# ---------------------------------------------------------------------------


def test_analyze_count_invalid(runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(fake_repo), "--count", "0"],
        env=env,
    )
    assert result.exit_code != 0
    assert "--count must be at least 1" in result.output


# ---------------------------------------------------------------------------
# analyze command — text format, no issues
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_commit",
    return_value="No issues detected.",
)
def test_analyze_text_no_issues(mock_ac, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(fake_repo)],
        env=env,
    )
    assert result.exit_code == 0
    assert "No issues detected" in result.output


# ---------------------------------------------------------------------------
# analyze command — text format, with issues
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_commit",
    return_value="Found a bug in line 42.",
)
def test_analyze_text_with_issues(mock_ac, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(fake_repo)],
        env=env,
    )
    assert result.exit_code != 0
    assert "Issues found" in result.output or "Found a bug" in result.output


# ---------------------------------------------------------------------------
# analyze command — json format, no findings
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_commit_json",
    return_value={"summary": "clean", "findings": []},
)
def test_analyze_json_no_findings(mock_acj, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(fake_repo), "--format", "json"],
        env=env,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["format_version"] == "1"
    assert len(data["results"]) == 1
    assert data["results"][0]["findings"] == []


# ---------------------------------------------------------------------------
# analyze command — json format, with findings → non-zero exit
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_commit_json",
    return_value={
        "summary": "issues",
        "findings": [{"severity": "warning", "title": "t"}],
    },
)
def test_analyze_json_with_findings(mock_acj, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(fake_repo), "--format", "json"],
        env=env,
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# analyze command — count > 1
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_commit",
    return_value="No issues detected.",
)
def test_analyze_multiple_commits(mock_ac, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(fake_repo), "--count", "3"],
        env=env,
    )
    assert result.exit_code == 0
    assert mock_ac.call_count == 3


# ---------------------------------------------------------------------------
# analyze command — error during analysis
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_commit",
    side_effect=Exception("boom"),
)
def test_analyze_error(mock_ac, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(fake_repo)],
        env=env,
    )
    assert result.exit_code != 0
    assert "error analyzing" in result.output.lower() or "failed" in result.output.lower()


# ---------------------------------------------------------------------------
# check command — missing API key
# ---------------------------------------------------------------------------


def test_check_missing_api_key(runner, fake_repo):
    env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
    result = runner.invoke(
        main,
        ["check", "--repo", str(fake_repo)],
        env=env,
    )
    assert result.exit_code != 0
    assert "API key" in result.output


# ---------------------------------------------------------------------------
# check command — invalid repo
# ---------------------------------------------------------------------------


def test_check_invalid_repo(runner, tmp_path):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["check", "--repo", str(tmp_path)],
        env=env,
    )
    assert result.exit_code != 0
    assert "Not a Git repository" in result.output


# ---------------------------------------------------------------------------
# check command — text format, no issues
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_staged",
    return_value="No issues detected.",
)
def test_check_text_no_issues(mock_as, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["check", "--repo", str(fake_repo)],
        env=env,
    )
    assert result.exit_code == 0
    assert "No issues detected" in result.output


# ---------------------------------------------------------------------------
# check command — text format, with issues
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_staged",
    return_value="Security vulnerability found.",
)
def test_check_text_with_issues(mock_as, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["check", "--repo", str(fake_repo)],
        env=env,
    )
    assert result.exit_code != 0
    assert "Issues found" in result.output or "Security vulnerability" in result.output


# ---------------------------------------------------------------------------
# check command — text format, no staged changes
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_staged",
    return_value="No staged changes to analyze.",
)
def test_check_text_no_staged(mock_as, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["check", "--repo", str(fake_repo)],
        env=env,
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# check command — json format, no findings
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_staged_json",
    return_value={"summary": "clean", "findings": []},
)
def test_check_json_no_findings(mock_asj, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["check", "--repo", str(fake_repo), "--format", "json"],
        env=env,
    )
    assert result.exit_code == 0
    data = json.loads(result.output.split("\n", 1)[1])  # skip "Analyzing staged changes..."
    assert data["format_version"] == "1"
    assert data["results"][0]["commit"] == "staged"
    assert data["results"][0]["findings"] == []


# ---------------------------------------------------------------------------
# check command — json format, with findings → non-zero exit
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_staged_json",
    return_value={
        "summary": "bad",
        "findings": [{"severity": "critical", "title": "xss"}],
    },
)
def test_check_json_with_findings(mock_asj, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["check", "--repo", str(fake_repo), "--format", "json"],
        env=env,
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# check command — error during analysis wraps in ClickException
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_staged",
    side_effect=Exception("kaboom"),
)
def test_check_error(mock_as, mock_update, runner, fake_repo):
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["check", "--repo", str(fake_repo)],
        env=env,
    )
    assert result.exit_code != 0
    assert "kaboom" in result.output


# ---------------------------------------------------------------------------
# Config file defaults
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_commit_json",
    return_value={"summary": "ok", "findings": []},
)
def test_analyze_config_default_format_json(
    mock_acj, mock_update, runner, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (tmp_path / ".commitguardrc").write_text('format = "json"\n', encoding="utf-8")
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(repo)],
        env=env,
    )
    assert result.exit_code == 0
    assert mock_acj.called


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_commit",
    return_value="No issues detected.",
)
def test_analyze_cli_overrides_config_format(
    mock_ac, mock_update, runner, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".commitguardrc").write_text('format = "json"\n', encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    env = {**os.environ, "OPENROUTER_API_KEY": "test-key"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(repo), "--format", "text"],
        env=env,
    )
    assert result.exit_code == 0
    assert mock_ac.called


# ---------------------------------------------------------------------------
# analyze command — api key via --api-key flag
# ---------------------------------------------------------------------------


@patch("commitguard.cli.check_for_update", return_value=None)
@patch(
    "commitguard.cli.analyze_commit",
    return_value="No issues detected.",
)
def test_analyze_api_key_flag(mock_ac, mock_update, runner, fake_repo):
    env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
    result = runner.invoke(
        main,
        ["analyze", "HEAD", "--repo", str(fake_repo), "--api-key", "my-key"],
        env=env,
    )
    assert result.exit_code == 0
    call_kwargs = mock_ac.call_args
    assert call_kwargs[1]["api_key"] == "my-key" or call_kwargs.kwargs["api_key"] == "my-key"
