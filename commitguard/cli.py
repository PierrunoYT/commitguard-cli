"""CLI for CommitGuard."""

from __future__ import annotations

import json
import os
from pathlib import Path

import click
from click.core import ParameterSource

from .analyzer import (
    analyze_commit,
    analyze_commit_json,
    analyze_staged,
    analyze_staged_json,
    has_issues_in_text,
    list_commit_shas_in_range,
    load_prompt_file,
)
from . import __version__
from .config import (
    load_resolved_config,
    normalize_choice,
    resolve_path_from_config,
    resolve_repo_from_config,
)
from .errors import AnalysisError
from .version import check_for_update

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
FOCUS_SET = frozenset({"general", "security", "performance", "bugs", "quality"})


def filter_findings_by_severity(
    findings: list[dict], min_severity: str
) -> list[dict]:
    """Filter findings to only include those at or above *min_severity*."""
    threshold = SEVERITY_ORDER.get(min_severity, 0)
    return [
        f
        for f in findings
        if SEVERITY_ORDER.get(f.get("severity", "info"), 0) >= threshold
    ]


def get_repo_path(path: str | None) -> Path:
    """Resolve repository path. Defaults to current directory."""
    repo_path = Path(path or ".").resolve()
    if not (repo_path / ".git").exists():
        raise click.ClickException(f"Not a Git repository: {repo_path}")
    return repo_path


