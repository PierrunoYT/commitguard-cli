"""CLI for CommitGuard."""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from .analyzer import (
    analyze_commit,
    analyze_commit_json,
    analyze_staged,
    analyze_staged_json,
    has_issues_in_text,
)
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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
def analyze(
    commit: str,
    repo_path: Path,
    count: int,
    api_key: str | None,
    model: str,
    output_format: str,
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
    issues_found = False
    json_results: list[dict] = []
    for ref in refs:
        try:
            if output_format == "json":
                result = analyze_commit_json(str(repo), ref, api_key=key, model=model)
                json_results.append({"commit": ref, **result})
                if result.get("findings"):
                    issues_found = True
            else:
                result = analyze_commit(str(repo), ref, api_key=key, model=model)
                click.echo()
                click.secho(f"Commit: {ref}", fg="cyan", bold=True)
                click.echo(result)
                click.echo()
                if has_issues_in_text(result):
                    issues_found = True
        except Exception as e:
            click.echo(click.style(f"Error analyzing {ref}: {e}", fg="red"))
            had_errors = True
    if had_errors:
        raise click.ClickException("One or more commits failed to analyze.")
    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "format_version": "1",
                    "results": json_results,
                },
                indent=2,
            )
        )
    if issues_found:
        raise click.ClickException("Issues found during analysis.")


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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
def check(
    repo_path: Path,
    api_key: str | None,
    model: str,
    output_format: str,
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
        if output_format == "json":
            result = analyze_staged_json(str(repo), api_key=key, model=model)
            click.echo(
                json.dumps(
                    {
                        "format_version": "1",
                        "results": [
                            {
                                "commit": "staged",
                                **result,
                            }
                        ],
                    },
                    indent=2,
                )
            )
            if result.get("findings"):
                raise click.ClickException("Issues found in staged changes.")
            return

        result = analyze_staged(str(repo), api_key=key, model=model)
        click.echo(result)
        if has_issues_in_text(result) and result != "No staged changes to analyze.":
            raise click.ClickException("Issues found in staged changes.")
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
