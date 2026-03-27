# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-03-27

### Added

- **Structured output**:
  - Added `--format` option with `text` (default) and `json` for both `analyze` and `check`
  - Added structured JSON response envelope with `format_version`, per-result `summary`, and `findings`
  - Added severity schema in JSON findings: `critical`, `warning`, `info`
- **Severity filtering**:
  - Added `--severity` flag to filter JSON findings by minimum severity level (`info`, `warning`, `critical`)
  - Added `--fail-on` flag to control which minimum severity triggers a non-zero exit code (default: `warning`)
- **Output to file**:
  - Added `-o` / `--output` flag to save analysis results to a file (in addition to stdout)
- **Configuration files**:
  - Support `.commitguardrc` (TOML) and `[tool.commitguard]` in `pyproject.toml` for defaults: `model`, `repo`, `format`, `severity`, `fail-on`, `focus`, `prompt_file`, and `no_cache`
  - Discovery walks upward from the working directory; optional `COMMITGUARD_CONFIG` env or `--config PATH` selects a file explicitly
  - CLI flags and environment variables override config when set (non-default)
- **Analysis focus**: `--focus` (`general`, `security`, `performance`, `bugs`, `quality`) on `analyze` and `check`; configurable via `focus` in config files
- **Custom system prompt**: `--prompt-file` and config key `prompt_file` (UTF-8 file replaces the default system prompt; focus hints are still appended unless `focus` is `general`)
- **Commit ranges**: `analyze --from REF --to REF` using Git range `from..to` (commits reachable from `to` but not from `from`, oldest first)—for example `main..feature`
- **Result cache**: Per-repository `.commitguard_cache/` stores text and JSON results keyed by commit SHA (or staged diff fingerprint), model, focus, and effective system prompt; use `--no-cache` or `no_cache = true` in config to bypass
- **Python library API**: Public exports from `commitguard` (`analyze_commit`, `analyze_commit_json`, `analyze_staged`, `analyze_staged_json`, `build_effective_system_prompt`, `list_commit_shas_in_range`, `load_prompt_file`, `has_issues_in_text`, `SYSTEM_PROMPT`, `FOCUS_EXTRA`) with docstrings on analyzer entry points
- **CI/CD examples**:
  - Added `examples/github-actions.yml`, `examples/gitlab-ci.yml`, and `examples/pre-commit-config.yaml` with README documentation
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md) with dev setup and PR checklist
- **GitHub templates**: Issue templates for bugs and features, and a pull request template under `.github/`
- **Testing**:
  - Added unit tests for `analyzer.py`, `cli.py`, `config.py`, and `cache.py`
  - Tests cover edge cases (root commits, truncated diffs, empty diffs), error handling (rate limits, timeouts, API errors), config discovery, CLI flags, commit ranges, and cache behavior
  - Added `pytest` configuration in `pyproject.toml`

### Changed

- **Exit code behavior**:
  - Commands now return a non-zero exit code when issues are detected, enabling CI gate usage
- **Model defaults**:
  - Changed the default model from `openai/gpt-4o-mini` to `anthropic/claude-sonnet-4.6` for both `analyze` and `check`
- **Documentation**:
  - Updated README examples and option tables to reflect the new default model and model IDs
  - Updated README with JSON usage examples, schema details, exit-code behavior, config file format, CI/pre-commit integration, focus and prompt options, commit ranges, cache behavior, and library usage
  - Added severity filtering and output-to-file documentation to README

### Fixed

- Removed unused `python-dotenv` from `requirements.txt`

### Internal

- Added `ruff` linter configuration to `pyproject.toml`
- Added `tomli` dependency for Python versions older than 3.11 (stdlib `tomllib` on 3.11+)

## [0.1.3] - 2026-03-27

### Changed

- **Error handling clarity**:
  - Added explicit handling for OpenRouter rate limits, timeouts, and API errors with user-facing `AnalysisError` messages
- **Package imports**:
  - Moved `AnalysisError` to a lightweight `commitguard.errors` module to avoid importing analyzer dependencies when importing `commitguard`
- **Dependencies**:
  - Removed unused `python-dotenv` dependency

## [0.1.2] - 2026-03-27

### Changed

- **Analyzer robustness**:
  - Reuse OpenAI client instances per API key to avoid recreating clients on each analysis call
  - Handle root commits more reliably when building diffs and changed file lists
  - Detect and surface when large diffs are truncated to the maximum analysis context
- **CLI behavior**:
  - Skip update checks when running bare `commitguard` without a subcommand
  - Analyze multi-commit ranges in chronological order when using `analyze -n/--count`

## [0.1.1] - 2025-03-21

### Added

- **Automatic update notifications**: Check PyPI for newer versions on CLI startup and display upgrade message when available
- **Version management**: New `version.py` module for PyPI version checking
- `packaging` dependency for version comparison

## [0.1.0] - 2025-03-15

### Added

- **CLI framework**: Click-based CLI with `commitguard` command
- **`analyze` command**: Analyze Git commits for bugs, security issues, and code quality
  - Analyze last commit (default: `HEAD`)
  - Analyze specific commit by hash
  - Analyze multiple commits with `-n` / `--count` flag
  - `-r` / `--repo` option to analyze repositories outside current directory
- **`check` command**: Analyze staged changes before committing
- **OpenRouter integration**: Multi-model AI support via OpenRouter API
  - Supports 100+ models (GPT-4, Claude, Gemini, etc.)
  - Default model: `openai/gpt-4o-mini`
  - `--model` / `-m` option to specify any OpenRouter model
  - `OPENROUTER_MODEL` environment variable for default model configuration
  - `--api-key` option for API key
  - `OPENROUTER_API_KEY` environment variable for authentication
- **AI analysis features**:
  - Bug detection and logic error identification
  - Security vulnerability scanning
  - Code quality assessment
  - Missing error handling detection
  - Performance concern identification
  - Diff analysis with 12000 character limit for context
  - File change tracking for adds/deletes/renames
- **CLI features**:
  - Colorized output with cyan headers and red error messages
  - Version flag (`--version`) showing CommitGuard version
  - Comprehensive help text for all commands
  - **Automatic update notifications** - checks PyPI for newer versions and displays upgrade message
- **Error handling**:
  - Validation for missing API keys
  - `--count` parameter validation (minimum value: 1)
  - Git repository detection and validation
  - Graceful error messages via ClickException
  - Error tracking for batch commit analysis (exits with error if any fail)
- **Documentation**:
  - Comprehensive README with usage examples
  - Troubleshooting guide with common errors and solutions
  - Installation instructions (PyPI and source)
  - Configuration examples for Linux/macOS/Windows
  - Model selection guide with recommended models
  - Development and build artifact cleanup instructions
- **Package structure**:
  - Modular design with `cli.py` and `analyzer.py`
  - Version tracking in `__init__.py`
  - PyPI package name: `commitguard-cli`
  - Console script entry point: `commitguard`
  - MIT License

### Technical Details

- Uses `GitPython` for Git operations
- Uses `openai` client library with OpenRouter base URL
- System prompt optimized for code review tasks
- Supports Python 3.9+
- Diff diffing against parent commits or show for initial commits
