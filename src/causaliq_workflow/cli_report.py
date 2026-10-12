"""CLI result reporting helpers for causaliq-workflow."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

import click


@dataclass
class _ResultCounts:
    """Aggregated step status counts for the CLI result report."""

    executed: int = 0
    skipped: int = 0
    forced: int = 0
    would_execute: int = 0
    would_skip: int = 0
    failed: int = 0
    new_entries: int = 0
    updates: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Return the total number of reported steps."""
        return (
            self.executed
            + self.skipped
            + self.forced
            + self.would_execute
            + self.would_skip
            + self.failed
        )


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

    counts = _count_results(results, mode)
    summary = _format_summary(counts, mode)
    detail = _format_detail(counts)
    click.echo(
        f"{timestamp} [causaliq-workflow] COMPLETED {counts.total} steps: "
        f"{summary}{detail}"
    )
    _log_result_errors(timestamp, counts.errors)


def _count_results(
    results: List[Dict[str, Any]], mode: str
) -> "_ResultCounts":
    """Aggregate step statuses across all job results."""
    counts = _ResultCounts()
    for result in results:
        for step_name, step_result in result.get("steps", {}).items():
            _count_step(counts, step_name, step_result, mode)
    return counts


def _count_step(
    counts: "_ResultCounts",
    step_name: str,
    step_result: Dict[str, Any],
    mode: str,
) -> None:
    """Fold a single step result into the aggregate counts."""
    status = step_result.get("status", "unknown")
    if status == "success":
        _count_success(counts, step_result, mode)
        return
    if status == "skipped":
        counts.skipped += 1
        return
    if status == "would_execute":
        _count_would_execute(counts, step_result)
        return
    if status == "would_skip":
        counts.would_skip += 1
        return
    if status in ("error", "failed"):
        _count_failure(counts, step_name, step_result)


def _count_success(
    counts: "_ResultCounts", step_result: Dict[str, Any], mode: str
) -> None:
    """Fold a successful step result into the counts."""
    if mode == "force":
        counts.forced += 1
    else:
        counts.executed += 1

    # Track new entries vs updates
    updated = step_result.get("entries_updated", 0)
    if updated > 0:
        counts.updates += updated
    else:
        counts.new_entries += 1


def _count_would_execute(
    counts: "_ResultCounts", step_result: Dict[str, Any]
) -> None:
    """Fold a dry-run would-execute step into the counts."""
    counts.would_execute += 1
    would_process = step_result.get("would_process", 0)
    would_skip = step_result.get("would_skip", 0)
    if would_process > 0 or would_skip > 0:
        # UPDATE step with sub-entries
        counts.updates += would_process
    else:
        # CREATE / AGGREGATE step
        counts.new_entries += 1


def _count_failure(
    counts: "_ResultCounts",
    step_name: str,
    step_result: Dict[str, Any],
) -> None:
    """Fold a failed step result and its messages into the counts."""
    counts.failed += 1
    for err in step_result.get("errors", []):
        counts.errors.append(f"  {step_name}: {err}")


def _format_summary(counts: "_ResultCounts", mode: str) -> str:
    """Format the completed-steps summary fragment."""
    parts: List[str] = []
    if mode == "dry-run":
        _append_if_positive(parts, counts.would_execute, "would execute")
        _append_if_positive(parts, counts.would_skip, "would skip")
    else:
        _append_if_positive(parts, counts.executed, "executed")
        _append_if_positive(parts, counts.skipped, "skipped")
        _append_if_positive(parts, counts.forced, "forced")
    _append_if_positive(parts, counts.failed, "failed")
    return ", ".join(parts) if parts else "0 steps"


def _append_if_positive(parts: List[str], count: int, label: str) -> None:
    """Append 'N label' to parts when the count is positive."""
    if count > 0:
        parts.append(f"{count} {label}")


def _format_detail(counts: "_ResultCounts") -> str:
    """Format the new-entry/update detail fragment."""
    detail_parts: List[str] = []
    if counts.new_entries > 0:
        detail_parts.append(
            _pluralise(counts.new_entries, "new entry", "new entries")
        )
    if counts.updates > 0:
        detail_parts.append(_pluralise(counts.updates, "update", "updates"))
    if not detail_parts:
        return ""
    return f" ({', '.join(detail_parts)})"


def _pluralise(count: int, singular: str, plural: str) -> str:
    """Return 'N singular' or 'N plural' depending on the count."""
    return f"{count} {singular if count == 1 else plural}"


def _log_result_errors(timestamp: str, error_messages: List[str]) -> None:
    """Print recorded step error messages, if any."""
    if not error_messages:
        return
    click.echo(f"{timestamp} [causaliq-workflow] ERRORS:")
    for err_msg in error_messages:
        click.echo(err_msg)
