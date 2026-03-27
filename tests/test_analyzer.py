"""Tests for commitguard.analyzer module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from openai import APIError, APITimeoutError, RateLimitError

from commitguard.analyzer import (
    MAX_DIFF_CHARS,
    SEVERITY_LEVELS,
    _call_ai,
    _call_ai_json,
    _get_client,
    _get_diff,
    analyze_commit,
    analyze_commit_json,
    analyze_staged,
    analyze_staged_json,
    build_effective_system_prompt,
    has_issues_in_text,
    list_commit_shas_in_range,
)
from commitguard.errors import AnalysisError


# ---------------------------------------------------------------------------
# has_issues_in_text
# ---------------------------------------------------------------------------


def test_has_issues_no_issues_detected():
    assert has_issues_in_text("No issues detected.") is False


def test_has_issues_no_issues_case_insensitive():
    assert has_issues_in_text("NO ISSUES DETECTED") is False
    assert has_issues_in_text("No Issues Detected") is False


def test_has_issues_with_issues():
    assert has_issues_in_text("Found a potential SQL injection.") is True


def test_has_issues_empty_string():
    assert has_issues_in_text("") is True


def test_has_issues_embedded_phrase():
    assert has_issues_in_text("Summary: no issues detected in code.") is False


# ---------------------------------------------------------------------------
# _get_diff
# ---------------------------------------------------------------------------


def test_get_diff_with_parents():
    parent = MagicMock()
    commit = MagicMock()
    commit.parents = [parent]
    repo = MagicMock()
    repo.git.diff.return_value = "abc123"

    diff, truncated = _get_diff(repo, commit)

    repo.git.diff.assert_called_once_with(parent, commit)
    assert diff == "abc123"
    assert truncated is False


def test_get_diff_no_parents():
    commit = MagicMock()
    commit.parents = []
    commit.hexsha = "deadbeef"
    repo = MagicMock()
    repo.git.diff.return_value = "initial"

    diff, truncated = _get_diff(repo, commit)

    repo.git.diff.assert_called_once_with("deadbeef", root=True)
    assert diff == "initial"
    assert truncated is False


def test_get_diff_truncated():
    commit = MagicMock()
    commit.parents = [MagicMock()]
    repo = MagicMock()
    long_diff = "x" * (MAX_DIFF_CHARS + 500)
    repo.git.diff.return_value = long_diff

    diff, truncated = _get_diff(repo, commit)

    assert len(diff) == MAX_DIFF_CHARS
    assert truncated is True


def test_get_diff_exact_limit():
    commit = MagicMock()
    commit.parents = [MagicMock()]
    repo = MagicMock()
    repo.git.diff.return_value = "x" * MAX_DIFF_CHARS

    diff, truncated = _get_diff(repo, commit)

    assert len(diff) == MAX_DIFF_CHARS
    assert truncated is False


# ---------------------------------------------------------------------------
# _get_client caching
# ---------------------------------------------------------------------------


def test_get_client_caching():
    import commitguard.analyzer as mod

    saved = mod._client_cache.copy()
    mod._client_cache.clear()
    try:
        with patch.object(mod, "OpenAI") as mock_openai:
            mock_openai.side_effect = lambda **kw: MagicMock(name=f"client-{kw['api_key']}")
            c1 = _get_client("key-a")
            c2 = _get_client("key-a")
            assert c1 is c2
            assert mock_openai.call_count == 1

            c3 = _get_client("key-b")
            assert c3 is not c1
            assert mock_openai.call_count == 2
    finally:
        mod._client_cache.clear()
        mod._client_cache.update(saved)


# ---------------------------------------------------------------------------
# _call_ai
# ---------------------------------------------------------------------------


def _mock_completion(content: str) -> MagicMock:
    """Build a fake completions response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@patch("commitguard.analyzer._get_client")
def test_call_ai_basic(mock_gc):
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion("looks good")
    mock_gc.return_value = client

    result = _call_ai("diff", "msg", ["a.py"], "key", "model-1")

    assert result == "looks good"
    client.chat.completions.create.assert_called_once()


@patch("commitguard.analyzer._get_client")
def test_call_ai_no_content_returns_fallback(mock_gc):
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion(None)
    mock_gc.return_value = client

    result = _call_ai("diff", "msg", [], "key", "m")

    assert result == "No response."


@patch("commitguard.analyzer._get_client")
def test_call_ai_truncation_note(mock_gc):
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion("ok")
    mock_gc.return_value = client

    _call_ai("diff", "msg", [], "key", "m", truncated=True)

    call_args = client.chat.completions.create.call_args
    user_msg = call_args[1]["messages"][1]["content"]
    assert "truncated" in user_msg.lower()


# ---------------------------------------------------------------------------
# _call_ai error handling
# ---------------------------------------------------------------------------


@patch("commitguard.analyzer._get_client")
def test_call_ai_rate_limit(mock_gc):
    client = MagicMock()
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {}
    client.chat.completions.create.side_effect = RateLimitError(
        message="rate limited", response=resp, body=None
    )
    mock_gc.return_value = client

    with pytest.raises(AnalysisError, match="Rate limit"):
        _call_ai("d", "m", [], "k", "model")


