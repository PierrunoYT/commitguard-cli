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

Defaults for `model`, `repo`, `format`, `severity`, and `fail-on` can be set in TOML (CLI flags and environment variables still override when you pass them explicitly).

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
```

When using `analyze -n`, commits are analyzed in chronological order (oldest to newest).

### Options

| Option | Description |
|--------|-------------|
| `-r, --repo PATH` | Path to Git repository (default: current dir) |
| `--api-key KEY` | OpenRouter API key (or `OPENROUTER_API_KEY` env) |
| `--config PATH` | Explicit TOML config file (see [Config files](#config-files)) |
| `-m, --model MODEL` | Model to use (default: `anthropic/claude-sonnet-4.6` or `OPENROUTER_MODEL` env) |
| `--format [text|json]` | Output format (default: `text`) |
| `--severity [info|warning|critical]` | Minimum severity to include in JSON output (default: `info`) |
| `--fail-on [info|warning|critical]` | Minimum severity that triggers a non-zero exit code, JSON only (default: `warning`) |
| `-o, --output FILE` | Save output to a file (in addition to stdout) |

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

## Changelog

[CHANGELOG.md](CHANGELOG.md)