def apply_user_config(
    ctx: click.Context,
    cfg: dict,
    base_dir: Path | None,
    *,
    model: str,
    repo_path: Path,
    output_format: str,
    severity: str,
    fail_on: str,
    focus: str,
    prompt_file: Path | None,
    no_cache: bool,
) -> tuple[str, Path, str, str, str, str, Path | None, bool]:
    """Apply discovered config when the user left options at CLI defaults."""
    src = ctx.get_parameter_source

    def is_default(name: str) -> bool:
        return src(name) == ParameterSource.DEFAULT

    try:
        if is_default("model") and cfg.get("model"):
            model = str(cfg["model"])
        if is_default("repo_path") and cfg.get("repo"):
            repo_path = resolve_repo_from_config(str(cfg["repo"]), base_dir)
        if is_default("output_format") and cfg.get("format") is not None:
            output_format = normalize_choice(
                cfg["format"], frozenset({"text", "json"}), "format"
            )
        if is_default("severity") and cfg.get("severity") is not None:
            severity = normalize_choice(
                cfg["severity"],
                frozenset({"info", "warning", "critical"}),
                "severity",
            )
        if is_default("fail_on") and cfg.get("fail_on") is not None:
            fail_on = normalize_choice(
                cfg["fail_on"],
                frozenset({"info", "warning", "critical"}),
                "fail_on",
            )
        if is_default("focus") and cfg.get("focus") is not None:
            focus = normalize_choice(cfg["focus"], FOCUS_SET, "focus")
        if is_default("prompt_file") and cfg.get("prompt_file"):
            prompt_file = resolve_path_from_config(str(cfg["prompt_file"]), base_dir)
        if is_default("no_cache") and cfg.get("no_cache") is True:
            no_cache = True
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    return model, repo_path, output_format, severity, fail_on, focus, prompt_file, no_cache


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
@click.pass_context
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
    help="Number of commits to analyze (when using HEAD~n). Not used with --from/--to.",
)
@click.option(
    "--from",
    "from_ref",
    default=None,
    help="Range start ref (use with --to). Analyzes commits in Git range from..to.",
)
@click.option(
    "--to",
    "to_ref",
    default=None,
    help="Range end ref (use with --from).",
)
@click.option(
    "--api-key",
    envvar="OPENROUTER_API_KEY",
    help="OpenRouter API key (or set OPENROUTER_API_KEY).",
)
@click.option(
    "--config",
    "config_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="TOML config file (otherwise: .commitguardrc, pyproject [tool.commitguard], or COMMITGUARD_CONFIG).",
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
@click.option(
    "--severity",
    type=click.Choice(["info", "warning", "critical"], case_sensitive=False),
    default="info",
    show_default=True,
    help="Minimum severity to include in JSON output.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["info", "warning", "critical"], case_sensitive=False),
    default="warning",
    show_default=True,
    help="Minimum severity that triggers a non-zero exit code (JSON only).",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Save output to a file (in addition to stdout).",
)
@click.option(
    "--focus",
    type=click.Choice(
        ["general", "security", "performance", "bugs", "quality"],
        case_sensitive=False,
    ),
    default="general",
    show_default=True,
    help="Scope the review toward security, performance, bugs, quality, or general.",
)
@click.option(
    "--prompt-file",
    "prompt_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Replace the system prompt with the contents of this UTF-8 text file.",
)
@click.option(
    "--no-cache",
    "no_cache",
    is_flag=True,
    default=False,
    help="Do not read or write .commitguard_cache in the repository.",
)
def analyze(
    ctx: click.Context,
    commit: str,
    repo_path: Path,
    count: int,
    from_ref: str | None,
    to_ref: str | None,
    api_key: str | None,
    config_file: Path | None,
    model: str,
    output_format: str,
    severity: str,
    fail_on: str,
    output_file: Path | None,
    focus: str,
    prompt_file: Path | None,
    no_cache: bool,
) -> None:
    """Analyze one or more commits for bugs and issues."""
    cfg, base_dir = load_resolved_config(config_file)
    (
        model,
        repo_path,
        output_format,
        severity,
        fail_on,
        focus,
        prompt_file,
        no_cache,
    ) = apply_user_config(
        ctx,
        cfg,
        base_dir,
        model=model,
        repo_path=repo_path,
        output_format=output_format,
        severity=severity,
        fail_on=fail_on,
        focus=focus,
        prompt_file=prompt_file,
        no_cache=no_cache,
    )
    repo = get_repo_path(str(repo_path))
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise click.ClickException(
            "OpenRouter API key required. Set OPENROUTER_API_KEY or use --api-key."
        )
    if count < 1:
        raise click.ClickException("--count must be at least 1.")

    range_mode = from_ref is not None and to_ref is not None
    if (from_ref is None) ^ (to_ref is None):
        raise click.ClickException(
            "Specify both --from and --to for a commit range, or neither."
        )
    if range_mode and ctx.get_parameter_source("count") != ParameterSource.DEFAULT:
        raise click.ClickException("Do not combine --count with --from/--to.")
    if range_mode and ctx.get_parameter_source("commit") != ParameterSource.DEFAULT:
        raise click.ClickException("Do not pass a COMMIT argument when using --from/--to.")

    prompt_override: str | None = None
    if prompt_file is not None:
        try:
            prompt_override = load_prompt_file(prompt_file)
        except AnalysisError as e:
            raise click.ClickException(str(e)) from e
    use_cache = not no_cache

    if range_mode:
        try:
            refs = list_commit_shas_in_range(str(repo), from_ref, to_ref)
        except AnalysisError as e:
            raise click.ClickException(str(e)) from e
        if not refs:
            raise click.ClickException(
                f"No commits in range {from_ref!r}..{to_ref!r} (exclusive start, inclusive end of feature tip)."
            )
    else:
        refs = (
            [commit]
            if count == 1
            else [f"{commit}~{i}" for i in range(count - 1, -1, -1)]
        )
    had_errors = False
    issues_found = False
    json_results: list[dict] = []
    text_parts: list[str] = []
    for ref in refs:
        try:
            if output_format == "json":
                result = analyze_commit_json(
                    str(repo),
                    ref,
                    api_key=key,
                    model=model,
                    focus=focus,
                    system_prompt_override=prompt_override,
                    use_cache=use_cache,
                )
                json_results.append({"commit": ref, **result})
                if result.get("findings"):
                    issues_found = True
            else:
                result = analyze_commit(
                    str(repo),
                    ref,
                    api_key=key,
                    model=model,
                    focus=focus,
                    system_prompt_override=prompt_override,
                    use_cache=use_cache,
                )
                click.echo()
                click.secho(f"Commit: {ref}", fg="cyan", bold=True)
                click.echo(result)
                click.echo()
                text_parts.append(f"Commit: {ref}\n{result}\n")
                if has_issues_in_text(result):
                    issues_found = True
        except Exception as e:
            click.echo(click.style(f"Error analyzing {ref}: {e}", fg="red"))
            had_errors = True
    if had_errors:
        raise click.ClickException("One or more commits failed to analyze.")
    if output_format == "json":
        for entry in json_results:
            if "findings" in entry:
                entry["findings"] = filter_findings_by_severity(
                    entry["findings"], severity
                )
        output_text = json.dumps(
            {
                "format_version": "1",
                "results": json_results,
            },
            indent=2,
        )
        click.echo(output_text)
        if output_file:
            output_file.write_text(output_text, encoding="utf-8")
        fail_threshold = SEVERITY_ORDER[fail_on]
        has_failing = any(
            SEVERITY_ORDER.get(f.get("severity", "info"), 0) >= fail_threshold
            for entry in json_results
            for f in entry.get("findings", [])
        )
        if has_failing:
            raise click.ClickException("Issues found during analysis.")
    else:
        if output_file:
            output_file.write_text("\n".join(text_parts), encoding="utf-8")
        if issues_found:
            raise click.ClickException("Issues found during analysis.")


@main.command()
@click.pass_context
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
    "--config",
    "config_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="TOML config file (otherwise: .commitguardrc, pyproject [tool.commitguard], or COMMITGUARD_CONFIG).",
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
@click.option(
    "--severity",
    type=click.Choice(["info", "warning", "critical"], case_sensitive=False),
    default="info",
    show_default=True,
    help="Minimum severity to include in JSON output.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["info", "warning", "critical"], case_sensitive=False),
    default="warning",
    show_default=True,
    help="Minimum severity that triggers a non-zero exit code (JSON only).",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Save output to a file (in addition to stdout).",
)
@click.option(
    "--focus",
    type=click.Choice(
        ["general", "security", "performance", "bugs", "quality"],
        case_sensitive=False,
    ),
    default="general",
    show_default=True,
    help="Scope the review toward security, performance, bugs, quality, or general.",
)
@click.option(
    "--prompt-file",
    "prompt_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Replace the system prompt with the contents of this UTF-8 text file.",
)
@click.option(
    "--no-cache",
    "no_cache",
    is_flag=True,
    default=False,
    help="Do not read or write .commitguard_cache in the repository.",
)
def check(
    ctx: click.Context,
    repo_path: Path,
    api_key: str | None,
    config_file: Path | None,
    model: str,
    output_format: str,
    severity: str,
    fail_on: str,
    output_file: Path | None,
    focus: str,
    prompt_file: Path | None,
    no_cache: bool,
) -> None:
    """Analyze staged changes (before commit)."""
    cfg, base_dir = load_resolved_config(config_file)
    (
        model,
        repo_path,
        output_format,
        severity,
        fail_on,
        focus,
        prompt_file,
        no_cache,
    ) = apply_user_config(
        ctx,
        cfg,
        base_dir,
        model=model,
        repo_path=repo_path,
        output_format=output_format,
        severity=severity,
        fail_on=fail_on,
        focus=focus,
        prompt_file=prompt_file,
        no_cache=no_cache,
    )
    repo = get_repo_path(str(repo_path))
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise click.ClickException(
            "OpenRouter API key required. Set OPENROUTER_API_KEY or use --api-key."
        )

    prompt_override: str | None = None
    if prompt_file is not None:
        try:
            prompt_override = load_prompt_file(prompt_file)
        except AnalysisError as e:
            raise click.ClickException(str(e)) from e
    use_cache = not no_cache

    click.echo("Analyzing staged changes...")
    try:
        if output_format == "json":
            result = analyze_staged_json(
                str(repo),
                api_key=key,
                model=model,
                focus=focus,
                system_prompt_override=prompt_override,
                use_cache=use_cache,
            )
            if "findings" in result:
                result["findings"] = filter_findings_by_severity(
                    result["findings"], severity
                )
            output_text = json.dumps(
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
            click.echo(output_text)
            if output_file:
                output_file.write_text(output_text, encoding="utf-8")
            fail_threshold = SEVERITY_ORDER[fail_on]
            has_failing = any(
                SEVERITY_ORDER.get(f.get("severity", "info"), 0) >= fail_threshold
                for f in result.get("findings", [])
            )
            if has_failing:
                raise click.ClickException("Issues found in staged changes.")
            return

        result = analyze_staged(
            str(repo),
            api_key=key,
            model=model,
            focus=focus,
            system_prompt_override=prompt_override,
            use_cache=use_cache,
        )
        click.echo(result)
        if output_file:
            output_file.write_text(result, encoding="utf-8")
        if has_issues_in_text(result) and result != "No staged changes to analyze.":
            raise click.ClickException("Issues found in staged changes.")
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
