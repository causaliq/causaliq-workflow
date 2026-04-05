"""Command-line interface for causaliq-workflow."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import click

from . import __version__


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
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """CausalIQ Workflow - Execute and manage causal discovery workflows.

    Use 'cqwork run' to execute workflows.
    Use 'cqwork export-cache' to export cache entries.
    Use 'cqwork import-cache' to import cache entries.
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
    type=click.Choice(["dry-run", "run", "force"]),
    help="Execution mode: 'dry-run' validates and previews (default), "
    "'run' executes with conservative skip, 'force' executes without skip",
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
        from causaliq_workflow.workflow import (
            WorkflowExecutionError,
            WorkflowExecutor,
        )

        executor = WorkflowExecutor()

        _log_cli_message(log_level, f"LOADING workflow from: {workflow_file}")

        try:
            workflow = executor.parse_workflow(str(workflow_file))
        except FileNotFoundError:
            _log_cli_error(f"Workflow file not found: {workflow_file}")
            sys.exit(1)
        except WorkflowExecutionError as e:
            # Our own errors - print directly
            _log_cli_error(str(e))
            sys.exit(1)
        except Exception as e:
            if "yaml" in str(e).lower():
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
            _log_cli_error(str(e))
            sys.exit(1)

        def log_step_execution(
            action_method: str,
            step_name: str,
            status: str,
            matrix_values: Dict[str, Any],
        ) -> None:
            """Log step execution in real-time."""
            if log_level == "all":
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Extract UPDATE step entry counts if present
                would_process = matrix_values.pop(
                    "_entries_would_process", None
                )
                would_skip = matrix_values.pop("_entries_would_skip", None)

                # Format matrix values as [key=value, ...]
                if matrix_values:
                    matrix_str = ", ".join(
                        f"{k}={v}" for k, v in matrix_values.items()
                    )
                    matrix_part = f" [{matrix_str}]"
                else:
                    matrix_part = ""

                # Add entry counts for UPDATE steps
                entry_info = ""
                if would_process is not None or would_skip is not None:
                    parts = []
                    if would_process:
                        parts.append(f"{would_process} to process")
                    if would_skip:
                        parts.append(f"{would_skip} to skip")
                    if parts:
                        entry_info = f" ({', '.join(parts)})"

                click.echo(
                    f"{timestamp} [{action_method}] {status:12} "
                    f"{step_name}{matrix_part}{entry_info}"
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
        click.echo(f"{timestamp} [causaliq-workflow] COMPLETED 0 steps")
        return

    # Count step statuses across all jobs
    executed = 0
    skipped = 0
    forced = 0
    would_execute = 0
    would_skip = 0
    failed = 0

    # Track new-entry vs update counts for summary detail
    new_entries = 0
    updates = 0

    # Collect error messages
    error_messages: List[str] = []

    for result in results:
        for step_name, step_result in result.get("steps", {}).items():
            status = step_result.get("status", "unknown")
            if status == "success":
                if mode == "force":
                    forced += 1
                else:
                    executed += 1
                # Track new entries vs updates
                eu = step_result.get("entries_updated", 0)
                if eu > 0:
                    updates += eu
                else:
                    new_entries += 1
            elif status == "skipped":
                skipped += 1
            elif status == "would_execute":
                would_execute += 1
                wp = step_result.get("would_process", 0)
                ws = step_result.get("would_skip", 0)
                if wp > 0 or ws > 0:
                    # UPDATE step with sub-entries
                    updates += wp
                else:
                    # CREATE / AGGREGATE step
                    new_entries += 1
            elif status == "would_skip":
                would_skip += 1
            elif status in ("error", "failed"):
                failed += 1
                # Collect error messages from step
                step_errors = step_result.get("errors", [])
                for err in step_errors:
                    error_messages.append(f"  {step_name}: {err}")

    total = executed + skipped + forced + would_execute + would_skip + failed

    # Build summary parts
    parts = []
    if mode == "dry-run":
        if would_execute > 0:
            parts.append(f"{would_execute} would execute")
        if would_skip > 0:
            parts.append(f"{would_skip} would skip")
    else:
        if executed > 0:
            parts.append(f"{executed} executed")
        if skipped > 0:
            parts.append(f"{skipped} skipped")
        if forced > 0:
            parts.append(f"{forced} forced")
    if failed > 0:
        parts.append(f"{failed} failed")

    summary = ", ".join(parts) if parts else "0 steps"

    # Build detail breakdown (new entries vs updates)
    detail = ""
    if new_entries > 0 or updates > 0:
        detail_parts = []
        if new_entries > 0:
            detail_parts.append(
                f"{new_entries} new entr"
                f"{'ies' if new_entries != 1 else 'y'}"
            )
        if updates > 0:
            detail_parts.append(
                f"{updates} update{'s' if updates != 1 else ''}"
            )
        detail = f" ({', '.join(detail_parts)})"

    click.echo(
        f"{timestamp} [causaliq-workflow] COMPLETED {total} steps: "
        f"{summary}{detail}"
    )

    # Display error messages if any
    if error_messages:
        click.echo(f"{timestamp} [causaliq-workflow] ERRORS:")
        for err_msg in error_messages:
            click.echo(err_msg)


# ============================================================================
# Cache export command
# ============================================================================


@cli.command(name="export-cache")
@click.option(
    "--input",
    "-i",
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
def export_cache(
    cache_file: Path,
    output: Path,
) -> None:
    """Export cache entries to directory or zip file.

    Reads all entries from a WorkflowCache database and exports them
    to a hierarchical directory structure based on matrix variable
    values. Each entry's objects are exported to separate files.

    Examples:

        cqflow export-cache -i cache.db -o ./results

        cqflow export-cache -i cache.db -o results.zip
    """
    try:
        from causaliq_workflow.cache import WorkflowCache

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(
            f"{timestamp} [causaliq-workflow] EXPORTING cache: {cache_file}"
        )

        with WorkflowCache(cache_file) as cache:
            entry_count = cache.entry_count()
            if entry_count == 0:
                click.echo(
                    f"{timestamp} [causaliq-workflow] "
                    "No entries found in cache"
                )
                sys.exit(0)

            click.echo(
                f"{timestamp} [causaliq-workflow] "
                f"Found {entry_count} entries"
            )

            try:
                exported = cache.export(output)
                click.echo(
                    f"{timestamp} [causaliq-workflow] "
                    f"EXPORTED {exported} entries to: {output}"
                )
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


@cli.command(name="import-cache")
@click.option(
    "--input",
    "-i",
    "input_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to exported directory or .zip file to import from.",
)
@click.option(
    "--output",
    "-o",
    "cache_file",
    required=True,
    type=click.Path(path_type=Path),
    help="Destination WorkflowCache database file (.db).",
)
def import_cache(
    input_path: Path,
    cache_file: Path,
) -> None:
    """Import cache entries from directory or zip file.

    Reads entries previously exported by 'export-cache' and stores them
    into the specified cache database. Creates the cache file if it
    does not exist.

    Examples:

        cqwork import-cache -i ./results -o cache.db

        cqwork import-cache -i results.zip -o cache.db
    """
    try:
        from causaliq_workflow.cache import WorkflowCache

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(
            f"{timestamp} [causaliq-workflow] IMPORTING from: {input_path}"
        )

        with WorkflowCache(cache_file) as cache:
            try:
                imported = cache.import_entries(input_path)
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
