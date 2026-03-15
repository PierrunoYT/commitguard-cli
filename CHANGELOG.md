# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
