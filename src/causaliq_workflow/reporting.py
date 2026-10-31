"""Workflow run reporting: step counts, summaries and error lines.

The executor records what a run did as nested step results; the CLI
reports those results at the end of a run and whenever a called
workflow returns. Both layers share the counting and formatting rules
here so the totals in the final summary, in a sub-workflow's completion
message and in the error list cannot disagree.

This module has no CLI dependency: it works on the plain result
dictionaries produced by :mod:`causaliq_workflow.workflow.execution`.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol

MAX_REPORTED_ERRORS = 10
"""Maximum number of messages listed in a run's error summary."""

_FAILURE_STATUSES = ("error", "failed")


class StepLogger(Protocol):
    """Callback receiving one workflow step log event.

    ``depth`` is the workflow nesting depth that produced the event: 0
    for the top-level workflow's own steps and one more for each called
    workflow. ``detail`` carries an optional trailing fragment, such as
    the cumulative counts of a workflow call.

    Both extra arguments are keyword-only and optional, so a four
    argument callback keeps working when it accepts keyword arguments.
    """

    def __call__(
        self,
        action_method: str,
        step_name: str,
        status: str,
        matrix_values: Dict[str, Any],
        *,
        depth: int = 0,
        detail: str = "",
    ) -> None:
        """Report a step status, a call boundary or a call completion."""
        ...


@dataclass
class StepCounts:
    """Aggregated step status counts for a workflow run."""

    executed: int = 0
    skipped: int = 0
    forced: int = 0
    would_execute: int = 0
    would_skip: int = 0
    failed: int = 0
    new_entries: int = 0
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


def format_matrix_values(matrix_values: Dict[str, Any]) -> str:
    """Format matrix values as ``' [key=value, ...]'`` (empty when none)."""
    if not matrix_values:
        return ""
    matrix_str = ", ".join(
        f"{key}={value}" for key, value in matrix_values.items()
    )
    return f" [{matrix_str}]"


def count_results(results: List[Dict[str, Any]], mode: str) -> StepCounts:
    """Aggregate step statuses across job results at every call depth.

    A workflow-call step reports the steps it ran, so those are counted
    in place of the call step itself. The recursion continues through
    nested calls, so the totals describe all the work the run performed.

    Args:
        results: Job results returned by the executor.
        mode: Execution mode used to word dry-run statuses.

    Returns:
        Aggregated counts, including formatted error lines.
    """
    counts = StepCounts()
    for result in results:
        matrix_values = result.get("job", {})
        for name, step in result.get("steps", {}).items():
            _count_step(counts, name, step, mode, matrix_values)
    return counts


def format_summary(counts: StepCounts, mode: str) -> str:
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


def format_detail(counts: StepCounts) -> str:
    """Format the new-entry detail fragment."""
    if counts.new_entries <= 0:
        return ""
    entries = _pluralise(counts.new_entries, "new entry", "new entries")
    return f" ({entries})"


def format_counts(counts: StepCounts, mode: str) -> str:
    """Format step counts as ``'N steps: <summary>'``.

    Used by a workflow call's completion message, where the total is
    cumulative for the called workflow and its own calls.

    Args:
        counts: Counts for the called workflow's whole subtree.
        mode: Execution mode used to word dry-run statuses.

    Returns:
        Compact description such as ``'6 steps: 3 executed, 3 skipped'``.
    """
    if counts.total == 0:
        return "0 steps"
    return f"{counts.total} steps: {format_summary(counts, mode)}"


def limit_errors(
    messages: List[str], limit: int = MAX_REPORTED_ERRORS
) -> List[str]:
    """Return at most ``limit`` error lines plus an omitted-count note.

    Args:
        messages: Formatted error lines, already indented.
        limit: Maximum number of lines to keep.

    Returns:
        The retained lines, followed by a note such as
        ``'  ... and 5 more errors'`` when lines were dropped.
    """
    if len(messages) <= limit:
        return list(messages)
    remaining = len(messages) - limit
    note = _pluralise(remaining, "more error", "more errors")
    return [*messages[:limit], f"  ... and {note}"]


def _count_step(
    counts: StepCounts,
    step_name: str,
    step_result: Dict[str, Any],
    mode: str,
    matrix_values: Dict[str, Any],
) -> None:
    """Fold one step result into the aggregate counts."""
    if step_result.get("workflow"):
        _count_called_steps(counts, step_result, mode)
        return
    _count_by_status(counts, step_name, step_result, mode, matrix_values)


def _count_called_steps(
    counts: StepCounts,
    step_result: Dict[str, Any],
    mode: str,
) -> None:
    """Count a called workflow's steps in place of the call step."""
    for nested in step_result.get("steps", []):
        _count_step(
            counts,
            str(nested.get("name", "")),
            nested,
            mode,
            nested.get("matrix_values", {}),
        )


def _count_by_status(
    counts: StepCounts,
    step_name: str,
    step_result: Dict[str, Any],
    mode: str,
    matrix_values: Dict[str, Any],
) -> None:
    """Fold one action step's status into the aggregate counts."""
    status = step_result.get("status", "unknown")
    if status == "success":
        _count_success(counts, mode)
        return
    if status == "skipped":
        counts.skipped += 1
        return
    if status == "would_execute":
        _count_would_execute(counts)
        return
    if status == "would_skip":
        counts.would_skip += 1
        return
    if status in _FAILURE_STATUSES:
        _count_failure(counts, step_name, step_result, matrix_values)


def _count_success(counts: StepCounts, mode: str) -> None:
    """Fold a successful step result into the counts."""
    if mode == "force":
        counts.forced += 1
    else:
        counts.executed += 1
    counts.new_entries += 1


def _count_would_execute(counts: StepCounts) -> None:
    """Fold a dry-run would-execute step into the counts."""
    counts.would_execute += 1
    counts.new_entries += 1


def _count_failure(
    counts: StepCounts,
    step_name: str,
    step_result: Dict[str, Any],
    matrix_values: Dict[str, Any],
) -> None:
    """Fold a failed step result and its messages into the counts."""
    counts.failed += 1
    if step_result.get("errors"):
        messages = step_result["errors"]
    else:
        messages = [step_result.get("reason") or "failed"]
    matrix_part = format_matrix_values(matrix_values)
    for message in messages:
        counts.errors.append(f"  {step_name}{matrix_part}: {message}")


def _append_if_positive(parts: List[str], count: int, label: str) -> None:
    """Append 'N label' to parts when the count is positive."""
    if count > 0:
        parts.append(f"{count} {label}")


def _pluralise(count: int, singular: str, plural: str) -> str:
    """Return 'N singular' or 'N plural' depending on the count."""
    return f"{count} {singular if count == 1 else plural}"
