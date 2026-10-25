"""Command-line interface for causaliq-workflow."""

import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Tuple

import click
import yaml

from causaliq_workflow.cli_report import _report_results

from . import __version__

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.workflow import WorkflowExecutor


def _log_cli_message(level: str, message: str) -> None:
    """Log CLI message with standardised format."""
    if level != "none":
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"{timestamp} [causaliq-workflow] {message}")


def _log_cli_error(message: str) -> None:
    """Log CLI error message with standardised format."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    click.echo(f"{timestamp} [causaliq-workflow] ERROR {message}", err=True)


def _split_cli_parameter(item: str) -> Tuple[str, Any]:
    """Split a ``NAME=VALUE`` CLI parameter into a name and typed value."""
    from causaliq_workflow.workflow.parameters import _is_parameter_name

    name, separator, text = item.partition("=")
    if not separator or not _is_parameter_name(name):
        raise click.BadParameter(
            f"expected NAME=VALUE with a valid parameter name, "
            f"got '{item}'",
            param_hint="--param",
        )
    return name, _parse_cli_value(text)


def _parse_cli_value(text: str) -> Any:
    """Parse a CLI parameter value as YAML, falling back to the string."""
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError:
        return text
    if isinstance(value, dict):
        raise click.BadParameter(
            f"parameter values must be a scalar or a list, got '{text}'",
            param_hint="--param",
        )
    return value


def _parse_cli_parameters(raw_params: Tuple[str, ...]) -> Dict[str, Any]:
    """Parse repeatable ``NAME=VALUE`` CLI parameters into a dictionary."""
    parameters: Dict[str, Any] = {}
    for item in raw_params:
        name, value = _split_cli_parameter(item)
        if name in parameters:
            raise click.BadParameter(
                f"duplicate parameter '{name}'", param_hint="--param"
            )
        parameters[name] = value
    return parameters


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
@click.option(
    "--param",
    "-p",
    "raw_params",
    multiple=True,
    metavar="NAME=VALUE",
    help="Workflow parameter, repeatable (e.g. --param sample_size=1000). "
    "Names matching a matrix entry replace that entry; other names "
    "replace {{name}} placeholders.",
)
def run_workflow(
    workflow_file: Path,
    mode: str,
    log_level: str,
    raw_params: Tuple[str, ...],
) -> None:
    """Execute a CausalIQ workflow file.

    WORKFLOW_FILE is the path to a YAML workflow file to execute.

    Examples:

        causaliq-workflow run experiment.yml

        causaliq-workflow run experiment.yml --mode=run

        causaliq-workflow run experiment.yml --mode=dry-run --log-level=all

        causaliq-workflow run experiment.yml --param sample_size=1000
    """
    try:
        from causaliq_workflow.workflow import WorkflowExecutor

        parameters = _parse_cli_parameters(raw_params)
        executor = WorkflowExecutor()
        _log_cli_message(log_level, f"LOADING workflow from: {workflow_file}")

        workflow = _parse_workflow_file(executor, workflow_file, parameters)
        _validate_workflow(executor, workflow, log_level, parameters)
        results = _run_workflow_jobs(
            executor, workflow, mode, log_level, parameters
        )
        _report_results(results, workflow, mode, log_level)

    except KeyboardInterrupt:
        _log_cli_error("Workflow execution interrupted by user")
        sys.exit(130)
    except ImportError as e:
        _log_cli_error(f"Missing required dependencies: {e}")
        sys.exit(1)


def _parse_workflow_file(
    executor: "WorkflowExecutor",
    workflow_file: Path,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """Parse the workflow file, exiting with a message on failure."""
    from causaliq_workflow.workflow import WorkflowExecutionError

    try:
        return executor.parse_workflow(
            str(workflow_file), parameters=parameters
        )
    except FileNotFoundError:
        _log_cli_error(f"Workflow file not found: {workflow_file}")
    except WorkflowExecutionError as e:
        # Our own errors - print directly
        _log_cli_error(str(e))
    except Exception as e:
        _log_parse_error(e)
    sys.exit(1)


def _log_parse_error(error: Exception) -> None:
    """Log a workflow parse error with YAML-specific wording."""
    if "yaml" in str(error).lower():
        _log_cli_error(f"Invalid YAML in workflow file: {error}")
    else:
        _log_cli_error(f"Failed to parse workflow: {error}")


def _validate_workflow(
    executor: "WorkflowExecutor",
    workflow: Dict[str, Any],
    log_level: str,
    parameters: Dict[str, Any],
) -> None:
    """Validate the parsed workflow, exiting with a message on failure."""
    _log_cli_message(log_level, "VALIDATING workflow syntax and parameters...")
    try:
        executor.execute_workflow(
            workflow, mode="validate", cli_params=parameters
        )
        _log_cli_message(log_level, "VALIDATED workflow successfully")
    except Exception as e:
        _log_cli_error(str(e))
        sys.exit(1)


def _run_workflow_jobs(
    executor: "WorkflowExecutor",
    workflow: Dict[str, Any],
    mode: str,
    log_level: str,
    parameters: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Execute the workflow in the requested mode, exiting on failure."""
    step_logger = _make_step_logger(log_level)
    _log_cli_message(log_level, f"EXECUTING workflow in {mode} mode...")
    try:
        return executor.execute_workflow(
            workflow,
            mode=mode,
            cli_params=parameters,
            step_logger=step_logger,
            validate=False,
        )
    except Exception as e:
        _log_cli_error(f"Workflow execution failed: {e}")
        sys.exit(1)


