# CommitGuard

AI-powered CLI that analyzes Git commits for bugs, security issues, and code quality problems. Uses [OpenRouter](https://openrouter.ai/) for access to GPT-4, Claude, Gemini, and 100+ other models.

[GitHub](https://github.com/PierrunoYT/commitguard) · [PyPI](https://pypi.org/project/commitguard-cli/)

## Features

- **Analyze commits** – Detect bugs, security issues, and code quality problems
- **Pre-commit check** – Review staged changes before committing
- **Multi-model** – Use any model on OpenRouter (GPT-4, Claude, Gemini, etc.)
- **Chronological batch analysis** – `analyze -n` processes commits oldest to newest
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
```

When using `analyze -n`, commits are analyzed in chronological order (oldest to newest).

### Options

| Option | Description |
|--------|-------------|
| `-r, --repo PATH` | Path to Git repository (default: current dir) |
| `--api-key KEY` | OpenRouter API key (or `OPENROUTER_API_KEY` env) |
| `-m, --model MODEL` | Model to use (default: `anthropic/claude-sonnet-4.6` or `OPENROUTER_MODEL` env) |

### Model examples

| Model | Use case |
|-------|----------|
| `anthropic/claude-sonnet-4.6` | Strong code analysis (default) |
| `openai/gpt-4o` | Higher quality |
| `openai/gpt-4o-mini` | Fast, cheaper option |
| `google/gemini-pro` | Alternative option |

See [OpenRouter models](https://openrouter.ai/models) for the full list.

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
