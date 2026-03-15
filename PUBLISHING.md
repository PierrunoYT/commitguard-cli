# Publishing to PyPI

## Prerequisites

1. Create an account at [pypi.org](https://pypi.org/account/register/)
2. Create an API token at [pypi.org/manage/account/token/](https://pypi.org/manage/account/token/)
3. Install build tools:

```bash
pip install build twine
```

## Development

```bash
python -m commitguard.cli analyze
```

### Clean Build Artifacts

To remove old build artifacts and Python cache files:

```powershell
# PowerShell
Remove-Item -Path ".\dist",".\build","*\.egg-info","*__pycache__","*\.pytest_cache","*\.mypy_cache" -Recurse -Force -ErrorAction SilentlyContinue; Get-ChildItem -Path "." -Recurse -Include "*.pyc","*.pyo","*.so","*.o" -Force | Remove-Item -Force
```

```bash
# Linux / macOS / WSL
find . -type d \( -name "__pycache__" -o -name "build" -o -name "dist" -o -name "*.egg-info" -o -name ".pytest_cache" -o -name ".mypy_cache" \) -exec rm -rf {} + 2>/dev/null
find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.so" -o -name "*.o" \) -delete 2>/dev/null
```

## Steps

1. **Update version** in `pyproject.toml` and `commitguard/__init__.py`

2. **Build the package:**
   ```bash
   python -m build
   ```

3. **Upload to PyPI:**
   ```bash
   twine upload dist/*
   ```
   Use your PyPI username and the API token as password.

4. **Test with TestPyPI first** (optional but recommended):
   ```bash
   twine upload --repository testpypi dist/*
   ```
   Then test install: `pip install -i https://test.pypi.org/simple/ commitguard-cli`

## Notes

- Package name `commitguard-cli` must be unique on PyPI
- Repository: https://github.com/PierrunoYT/commitguard