def _make_step_logger(
    log_level: str,
) -> Callable[[str, str, str, Dict[str, Any]], None]:
    """Build the real-time per-step logging callback for a log level."""

    def log_step_execution(
        action_method: str,
        step_name: str,
        status: str,
        matrix_values: Dict[str, Any],
    ) -> None:
        """Log step execution in real-time."""
        if log_level != "all":
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Extract per-entry counts from a dry-run scan if present
        would_process = matrix_values.pop("_entries_would_process", None)
        would_skip = matrix_values.pop("_entries_would_skip", None)

        matrix_part = _format_matrix_values(matrix_values)
        entry_info = _format_entry_counts(would_process, would_skip)

        click.echo(
            f"{timestamp} [{action_method}] {status:12} "
            f"{step_name}{matrix_part}{entry_info}"
        )

    return log_step_execution


def _format_matrix_values(matrix_values: Dict[str, Any]) -> str:
    """Format matrix values as ' [key=value, ...]' (empty when none)."""
    if not matrix_values:
        return ""
    matrix_str = ", ".join(
        f"{key}={value}" for key, value in matrix_values.items()
    )
    return f" [{matrix_str}]"


def _format_entry_counts(would_process: Any, would_skip: Any) -> str:
    """Format per-entry counts as ' (n to process, m to skip)'."""
    if would_process is None and would_skip is None:
        return ""

    parts = []
    if would_process:
        parts.append(f"{would_process} to process")
    if would_skip:
        parts.append(f"{would_skip} to skip")
    if not parts:
        return ""
    return f" ({', '.join(parts)})"


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
            _export_cache_entries(cache, output, timestamp)

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


def _export_cache_entries(cache: Any, output: Path, timestamp: str) -> None:
    """Report the entry count and export the cache contents."""
    entry_count = cache.entry_count()
    if entry_count == 0:
        click.echo(
            f"{timestamp} [causaliq-workflow] " "No entries found in cache"
        )
        sys.exit(0)

    click.echo(
        f"{timestamp} [causaliq-workflow] " f"Found {entry_count} entries"
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
            _import_cache_entries(cache, input_path, cache_file, timestamp)

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


def _import_cache_entries(
    cache: Any, input_path: Path, cache_file: Path, timestamp: str
) -> None:
    """Import entries from a path and report the result."""
    try:
        imported = cache.import_entries(input_path)
        click.echo(
            f"{timestamp} [causaliq-workflow] "
            f"IMPORTED {imported} entries into: {cache_file}"
        )
    except Exception as e:
        _log_cli_error(f"Import failed: {e}")
        sys.exit(1)


def main() -> None:
    """Entry point for the CLI."""
    cli(prog_name="causaliq-workflow")


if __name__ == "__main__":  # pragma: no cover
    main()