@patch("commitguard.analyzer._get_client")
def test_call_ai_timeout(mock_gc):
    client = MagicMock()
    client.chat.completions.create.side_effect = APITimeoutError(request=MagicMock())
    mock_gc.return_value = client

    with pytest.raises(AnalysisError, match="timed out"):
        _call_ai("d", "m", [], "k", "model")


@patch("commitguard.analyzer._get_client")
def test_call_ai_api_error(mock_gc):
    client = MagicMock()
    resp = MagicMock()
    resp.status_code = 500
    resp.headers = {}
    client.chat.completions.create.side_effect = APIError(
        message="server error", request=MagicMock(), body=None
    )
    mock_gc.return_value = client

    with pytest.raises(AnalysisError, match="API error"):
        _call_ai("d", "m", [], "k", "model")


# ---------------------------------------------------------------------------
# _call_ai_json
# ---------------------------------------------------------------------------


@patch("commitguard.analyzer._get_client")
def test_call_ai_json_valid(mock_gc):
    payload = {
        "summary": "All good",
        "findings": [
            {
                "severity": "warning",
                "title": "Unused import",
                "description": "os is imported but unused",
                "file": "main.py",
            }
        ],
    }
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion(json.dumps(payload))
    mock_gc.return_value = client

    result = _call_ai_json("d", "m", [], "k", "model")

    assert result["summary"] == "All good"
    assert len(result["findings"]) == 1
    assert result["findings"][0]["severity"] == "warning"


@patch("commitguard.analyzer._get_client")
def test_call_ai_json_invalid_json(mock_gc):
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion("not json {{")
    mock_gc.return_value = client

    with pytest.raises(AnalysisError, match="invalid JSON"):
        _call_ai_json("d", "m", [], "k", "model")


@patch("commitguard.analyzer._get_client")
def test_call_ai_json_missing_findings(mock_gc):
    payload = {"summary": "ok"}
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion(json.dumps(payload))
    mock_gc.return_value = client

    with pytest.raises(AnalysisError, match="findings"):
        _call_ai_json("d", "m", [], "k", "model")


@patch("commitguard.analyzer._get_client")
def test_call_ai_json_findings_not_list(mock_gc):
    payload = {"summary": "ok", "findings": "none"}
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion(json.dumps(payload))
    mock_gc.return_value = client

    with pytest.raises(AnalysisError, match="findings"):
        _call_ai_json("d", "m", [], "k", "model")


@patch("commitguard.analyzer._get_client")
def test_call_ai_json_severity_normalization(mock_gc):
    payload = {
        "summary": "s",
        "findings": [
            {"severity": "CRITICAL", "title": "t1", "description": "d1", "file": None},
            {"severity": "UNKNOWN", "title": "t2", "description": "d2", "file": None},
            {"severity": "Warning", "title": "t3", "description": "d3", "file": None},
        ],
    }
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion(json.dumps(payload))
    mock_gc.return_value = client

    result = _call_ai_json("d", "m", [], "k", "model")

    assert result["findings"][0]["severity"] == "critical"
    assert result["findings"][1]["severity"] == "info"  # unknown → info
    assert result["findings"][2]["severity"] == "warning"


@patch("commitguard.analyzer._get_client")
def test_call_ai_json_empty_findings(mock_gc):
    payload = {"summary": "clean", "findings": []}
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion(json.dumps(payload))
    mock_gc.return_value = client

    result = _call_ai_json("d", "m", [], "k", "model")

    assert result["findings"] == []
    assert result["summary"] == "clean"


@patch("commitguard.analyzer._get_client")
def test_call_ai_json_non_dict_finding_skipped(mock_gc):
    payload = {"summary": "s", "findings": ["not-a-dict", {"severity": "info", "title": "t"}]}
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion(json.dumps(payload))
    mock_gc.return_value = client

    result = _call_ai_json("d", "m", [], "k", "model")

    assert len(result["findings"]) == 1


@patch("commitguard.analyzer._get_client")
def test_call_ai_json_rate_limit(mock_gc):
    client = MagicMock()
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {}
    client.chat.completions.create.side_effect = RateLimitError(
        message="rate limited", response=resp, body=None
    )
    mock_gc.return_value = client

    with pytest.raises(AnalysisError, match="Rate limit"):
        _call_ai_json("d", "m", [], "k", "model")


# ---------------------------------------------------------------------------
# SEVERITY_LEVELS constant
# ---------------------------------------------------------------------------


def test_severity_levels():
    assert SEVERITY_LEVELS == {"critical", "warning", "info"}


def test_build_effective_system_prompt_security():
    sp = build_effective_system_prompt("security", None)
    assert "security" in sp.lower() or "injection" in sp.lower()


def test_build_effective_system_prompt_override():
    sp = build_effective_system_prompt("general", "CUSTOM PROMPT ONLY")
    assert sp.startswith("CUSTOM PROMPT ONLY")


# ---------------------------------------------------------------------------
# list_commit_shas_in_range (real git repo)
# ---------------------------------------------------------------------------


