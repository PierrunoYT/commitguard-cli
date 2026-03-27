# CommitGuard

AI-powered CLI that analyzes Git commits for bugs, security issues, and code quality problems. Uses [OpenRouter](https://openrouter.ai/) for access to GPT-4, Claude, Gemini, and 100+ other models.

[GitHub](https://github.com/PierrunoYT/commitguard) · [PyPI](https://pypi.org/project/commitguard-cli/)

## Features

- **Analyze commits** – Detect bugs, security issues, and code quality problems
- **Pre-commit check** – Review staged changes before committing
- **Multi-model** – Use any model on OpenRouter (GPT-4, Claude, Gemini, etc.)
- **Chronological batch analysis** – `analyze -n` processes commits oldest to newest
- **Structured output** – `--format json` for machine-readable CI integrations
- **Severity filtering** – `--severity` to filter findings, `--fail-on` to control exit codes
- **CI-friendly exit codes** – exits non-zero when issues are detected
- **Output to file** – `--output` to save results to a file
- **Config files** – `.commitguardrc` or `[tool.commitguard]` in `pyproject.toml` for defaults
- **Focus & prompts** – `--focus` to steer reviews; `--prompt-file` or config for a custom system prompt
- **Commit ranges** – `analyze --from main --to feature` (Git `from..to` range, chronological)
- **Local cache** – `.commitguard_cache/` avoids repeat API calls for the same commit and settings (`--no-cache` to skip)
- **Python API** – Import `commitguard` and call analyzer functions from code (see [Library usage](#library-usage))
- **Quiet base command** – Update checks run only when a subcommand is invoked
- **Simple CLI** – One command, clear output

## Requirements

- Python 3.9+
- [OpenRouter](https://openrouter.ai/) API key

## Installation

```bash
pip install commitguard-cli
```

From source:

```bash
git clone https://github.com/PierrunoYT/commitguard.git
cd commitguard
pip install -e .
```

## Configuration

Get an API key at [openrouter.ai/keys](https://openrouter.ai/keys):

```bash
# Linux / macOS
export OPENROUTER_API_KEY=sk-or-...

# Windows (PowerShell)
$env:OPENROUTER_API_KEY = "sk-or-..."
```

Optional - default model (otherwise `anthropic/claude-sonnet-4.6`):

```bash
export OPENROUTER_MODEL=anthropic/claude-sonnet-4.6   # Linux/macOS
$env:OPENROUTER_MODEL = "anthropic/claude-sonnet-4.6" # Windows
```

### Config files

Defaults for `model`, `repo`, `format`, `severity`, `fail-on`, `focus`, `prompt_file`, and `no_cache` can be set in TOML (CLI flags and environment variables still override when you pass them explicitly).

**Resolution order**

1. `--config /path/to/file.toml` if you pass it
2. `COMMITGUARD_CONFIG` environment variable (path to a TOML file)
3. Nearest `.commitguardrc` when walking up from the current directory
4. Otherwise the nearest `pyproject.toml` with a `[tool.commitguard]` section

**`.commitguardrc`** (repository root or any parent directory):

```toml
model = "anthropic/claude-sonnet-4.6"
repo = "."
format = "json"
severity = "warning"
fail_on = "critical"
focus = "security"
prompt_file = "prompts/review.txt"
no_cache = false
```

Paths in `repo` are resolved relative to the directory that contains the config file.

**`pyproject.toml`**:

```toml
[tool.commitguard]
model = "anthropic/claude-sonnet-4.6"
format = "text"
```

## Usage

```bash
# Analyze last commit
commitguard analyze

# Analyze specific commit
commitguard analyze abc123

# Analyze last 5 commits
commitguard analyze -n 5

# Analyze staged changes (before commit)
commitguard check

# Use a different model
commitguard analyze --model anthropic/claude-sonnet-4.6
commitguard analyze -m google/gemini-pro

# JSON output for automation
commitguard analyze --format json
commitguard check --format json

# Filter by severity (JSON only)
commitguard analyze --format json --severity warning
commitguard analyze --format json --fail-on critical

# Save output to a file
commitguard analyze --output report.txt
commitguard analyze --format json -o results.json

# Steer the review (analyze or check)
commitguard analyze --focus security
commitguard check --focus performance

# Custom system prompt (UTF-8 text file)
commitguard analyze --prompt-file ./my-system-prompt.txt

# Analyze commits on a branch not in main (Git range main..feature)
commitguard analyze --from main --to feature

# Skip reading/writing .commitguard_cache in the repo
commitguard analyze --no-cache HEAD
```

When using `analyze -n`, commits are analyzed in chronological order (oldest to newest). Do not combine `-n`/`COMMIT` with `--from`/`--to`.

### Options (`analyze`)

| Option | Description |
|--------|-------------|
| `COMMIT` | Starting commit (default `HEAD`). Ignored when using `--from`/`--to`. |
| `-r, --repo PATH` | Path to Git repository (default: current dir) |
| `-n, --count N` | Analyze N commits walking back from `COMMIT` (not used with `--from`/`--to`) |
| `--from REF` | Range start (use with `--to`; Git range `from..to`) |
| `--to REF` | Range end (use with `--from`) |
| `--api-key KEY` | OpenRouter API key (or `OPENROUTER_API_KEY` env) |
| `--config PATH` | Explicit TOML config file (see [Config files](#config-files)) |
| `-m, --model MODEL` | Model to use (default: `anthropic/claude-sonnet-4.6` or `OPENROUTER_MODEL` env) |
| `--format [text|json]` | Output format (default: `text`) |
| `--severity [info|warning|critical]` | Minimum severity to include in JSON output (default: `info`) |
| `--fail-on [info|warning|critical]` | Minimum severity that triggers a non-zero exit code, JSON only (default: `warning`) |
| `-o, --output FILE` | Save output to a file (in addition to stdout) |
| `--focus FOCUS` | `general`, `security`, `performance`, `bugs`, or `quality` |
| `--prompt-file PATH` | Replace the built-in system prompt with this UTF-8 file |
| `--no-cache` | Do not use `.commitguard_cache/` |

### Options (`check`)

Same as `analyze` except there is no `COMMIT`, `-n`, `--from`, or `--to`.

### Cache

Successful analyses are stored under **`.commitguard_cache/`** in the Git repository (text and JSON cached separately). Staged runs are keyed by a hash of the staged diff. Delete that folder or pass **`--no-cache`** to force a fresh API call. Add `.commitguard_cache/` to `.gitignore` if you use the tool inside a project (the published CLI’s own repo already ignores it).

### JSON output schema

`--format json` returns:

```json
{
  "format_version": "1",
  "results": [
    {
      "commit": "HEAD",
      "summary": "string",
      "findings": [
        {
          "severity": "critical | warning | info",
          "title": "string",
          "description": "string",
          "file": "path/or/null"
        }
      ]
    }
  ]
}
```

### Exit codes

- Returns non-zero when analysis finds issues.
- Returns non-zero on command/runtime errors.
- Returns zero only when no issues are detected.

### Model examples

| Model | Use case |
|-------|----------|
| `anthropic/claude-sonnet-4.6` | Strong code analysis (default) |
| `openai/gpt-4o` | Higher quality |
| `openai/gpt-4o-mini` | Fast, cheaper option |
| `google/gemini-pro` | Alternative option |

See [OpenRouter models](https://openrouter.ai/models) for the full list.

## Library usage

Install the package, then import the same functions the CLI uses:

```python
from commitguard import (
    analyze_commit,
    analyze_commit_json,
    analyze_staged,
    analyze_staged_json,
    build_effective_system_prompt,
    list_commit_shas_in_range,
    load_prompt_file,
)

# Markdown review of HEAD
text = analyze_commit(
    "/path/to/repo",
    "HEAD",
    api_key="sk-or-...",
    focus="security",
    use_cache=True,
)

# Structured JSON for one commit
data = analyze_commit_json(
    "/path/to/repo",
    "abc123",
    api_key="sk-or-...",
    model="anthropic/claude-sonnet-4.6",
)

# Commits in Git range main..feature (oldest first)
shas = list_commit_shas_in_range("/path/to/repo", "main", "feature")
```

`AnalysisError` is raised for invalid API responses, configuration, or Git errors. See docstrings on these functions for parameters.

## CI and pre-commit

Example files live under [`examples/`](examples/):

| File | Purpose |
|------|---------|
| [`examples/github-actions.yml`](examples/github-actions.yml) | GitHub Actions: analyze `HEAD` after checkout (set `OPENROUTER_API_KEY` as a repo secret) |
| [`examples/gitlab-ci.yml`](examples/gitlab-ci.yml) | GitLab CI job snippet |
| [`examples/pre-commit-config.yaml`](examples/pre-commit-config.yaml) | Local [pre-commit](https://pre-commit.com/) hook running `commitguard check` on staged changes |

In CI, `commitguard analyze HEAD` fits push and pull-request pipelines. For a gate on **staged** edits before you commit, use `commitguard check` (for example via pre-commit) so the model sees your index, not the remote history.

## Troubleshooting

| Error | Solution |
|-------|----------|
| Invalid or missing API key | Set `OPENROUTER_API_KEY` or use `--api-key`. Get a key at [openrouter.ai/keys](https://openrouter.ai/keys) |
| Model not found | Use the full model ID (e.g. `anthropic/claude-sonnet-4.6`). Check [openrouter.ai/models](https://openrouter.ai/models) |
| Rate limit exceeded | Wait and retry, or switch to a different model |
| Request timed out | Retry the command, or use a faster/smaller model |
| Service unavailable | OpenRouter may be down; try again later |

**Security:** Never commit your API key. Use environment variables or `--api-key` at runtime.

## License

[MIT](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and pull request expectations.

## Changelog

[CHANGELOG.md](CHANGELOG.md)
