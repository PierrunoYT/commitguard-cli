"""Commit analysis using AI via OpenRouter."""

from __future__ import annotations

import json
from pathlib import Path

from git import Repo
from openai import OpenAI, APIError, RateLimitError, APITimeoutError

from .cache import (
    make_cache_key,
    read_cached_json,
    read_cached_text,
    staged_diff_fingerprint,
    write_cached_json,
    write_cached_text,
)
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

# Extra instructions appended when using ``--focus`` (or config ``focus``).
FOCUS_EXTRA: dict[str, str] = {
    "general": "",
    "security": (
        "\n\nFocus this review on security: injection, auth/authz, secrets, "
        "cryptography, and unsafe deserialization."
    ),
    "performance": (
        "\n\nFocus this review on performance: algorithmic complexity, I/O, "
        "memory use, and hot paths."
    ),
    "bugs": (
        "\n\nFocus this review on correctness: logic bugs, edge cases, "
        "race conditions, and error handling gaps."
    ),
    "quality": (
        "\n\nFocus this review on maintainability: readability, structure, "
        "tests, and technical debt."
    ),
}

_client_cache: dict[str, OpenAI] = {}
SEVERITY_LEVELS = {"critical", "warning", "info"}


def build_effective_system_prompt(
    focus: str = "general",
    system_prompt_override: str | None = None,
) -> str:
    """
    Combine the default or custom system prompt with *focus* scoping.

    If *system_prompt_override* is set (e.g. from ``--prompt-file``), it replaces
    the built-in system prompt; focus instructions are still appended when not ``general``.
    """
    focus_key = focus if focus in FOCUS_EXTRA else "general"
    base = (
        system_prompt_override.strip()
        if system_prompt_override
        else SYSTEM_PROMPT
    )
    return base + FOCUS_EXTRA[focus_key]


def load_prompt_file(path: str | Path) -> str:
    """Read UTF-8 text from *path* for use as ``system_prompt_override``."""
    p = Path(path)
    if not p.is_file():
        raise AnalysisError(f"Prompt file not found: {p}")
    try:
        return p.read_text(encoding="utf-8")
    except OSError as e:
        raise AnalysisError(f"Could not read prompt file ({p}): {e}") from e


def list_commit_shas_in_range(repo_path: str, from_ref: str, to_ref: str) -> list[str]:
    """
    Return commit SHAs in ``from_ref..to_ref`` (Git range), oldest first.

    This matches ``git rev-list --reverse from_ref..to_ref``: commits reachable
    from *to_ref* but not from *from_ref* (branch comparison / feature range).
    """
    repo = Repo(repo_path)
    spec = f"{from_ref}..{to_ref}"
    try:
        commits = list(repo.iter_commits(spec, reverse=True))
    except Exception as e:
        raise AnalysisError(
            f"Invalid commit range {spec!r}: {e}"
        ) from e
    return [c.hexsha for c in commits]


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
    *,
    system_prompt: str | None = None,
) -> str:
    """Call OpenRouter API for analysis (supports multiple models)."""
    client = _get_client(api_key)
    sp = system_prompt if system_prompt is not None else SYSTEM_PROMPT
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
                {"role": "system", "content": sp},
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
    *,
    system_prompt: str | None = None,
) -> dict:
    """Call OpenRouter API and request strict JSON output."""
    client = _get_client(api_key)
    sp = system_prompt if system_prompt is not None else SYSTEM_PROMPT
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
                {"role": "system", "content": sp},
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


def _collect_commit_files(commit) -> list[str]:
    files: list[str] = []
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
    return files


def _commit_message(commit) -> str:
    msg = commit.message
    return msg.decode("utf-8") if isinstance(msg, bytes) else msg


def analyze_commit(
    repo_path: str,
    ref: str = "HEAD",
    *,
    api_key: str,
    model: str = "anthropic/claude-sonnet-4.6",
    focus: str = "general",
    system_prompt_override: str | None = None,
    use_cache: bool = True,
) -> str:
    """
    Analyze a single commit and return markdown.

    Results may be read from ``.commitguard_cache/`` when *use_cache* is true.
    """
    effective = build_effective_system_prompt(focus, system_prompt_override)
    repo = Repo(repo_path)
    commit = repo.commit(ref)
    diff, truncated = _get_diff(repo, commit)
    files = _collect_commit_files(commit)
    message = _commit_message(commit)

    if use_cache:
        key = make_cache_key(
            kind="text",
            model=model,
            focus=focus,
            system_prompt=effective,
            commit_hex=commit.hexsha,
        )
        hit = read_cached_text(repo_path, key)
        if hit is not None:
            return hit

    out = _call_ai(
        diff, message, files, api_key, model, truncated, system_prompt=effective
    )

    if use_cache:
        key = make_cache_key(
            kind="text",
            model=model,
            focus=focus,
            system_prompt=effective,
            commit_hex=commit.hexsha,
        )
        write_cached_text(repo_path, key, out)
    return out


