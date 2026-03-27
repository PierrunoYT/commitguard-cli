"""CommitGuard - AI-powered Git commit analysis for bugs and issues."""

from .analyzer import (
    FOCUS_EXTRA,
    SYSTEM_PROMPT,
    analyze_commit,
    analyze_commit_json,
    analyze_staged,
    analyze_staged_json,
    build_effective_system_prompt,
    has_issues_in_text,
    list_commit_shas_in_range,
    load_prompt_file,
)
from .errors import AnalysisError

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "AnalysisError",
    "SYSTEM_PROMPT",
    "FOCUS_EXTRA",
    "analyze_commit",
    "analyze_commit_json",
    "analyze_staged",
    "analyze_staged_json",
    "build_effective_system_prompt",
    "has_issues_in_text",
    "list_commit_shas_in_range",
    "load_prompt_file",
]
