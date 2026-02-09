"""Command-line interface for causaliq-workflow."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click


def _log_cli_message(level: str, message: str) -> None:
    """Log CLI message with standardised format."""
    if level != "none":
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"{timestamp} [causaliq-workflow] {message}")


def _log_cli_error(message: str) -> None:
    """Log CLI error message with standardised format."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    click.echo(f"{timestamp} [causaliq-workflow] ERROR {message}", err=True)


# ============================================================================
# Main CLI group
# ============================================================================


@click.group(name="causaliq-workflow", invoke_without_command=True)
@click.version_option(version="0.2.0")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """CausalIQ Workflow - Execute and manage causal discovery workflows.

    Use 'cqwork run' to execute workflows.
    Use 'cqwork export_cache' to export cache entries.
    Use 'cqwork import_cache' to import cache entries.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ============================================================================
# Run command (workflow execution)
# ============================================================================


@cli.command(name="run")
@click.argument(
    "workflow_file",
    metavar="WORKFLOW_FILE",
    required=True,
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--mode",
    default="dry-run",
    type=click.Choice(["dry-run", "run"]),
    help="Execution mode: 'dry-run' validates and previews (default), "
    "'run' executes workflow",
)
@click.option(
    "--log-level",
    default="summary",
    type=click.Choice(["none", "summary", "all"]),
    help="Logging level for output",
)
def run_workflow(workflow_file: Path, mode: str, log_level: str) -> None:
    """Execute a CausalIQ workflow file.

    WORKFLOW_FILE is the path to a YAML workflow file to execute.

    Examples:

        causaliq-workflow run experiment.yml

        causaliq-workflow run experiment.yml --mode=run

        causaliq-workflow run experiment.yml --mode=dry-run --log-level=all
    """
    try:
        from causaliq_workflow.workflow import WorkflowExecutor

        executor = WorkflowExecutor()

        _log_cli_message(log_level, f"LOADING workflow from: {workflow_file}")

        try:
            workflow = executor.parse_workflow(str(workflow_file))
        except FileNotFoundError:
            _log_cli_error(f"Workflow file not found: {workflow_file}")
            sys.exit(1)
        except Exception as e:
            if "yaml" in str(e).lower() or "parsing" in str(e).lower():
                _log_cli_error(f"Invalid YAML in workflow file: {e}")
            else:
                _log_cli_error(f"Failed to parse workflow: {e}")
            sys.exit(1)

        _log_cli_message(
            log_level, "VALIDATING workflow syntax and parameters..."
        )
        try:
            executor.execute_workflow(workflow, mode="validate")
            _log_cli_message(log_level, "VALIDATED workflow successfully")
        except Exception as e:
            _log_cli_error(f"Workflow validation failed: {e}")
            sys.exit(1)

        def log_step_execution(
            action_name: str, step_name: str, status: str
        ) -> None:
            """Log step execution in real-time."""
            if log_level == "all":
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                click.echo(
                    f"{timestamp} [{action_name}] STEP {status} {step_name}"
                )

        try:
            _log_cli_message(
                log_level, f"EXECUTING workflow in {mode} mode..."
            )
            results = executor.execute_workflow(
                workflow, mode=mode, step_logger=log_step_execution
            )
        except Exception as e:
            _log_cli_error(f"Workflow execution failed: {e}")
            sys.exit(1)

        _report_results(results, workflow, mode, log_level)

    except KeyboardInterrupt:
        _log_cli_error("Workflow execution interrupted by user")
        sys.exit(130)
    except ImportError as e:
        _log_cli_error(f"Missing required dependencies: {e}")
        sys.exit(1)


def _report_results(
    results: List[Dict[str, Any]],
    workflow: Dict[str, Any],
    mode: str,
    log_level: str,
) -> None:
    """Report workflow execution results following standardised format."""
    if log_level == "none":
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not results:
        click.echo(
            f"{timestamp} [causaliq-workflow] COMPLETED workflow with 0 jobs"
        )
        return

    total_steps = sum(len(result.get("steps", {})) for result in results)

    if log_level == "all":
        for i, result in enumerate(results):
            steps = result.get("steps", {})
            click.echo(
                f"{timestamp} [causaliq-workflow] JOB {i + 1} completed "
                f"{len(steps)} step(s)"
            )

    click.echo(
        f"{timestamp} [causaliq-workflow] COMPLETED workflow with "
        f"{len(results)} job(s) ({total_steps} steps)"
    )


# ============================================================================
# Cache export command
# ============================================================================


@cli.command(name="export_cache")
@click.option(
    "--cache",
    "-c",
    "cache_file",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to WorkflowCache database file (.db) to export from.",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="Output directory or .zip file path for exported entries.",
)
@click.option(
    "--entry-type",
    "-t",
    default="graph",
    help="Entry type to export (default: graph).",
)
@click.option(
    "--matrix-keys",
    "-k",
    default=None,
    help="Comma-separated list of matrix variable names for directory "
    "hierarchy order (default: alphabetical).",
)
def export_cache(
    cache_file: Path,
    output: Path,
    entry_type: str,
    matrix_keys: Optional[str],
) -> None:
    """Export cache entries to directory or zip file.

    Reads entries from a WorkflowCache database and exports them to a
    hierarchical directory structure based on matrix variable values.
    Each entry is exported as a pair of files: <timestamp>.graphml and
    <timestamp>.json (metadata).

    Examples:

        cqwork export_cache -c cache.db -o ./results

        cqwork export_cache -c cache.db -o results.zip

        cqwork export_cache -c cache.db -o ./out -k dataset,algorithm
    """
    try:
        from causaliq_core.cache.encoders import JsonEncoder

        from causaliq_workflow.cache import WorkflowCache

        keys_list: Optional[List[str]] = None
        if matrix_keys:
            keys_list = [k.strip() for k in matrix_keys.split(",")]

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(
            f"{timestamp} [causaliq-workflow] EXPORTING cache: {cache_file}"
        )

        with WorkflowCache(cache_file) as cache:
            if not cache.has_encoder("json"):
                cache.register_encoder("json", JsonEncoder())

            entry_count = cache.entry_count(entry_type)
            if entry_count == 0:
                click.echo(
                    f"{timestamp} [causaliq-workflow] "
                    f"No entries of type '{entry_type}' found in cache"
                )
                sys.exit(0)

            click.echo(
                f"{timestamp} [causaliq-workflow] "
                f"Found {entry_count} entries of type '{entry_type}'"
            )

            try:
                exported = cache.export(output, entry_type, keys_list)
                click.echo(
                    f"{timestamp} [causaliq-workflow] "
                    f"EXPORTED {exported} entries to: {output}"
                )
            except KeyError as e:
                _log_cli_error(f"Export failed: {e}")
                sys.exit(1)
            except Exception as e:
                _log_cli_error(f"Export failed: {e}")
                sys.exit(1)

    except FileNotFoundError:  # pragma: no cover
        # Defensive: Click validates exists=True, but kept for safety
        _log_cli_error(f"Cache file not found: {cache_file}")
        sys.exit(1)
    except KeyboardInterrupt:
        _log_cli_error("Export interrupted by user")
        sys.exit(130)
    except ImportError as e:
        _log_cli_error(f"Missing required dependencies: {e}")
        sys.exit(1)


@cli.command(name="import_cache")
@click.option(
    "--input",
    "-i",
    "input_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to exported directory or .zip file to import from.",
)
@click.option(
    "--cache",
    "-c",
    "cache_file",
    required=True,
    type=click.Path(path_type=Path),
    help="Destination WorkflowCache database file (.db).",
)
@click.option(
    "--entry-type",
    "-t",
    default="graph",
    help="Entry type to import (default: graph).",
)
def import_cache(
    input_path: Path,
    cache_file: Path,
    entry_type: str,
) -> None:
    """Import cache entries from directory or zip file.

    Reads entries previously exported by 'export_cache' and stores them
    into the specified cache database. Creates the cache file if it
    does not exist.

    Examples:

        cqwork import_cache -i ./results -c cache.db

        cqwork import_cache -i results.zip -c cache.db

        cqwork import_cache -i ./out -c cache.db -t graph
    """
    try:
        from causaliq_core.cache.encoders import JsonEncoder

        from causaliq_workflow.cache import WorkflowCache

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(
            f"{timestamp} [causaliq-workflow] IMPORTING from: {input_path}"
        )

        with WorkflowCache(cache_file) as cache:
            if not cache.has_encoder("json"):
                cache.register_encoder("json", JsonEncoder())

            try:
                imported = cache.import_entries(input_path, entry_type)
                click.echo(
                    f"{timestamp} [causaliq-workflow] "
                    f"IMPORTED {imported} entries into: {cache_file}"
                )
            except KeyError as e:
                _log_cli_error(f"Import failed: {e}")
                sys.exit(1)
            except Exception as e:
                _log_cli_error(f"Import failed: {e}")
                sys.exit(1)

    except FileNotFoundError:  # pragma: no cover
        # Defensive: Click validates exists=True, but kept for safety
        _log_cli_error(f"Input path not found: {input_path}")
        sys.exit(1)
    except KeyboardInterrupt:
        _log_cli_error("Import interrupted by user")
        sys.exit(130)
    except ImportError as e:
        _log_cli_error(f"Missing required dependencies: {e}")
        sys.exit(1)


def main() -> None:
    """Entry point for the CLI."""
    cli(prog_name="causaliq-workflow")


if __name__ == "__main__":  # pragma: no cover
    main()
