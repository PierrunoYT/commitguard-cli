"""Commit analysis using AI via OpenRouter."""

from __future__ import annotations

from git import Repo
from openai import OpenAI

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


def _call_ai(diff: str, message: str, files: list[str], api_key: str, model: str, truncated: bool = False) -> str:
    """Call OpenRouter API for analysis (supports multiple models)."""
    client = _get_client(api_key)
    truncation_note = "\n\n*Note: The diff was truncated due to size.*" if truncated else ""
    user_content = f"""Analyze this commit:

**Message:** {message}
**Files:** {', '.join(files) if files else 'N/A'}

**Diff:**
```
{diff or '(no diff)'}
```{truncation_note}
"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content or "No response."


def analyze_commit(
    repo_path: str,
    ref: str = "HEAD",
    *,
    api_key: str,
    model: str = "openai/gpt-4o-mini",
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
    return _call_ai(diff, commit.message, files, api_key, model, truncated)


def analyze_staged(
    repo_path: str,
    *,
    api_key: str,
    model: str = "openai/gpt-4o-mini",
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
