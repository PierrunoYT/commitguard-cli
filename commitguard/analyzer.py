"""Commit analysis using AI via OpenRouter."""

from __future__ import annotations

import json
from git import Repo
from openai import OpenAI, APIError, RateLimitError, APITimeoutError
from .errors import AnalysisError

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_DIFF_CHARS = 12000


SYSTEM_PROMPT = """You are a code review assistant. Analyze Git commits for:
1. Potential bugs and logic errors
2. Security vulnerabilities
3. Code quality issues
4. Missing error handling or validation
5. Performance concerns

Respond in markdown. Be concise. If nothing concerning is found, say "No issues detected."
"""

_client_cache: dict[str, OpenAI] = {}
SEVERITY_LEVELS = {"critical", "warning", "info"}


def _get_client(api_key: str) -> OpenAI:
    """Get or create a reusable OpenAI client."""
    if api_key not in _client_cache:
        _client_cache[api_key] = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
        )
    return _client_cache[api_key]


def _get_diff(repo: Repo, commit) -> tuple[str, bool]:
    """Get diff for a commit. Returns (diff, was_truncated)."""
    if commit.parents:
        diff = repo.git.diff(commit.parents[0], commit)
    else:
        diff = repo.git.diff(commit.hexsha, root=True)
    truncated = len(diff) > MAX_DIFF_CHARS
    return diff[:MAX_DIFF_CHARS], truncated


def _call_ai(
    diff: str,
    message: str,
    files: list[str],
    api_key: str,
    model: str,
    truncated: bool = False,
) -> str:
    """Call OpenRouter API for analysis (supports multiple models)."""
    client = _get_client(api_key)
    truncation_note = (
        "\n\n*Note: The diff was truncated due to size.*" if truncated else ""
    )
    user_content = f"""Analyze this commit:

**Message:** {message}
**Files:** {", ".join(files) if files else "N/A"}

**Diff:**
```
{diff or "(no diff)"}
```{truncation_note}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        return response.choices[0].message.content or "No response."
    except RateLimitError as e:
        raise AnalysisError(
            f"Rate limit exceeded. Please wait and retry. Details: {e}"
        ) from e
    except APITimeoutError as e:
        raise AnalysisError(f"Request timed out. Please try again. Details: {e}") from e
    except APIError as e:
        raise AnalysisError(f"API error occurred: {e}") from e


def _call_ai_json(
    diff: str,
    message: str,
    files: list[str],
    api_key: str,
    model: str,
    truncated: bool = False,
) -> dict:
    """Call OpenRouter API and request strict JSON output."""
    client = _get_client(api_key)
    truncation_note = (
        "\n\nThe diff was truncated due to size." if truncated else ""
    )
    response_schema = {
        "summary": "string",
        "findings": [
            {
                "severity": "critical|warning|info",
                "title": "string",
                "description": "string",
                "file": "string|null",
            }
        ],
    }
    user_content = f"""Analyze this commit and return ONLY valid JSON with this schema:
{json.dumps(response_schema, indent=2)}

Rules:
- findings must be an array (can be empty)
- severity must be one of: critical, warning, info
- if no meaningful issues are found, return an empty findings array

Message: {message}
Files: {", ".join(files) if files else "N/A"}
Diff:
{diff or "(no diff)"}{truncation_note}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
    except json.JSONDecodeError as e:
        raise AnalysisError(f"Model returned invalid JSON: {e}") from e
    except RateLimitError as e:
        raise AnalysisError(
            f"Rate limit exceeded. Please wait and retry. Details: {e}"
        ) from e
    except APITimeoutError as e:
        raise AnalysisError(f"Request timed out. Please try again. Details: {e}") from e
    except APIError as e:
        raise AnalysisError(f"API error occurred: {e}") from e

    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise AnalysisError("Invalid JSON response: 'findings' must be an array.")

    normalized_findings: list[dict] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity", "")).lower()
        if severity not in SEVERITY_LEVELS:
            severity = "info"
        normalized_findings.append(
            {
                "severity": severity,
                "title": str(finding.get("title", "Untitled finding")),
                "description": str(finding.get("description", "")),
                "file": finding.get("file"),
            }
        )

    return {
        "summary": str(payload.get("summary", "")),
        "findings": normalized_findings,
    }


def has_issues_in_text(result: str) -> bool:
    """Best-effort detector for issue presence in markdown output."""
    return "no issues detected" not in result.lower()


def analyze_commit(
    repo_path: str,
    ref: str = "HEAD",
    *,
    api_key: str,
    model: str = "anthropic/claude-sonnet-4.6",
) -> str:
    """Analyze a specific commit."""
    repo = Repo(repo_path)
    commit = repo.commit(ref)
    diff, truncated = _get_diff(repo, commit)
    files = []
    if commit.parents:
        for diff_item in commit.diff(commit.parents[0], create_patch=False):
            path = diff_item.b_path or diff_item.a_path
            if path:
                files.append(path)
    else:
        for diff_item in commit.diff(None, create_patch=False):
            path = diff_item.b_path or diff_item.a_path
            if path:
                files.append(path)
    message = (
        commit.message.decode("utf-8")
        if isinstance(commit.message, bytes)
        else commit.message
    )
    return _call_ai(diff, message, files, api_key, model, truncated)


def analyze_commit_json(
    repo_path: str,
    ref: str = "HEAD",
    *,
    api_key: str,
    model: str = "anthropic/claude-sonnet-4.6",
) -> dict:
    """Analyze a specific commit and return structured JSON."""
    repo = Repo(repo_path)
    commit = repo.commit(ref)
    diff, truncated = _get_diff(repo, commit)
    files = []
    if commit.parents:
        for diff_item in commit.diff(commit.parents[0], create_patch=False):
            path = diff_item.b_path or diff_item.a_path
            if path:
                files.append(path)
    else:
        for diff_item in commit.diff(None, create_patch=False):
            path = diff_item.b_path or diff_item.a_path
            if path:
                files.append(path)
    message = (
        commit.message.decode("utf-8")
        if isinstance(commit.message, bytes)
        else commit.message
    )
    return _call_ai_json(diff, message, files, api_key, model, truncated)


def analyze_staged(
    repo_path: str,
    *,
    api_key: str,
    model: str = "anthropic/claude-sonnet-4.6",
) -> str:
    """Analyze staged changes."""
    repo = Repo(repo_path)
    diff = repo.git.diff("--cached")
    if not diff.strip():
        return "No staged changes to analyze."
    truncated = len(diff) > MAX_DIFF_CHARS
    diff = diff[:MAX_DIFF_CHARS]
    files = repo.git.diff("--cached", "--name-only").splitlines()
    return _call_ai(diff, "(staged changes)", files, api_key, model, truncated)


def analyze_staged_json(
    repo_path: str,
    *,
    api_key: str,
    model: str = "anthropic/claude-sonnet-4.6",
) -> dict:
    """Analyze staged changes and return structured JSON."""
    repo = Repo(repo_path)
    diff = repo.git.diff("--cached")
    if not diff.strip():
        return {"summary": "No staged changes to analyze.", "findings": []}
    truncated = len(diff) > MAX_DIFF_CHARS
    diff = diff[:MAX_DIFF_CHARS]
    files = repo.git.diff("--cached", "--name-only").splitlines()
    return _call_ai_json(diff, "(staged changes)", files, api_key, model, truncated)
