"""CLI result reporting helpers for causaliq-workflow."""

from datetime import datetime
from typing import Any, Dict, List

import click

from causaliq_workflow.reporting import (
    count_results,
    format_detail,
    format_summary,
    limit_errors,
)


def _report_results(
    results: List[Dict[str, Any]],
    workflow: Dict[str, Any],
    mode: str,
    log_depth: int,
) -> None:
    """Report workflow execution results following standardised format."""
    if log_depth < 1:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not results:
        click.echo(f"{timestamp} [causaliq-workflow] COMPLETED 0 steps")
        return

    counts = count_results(results, mode)
    summary = format_summary(counts, mode)
    detail = format_detail(counts)
    click.echo(
        f"{timestamp} [causaliq-workflow] COMPLETED {counts.total} steps: "
        f"{summary}{detail}"
    )
    _log_result_errors(timestamp, counts.errors)


def _log_result_errors(timestamp: str, error_messages: List[str]) -> None:
    """Print recorded step error messages, capped, with an omitted count."""
    if not error_messages:
        return
    click.echo(f"{timestamp} [causaliq-workflow] ERRORS:")
    for err_msg in limit_errors(error_messages):
        click.echo(err_msg)
