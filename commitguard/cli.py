"""CLI for CommitGuard."""

from __future__ import annotations

import os
from pathlib import Path

import click

from .analyzer import analyze_commit, analyze_staged
from . import __version__
from .version import check_for_update


def get_repo_path(path: str | None) -> Path:
    """Resolve repository path. Defaults to current directory."""
    repo_path = Path(path or ".").resolve()
    if not (repo_path / ".git").exists():
        raise click.ClickException(f"Not a Git repository: {repo_path}")
    return repo_path


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="CommitGuard")
@click.pass_context
def main(ctx: click.Context) -> None:
    """AI-powered tool to analyze Git commits for bugs and issues."""
    # Only check for updates when a subcommand is invoked
    if ctx.invoked_subcommand is None:
        return
    try:
        latest = check_for_update()
        if latest:
            click.secho(
                f"Update available: {latest}. Run 'pip install --upgrade commitguard-cli' to update.",
                fg="yellow",
                bold=True,
            )
            click.echo()
    except Exception:
        pass


@main.command()
@click.argument("commit", default="HEAD", required=False)
@click.option(
    "-r",
    "--repo",
    "repo_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to Git repository.",
)
@click.option(
    "-n",
    "--count",
    type=int,
    default=1,
    help="Number of commits to analyze (when using HEAD~n).",
)
@click.option(
    "--api-key",
    envvar="OPENROUTER_API_KEY",
    help="OpenRouter API key (or set OPENROUTER_API_KEY).",
)
@click.option(
    "--model",
    "-m",
    envvar="OPENROUTER_MODEL",
    default="anthropic/claude-sonnet-4.6",
    help="Model to use (e.g. anthropic/claude-sonnet-4.6, openai/gpt-4o, google/gemini-pro). Set OPENROUTER_MODEL for default.",
)
def analyze(
    commit: str,
    repo_path: Path,
    count: int,
    api_key: str | None,
    model: str,
) -> None:
    """Analyze one or more commits for bugs and issues."""
    repo = get_repo_path(str(repo_path))
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise click.ClickException(
            "OpenRouter API key required. Set OPENROUTER_API_KEY or use --api-key."
        )
    if count < 1:
        raise click.ClickException("--count must be at least 1.")

    refs = [commit] if count == 1 else [f"{commit}~{i}" for i in range(count - 1, -1, -1)]
    had_errors = False
    for ref in refs:
        try:
            result = analyze_commit(str(repo), ref, api_key=key, model=model)
            click.echo()
            click.secho(f"Commit: {ref}", fg="cyan", bold=True)
            click.echo(result)
            click.echo()
        except Exception as e:
            click.echo(click.style(f"Error analyzing {ref}: {e}", fg="red"))
            had_errors = True
    if had_errors:
        raise click.ClickException("One or more commits failed to analyze.")


@main.command()
@click.option(
    "-r",
    "--repo",
    "repo_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Path to Git repository.",
)
@click.option(
    "--api-key",
    envvar="OPENROUTER_API_KEY",
    help="OpenRouter API key (or set OPENROUTER_API_KEY).",
)
@click.option(
    "--model",
    "-m",
    envvar="OPENROUTER_MODEL",
    default="anthropic/claude-sonnet-4.6",
    help="Model to use (e.g. anthropic/claude-sonnet-4.6, openai/gpt-4o). Set OPENROUTER_MODEL for default.",
)
def check(
    repo_path: Path,
    api_key: str | None,
    model: str,
) -> None:
    """Analyze staged changes (before commit)."""
    repo = get_repo_path(str(repo_path))
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise click.ClickException(
            "OpenRouter API key required. Set OPENROUTER_API_KEY or use --api-key."
        )

    click.echo("Analyzing staged changes...")
    try:
        result = analyze_staged(str(repo), api_key=key, model=model)
        click.echo(result)
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