def test_list_commit_shas_in_range(tmp_path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "f.txt").write_text("a")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "first"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "-b", "feature"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "f.txt").write_text("ab")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "second"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    shas = list_commit_shas_in_range(str(tmp_path), "main", "feature")
    assert len(shas) == 1


# ---------------------------------------------------------------------------
# analyze_commit / analyze_commit_json (integration-ish with mocked internals)
# ---------------------------------------------------------------------------


@patch("commitguard.analyzer.write_cached_text")
@patch("commitguard.analyzer.read_cached_text", return_value=None)
@patch("commitguard.analyzer._call_ai", return_value="No issues detected.")
@patch("commitguard.analyzer.Repo")
def test_analyze_commit(mock_repo_cls, mock_call, _rc, _wc):
    repo = MagicMock()
    mock_repo_cls.return_value = repo

    commit = MagicMock()
    commit.hexsha = "abc123deadbeef"
    commit.parents = [MagicMock()]
    commit.message = "fix bug"
    diff_item = MagicMock()
    diff_item.b_path = "file.py"
    diff_item.a_path = "file.py"
    commit.diff.return_value = [diff_item]
    repo.commit.return_value = commit
    repo.git.diff.return_value = "some diff"

    result = analyze_commit("/repo", "abc123", api_key="k", model="m")

    assert result == "No issues detected."
    mock_call.assert_called_once()


@patch("commitguard.analyzer.write_cached_json")
@patch("commitguard.analyzer.read_cached_json", return_value=None)
@patch("commitguard.analyzer._call_ai_json", return_value={"summary": "ok", "findings": []})
@patch("commitguard.analyzer.Repo")
def test_analyze_commit_json(mock_repo_cls, mock_call, _rj, _wj):
    repo = MagicMock()
    mock_repo_cls.return_value = repo

    commit = MagicMock()
    commit.hexsha = "abc123deadbeef"
    commit.parents = [MagicMock()]
    commit.message = "fix bug"
    commit.diff.return_value = []
    repo.commit.return_value = commit
    repo.git.diff.return_value = "diff"

    result = analyze_commit_json("/repo", "abc", api_key="k", model="m")

    assert result == {"summary": "ok", "findings": []}


@patch("commitguard.analyzer.write_cached_text")
@patch("commitguard.analyzer.read_cached_text", return_value=None)
@patch("commitguard.analyzer._call_ai", return_value="No issues detected.")
@patch("commitguard.analyzer.Repo")
def test_analyze_commit_initial_commit(mock_repo_cls, mock_call, _rc, _wc):
    """Test path for commits with no parents (initial commit)."""
    repo = MagicMock()
    mock_repo_cls.return_value = repo

    commit = MagicMock()
    commit.hexsha = "1111111111111111"
    commit.parents = []
    commit.message = b"initial"  # test bytes message path
    diff_item = MagicMock()
    diff_item.b_path = None
    diff_item.a_path = "README.md"
    commit.diff.return_value = [diff_item]
    repo.commit.return_value = commit
    repo.git.diff.return_value = "init diff"

    result = analyze_commit("/repo", "HEAD", api_key="k", model="m")

    assert result == "No issues detected."


# ---------------------------------------------------------------------------
# analyze_staged / analyze_staged_json
# ---------------------------------------------------------------------------


@patch("commitguard.analyzer.write_cached_text")
@patch("commitguard.analyzer.read_cached_text", return_value=None)
@patch("commitguard.analyzer._call_ai", return_value="Looks fine")
@patch("commitguard.analyzer.Repo")
def test_analyze_staged(mock_repo_cls, mock_call, _rc, _wc):
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.git.diff.side_effect = lambda *a, **kw: (
        "staged diff" if "--cached" in a else ""
    )

    # The function calls repo.git.diff("--cached") first, then
    # repo.git.diff("--cached", "--name-only") second.
    repo.git.diff.side_effect = None
    repo.git.diff.return_value = "staged diff"

    result = analyze_staged("/repo", api_key="k", model="m")

    assert result == "Looks fine"


@patch("commitguard.analyzer.Repo")
def test_analyze_staged_no_changes(mock_repo_cls):
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.git.diff.return_value = "   "

    result = analyze_staged("/repo", api_key="k", model="m")

    assert result == "No staged changes to analyze."


@patch("commitguard.analyzer.Repo")
def test_analyze_staged_json_no_changes(mock_repo_cls):
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.git.diff.return_value = ""

    result = analyze_staged_json("/repo", api_key="k", model="m")

    assert result == {"summary": "No staged changes to analyze.", "findings": []}


@patch("commitguard.analyzer.write_cached_json")
@patch("commitguard.analyzer.read_cached_json", return_value=None)
@patch("commitguard.analyzer._call_ai_json", return_value={"summary": "s", "findings": []})
@patch("commitguard.analyzer.Repo")
def test_analyze_staged_json_with_changes(mock_repo_cls, mock_call, _rj, _wj):
    repo = MagicMock()
    mock_repo_cls.return_value = repo
    repo.git.diff.return_value = "some staged diff"

    result = analyze_staged_json("/repo", api_key="k", model="m")

    assert result["summary"] == "s"
    mock_call.assert_called_once()