def analyze_commit_json(
    repo_path: str,
    ref: str = "HEAD",
    *,
    api_key: str,
    model: str = "anthropic/claude-sonnet-4.6",
    focus: str = "general",
    system_prompt_override: str | None = None,
    use_cache: bool = True,
) -> dict:
    """
    Analyze a single commit and return structured JSON (summary + findings).

    Cached separately from markdown output under ``.commitguard_cache/``.
    """
    effective = build_effective_system_prompt(focus, system_prompt_override)
    repo = Repo(repo_path)
    commit = repo.commit(ref)
    diff, truncated = _get_diff(repo, commit)
    files = _collect_commit_files(commit)
    message = _commit_message(commit)

    if use_cache:
        key = make_cache_key(
            kind="json",
            model=model,
            focus=focus,
            system_prompt=effective,
            commit_hex=commit.hexsha,
        )
        hit = read_cached_json(repo_path, key)
        if hit is not None:
            return hit

    out = _call_ai_json(
        diff, message, files, api_key, model, truncated, system_prompt=effective
    )

    if use_cache:
        key = make_cache_key(
            kind="json",
            model=model,
            focus=focus,
            system_prompt=effective,
            commit_hex=commit.hexsha,
        )
        write_cached_json(repo_path, key, out)
    return out


def analyze_staged(
    repo_path: str,
    *,
    api_key: str,
    model: str = "anthropic/claude-sonnet-4.6",
    focus: str = "general",
    system_prompt_override: str | None = None,
    use_cache: bool = True,
) -> str:
    """Analyze staged changes (index) and return markdown."""
    effective = build_effective_system_prompt(focus, system_prompt_override)
    repo = Repo(repo_path)
    diff = repo.git.diff("--cached")
    if not diff.strip():
        return "No staged changes to analyze."
    truncated = len(diff) > MAX_DIFF_CHARS
    diff_slice = diff[:MAX_DIFF_CHARS]
    files = repo.git.diff("--cached", "--name-only").splitlines()
    fp = staged_diff_fingerprint(diff)

    if use_cache:
        key = make_cache_key(
            kind="text",
            model=model,
            focus=focus,
            system_prompt=effective,
            staged_fingerprint=fp,
        )
        hit = read_cached_text(repo_path, key)
        if hit is not None:
            return hit

    out = _call_ai(
        diff_slice,
        "(staged changes)",
        files,
        api_key,
        model,
        truncated,
        system_prompt=effective,
    )

    if use_cache:
        key = make_cache_key(
            kind="text",
            model=model,
            focus=focus,
            system_prompt=effective,
            staged_fingerprint=fp,
        )
        write_cached_text(repo_path, key, out)
    return out


def analyze_staged_json(
    repo_path: str,
    *,
    api_key: str,
    model: str = "anthropic/claude-sonnet-4.6",
    focus: str = "general",
    system_prompt_override: str | None = None,
    use_cache: bool = True,
) -> dict:
    """Analyze staged changes and return structured JSON."""
    effective = build_effective_system_prompt(focus, system_prompt_override)
    repo = Repo(repo_path)
    diff = repo.git.diff("--cached")
    if not diff.strip():
        return {"summary": "No staged changes to analyze.", "findings": []}
    truncated = len(diff) > MAX_DIFF_CHARS
    diff_slice = diff[:MAX_DIFF_CHARS]
    files = repo.git.diff("--cached", "--name-only").splitlines()
    fp = staged_diff_fingerprint(diff)

    if use_cache:
        key = make_cache_key(
            kind="json",
            model=model,
            focus=focus,
            system_prompt=effective,
            staged_fingerprint=fp,
        )
        hit = read_cached_json(repo_path, key)
        if hit is not None:
            return hit

    out = _call_ai_json(
        diff_slice,
        "(staged changes)",
        files,
        api_key,
        model,
        truncated,
        system_prompt=effective,
    )

    if use_cache:
        key = make_cache_key(
            kind="json",
            model=model,
            focus=focus,
            system_prompt=effective,
            staged_fingerprint=fp,
        )
        write_cached_json(repo_path, key, out)
    return out
