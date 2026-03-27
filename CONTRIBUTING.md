# Contributing to CommitGuard

Thanks for helping improve CommitGuard.

## Development setup

1. **Python** 3.9 or newer.

2. Clone the repository and create a virtual environment:

   ```bash
   git clone https://github.com/PierrunoYT/commitguard.git
   cd commitguard
   python -m venv .venv
   ```

3. Activate the venv and install the package in editable mode with dev dependencies:

   ```bash
   # Linux / macOS
   source .venv/bin/activate

   # Windows (PowerShell)
   .\.venv\Scripts\Activate.ps1

   pip install -e ".[dev]"
   ```

4. Run the test suite and linter:

   ```bash
   pytest
   ruff check commitguard tests
   ```

## Pull requests

- Keep changes focused on a single topic when possible.
- Add or update tests for behavior you change.
- Update [CHANGELOG.md](CHANGELOG.md) and [README.md](README.md) when user-facing behavior changes.

## Code style

- Formatting and linting use **Ruff** (see `[tool.ruff]` in `pyproject.toml`).
- Prefer clear names and small, testable functions over large monoliths.
