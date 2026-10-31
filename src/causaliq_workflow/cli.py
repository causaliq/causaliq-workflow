"""Command-line interface for causaliq-workflow."""

import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import click
import yaml

from causaliq_workflow.cli_report import _report_results
from causaliq_workflow.reporting import StepLogger, format_matrix_values
from causaliq_workflow.yaml_frontend import parse_scalar_text

from . import __version__

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.workflow import WorkflowExecutor


def _log_cli_message(log_depth: int, message: str) -> None:
    """Log CLI message with standardised format."""
    if log_depth < 1:
        return
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
    """Parse a CLI parameter value with workflow value rules."""
    try:
        value = parse_scalar_text(text)
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
    "--log-depth",
    default=1,
    type=click.IntRange(min=0),
    envvar="CAUSALIQ_LOG_DEPTH",
    show_default=True,
    help="Maximum workflow nesting depth to report: 0 is silent, "
    "1 reports the top-level summary, 2 adds the top-level steps, "
    "3 also adds first-level sub-workflow steps, and so on.",
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
    log_depth: int,
    raw_params: Tuple[str, ...],
) -> None:
    """Execute a CausalIQ workflow file.

    WORKFLOW_FILE is the path to a YAML workflow file to execute.

    Examples:

        causaliq-workflow run experiment.yml

        causaliq-workflow run experiment.yml --mode=run

        causaliq-workflow run experiment.yml --mode=dry-run --log-depth=2

        causaliq-workflow run experiment.yml --param sample_size=1000
    """
    try:
        from causaliq_workflow.workflow import WorkflowExecutor

        parameters = _parse_cli_parameters(raw_params)
        executor = WorkflowExecutor()
        _log_cli_message(log_depth, f"LOADING workflow from: {workflow_file}")

        workflow = _parse_workflow_file(executor, workflow_file, parameters)
        _validate_workflow(executor, workflow, log_depth, parameters)
        results = _run_workflow_jobs(
            executor, workflow, mode, log_depth, parameters
        )
        _report_results(results, workflow, mode, log_depth)

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
    log_depth: int,
    parameters: Dict[str, Any],
) -> None:
    """Validate the parsed workflow, exiting with a message on failure."""
    _log_cli_message(log_depth, "VALIDATING workflow syntax and parameters...")
    try:
        executor.execute_workflow(
            workflow, mode="validate", cli_params=parameters
        )
        _log_cli_message(log_depth, "VALIDATED workflow successfully")
    except Exception as e:
        _log_cli_error(str(e))
        sys.exit(1)


def _run_workflow_jobs(
    executor: "WorkflowExecutor",
    workflow: Dict[str, Any],
    mode: str,
    log_depth: int,
    parameters: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Execute the workflow in the requested mode, exiting on failure."""
    step_logger = _make_step_logger(log_depth)
    _log_cli_message(log_depth, f"EXECUTING workflow in {mode} mode...")
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


def _make_step_logger(log_depth: int) -> StepLogger:
    """Build the real-time per-step logging callback for a log depth."""

    def log_step_execution(
        action_method: str,
        step_name: str,
        status: str,
        matrix_values: Dict[str, Any],
        *,
        depth: int = 0,
        detail: str = "",
    ) -> None:
        """Log a step event, indented by its workflow call depth."""
        if depth + 2 > log_depth:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        indent = "  " * depth
        matrix_part = format_matrix_values(matrix_values)
        detail_part = f" ({detail})" if detail else ""

        click.echo(
            f"{timestamp} {indent}[{action_method}] {status} "
            f"{step_name}{matrix_part}{detail_part}"
        )

    return log_step_execution


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
