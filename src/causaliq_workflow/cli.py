"""Command-line interface for causaliq-workflow."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import click


def _log_cli_message(level: str, message: str) -> None:
    """Log CLI message with standardized format."""
    if level != "none":
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"{timestamp} [causaliq-workflow] {message}")


def _log_cli_error(message: str) -> None:
    """Log CLI error message with standardized format."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    click.echo(f"{timestamp} [causaliq-workflow] ERROR {message}", err=True)


@click.command(name="causaliq-workflow")
@click.version_option(version="0.1.0")
@click.argument(
    "workflow_file",
    metavar="WORKFLOW_FILE",
    required=True,
    type=click.Path(path_type=Path),
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
def cli(workflow_file: Path, mode: str, log_level: str) -> None:
    """
    Execute CausalIQ workflow files.

    WORKFLOW_FILE is the path to a YAML workflow file to execute.

    Examples:
        causaliq-workflow experiment.yml              # Validate and preview
        causaliq-workflow experiment.yml --mode=run  # Execute workflow
        causaliq-workflow experiment.yml --mode=dry-run --log-level=all  \
            # Detailed preview
    """
    try:
        from causaliq_workflow.workflow import WorkflowExecutor

        # Create workflow executor
        executor = WorkflowExecutor()

        # Load and parse workflow
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

        # Validate workflow syntax and parameters for ALL modes
        _log_cli_message(
            log_level, "VALIDATING workflow syntax and parameters..."
        )
        try:
            # Use internal "validate" mode for silent pre-validation
            executor.execute_workflow(workflow, mode="validate")
            _log_cli_message(log_level, "VALIDATED workflow successfully")
        except Exception as e:
            _log_cli_error(f"Workflow validation failed: {e}")
            sys.exit(1)

        # Define step logger for real-time step reporting
        def log_step_execution(
            action_name: str, step_name: str, status: str
        ) -> None:
            """Log step execution in real-time."""
            if log_level == "all":
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                click.echo(
                    f"{timestamp} [{action_name}] STEP {status} {step_name}"
                )

        # Execute workflow in requested mode
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

        # Report results
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
    """Report workflow execution results following standardized format."""
    if log_level == "none":
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not results:
        click.echo(
            f"{timestamp} [causaliq-workflow] COMPLETED workflow with 0 jobs"
        )
        return

    total_steps = sum(len(result.get("steps", {})) for result in results)

    # For detailed logging, show job summaries (steps already logged real-time)
    if log_level == "all":
        for i, result in enumerate(results):
            steps = result.get("steps", {})
            click.echo(
                f"{timestamp} [causaliq-workflow] JOB {i + 1} completed "
                f"{len(steps)} step(s)"
            )

    # Report workflow summary
    click.echo(
        f"{timestamp} [causaliq-workflow] COMPLETED workflow with "
        f"{len(results)} job(s) ({total_steps} steps)"
    )


def main() -> None:
    """Entry point for the CLI."""
    cli(prog_name="causaliq-workflow")


if __name__ == "__main__":  # pragma: no cover
    main()
