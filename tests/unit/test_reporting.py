"""Unit tests for workflow run reporting."""

from typing import Any, Dict, List

import pytest

from causaliq_workflow.reporting import (
    MAX_REPORTED_ERRORS,
    StepCounts,
    count_results,
    format_counts,
    format_detail,
    format_matrix_values,
    format_summary,
    limit_errors,
)


def _child(name: str, status: str, **extra: Any) -> Dict[str, Any]:
    """Return one child step summary."""
    return {"name": name, "status": status, **extra}


def _call(steps: List[Dict[str, Any]], **extra: Any) -> Dict[str, Any]:
    """Return a workflow-call step summary wrapping child steps."""
    return {
        "status": "success",
        "workflow": "child.yml",
        "steps": steps,
        **extra,
    }


# Matrix values are formatted as a bracketed pair list.
def test_format_matrix_values_lists_pairs() -> None:
    values = {"network": "asia", "algorithm": "pc"}
    assert format_matrix_values(values) == " [network=asia, algorithm=pc]"


# An empty matrix produces no bracket fragment.
def test_format_matrix_values_empty() -> None:
    assert format_matrix_values({}) == ""


# Leaf steps are counted through every level of nested calls.
def test_count_results_counts_nested_call_leaf_steps() -> None:
    # The reported bug: three migrations and three learning calls were
    # summarised as "3 executed, 3 skipped" instead of "6 skipped".
    results = [
        {
            "job": {},
            "steps": {
                "Migrate": _call([_child("migrate", "skipped")] * 3),
                "BNSL": _call(
                    [
                        _call([_child("learn", "skipped")], name="std"),
                        _call([_child("learn", "skipped")], name="opt"),
                        _call([_child("learn", "skipped")], name="bad"),
                    ]
                ),
            },
        }
    ]

    counts = count_results(results, "run")

    assert counts.skipped == 6
    assert counts.executed == 0
    assert counts.new_entries == 0
    assert counts.total == 6


# A top-level failure is reported with the job's matrix values.
def test_count_results_reports_job_matrix_values() -> None:
    results = [
        {
            "job": {"network": "asia", "sample_size": 10},
            "steps": {"Learn": {"status": "failed"}},
        }
    ]

    counts = count_results(results, "run")

    assert counts.errors == ["  Learn [network=asia, sample_size=10]: failed"]


# A nested failure uses the child step's own matrix values.
def test_count_results_reports_nested_matrix_values() -> None:
    child = _child(
        "learn",
        "error",
        errors=["boom"],
        matrix_values={"network": "asia"},
    )
    results = [{"job": {}, "steps": {"Call": _call([child])}}]

    counts = count_results(results, "run")

    assert counts.errors == ["  learn [network=asia]: boom"]


# Dry-run totals use the would-execute wording.
def test_count_results_dry_run_wording() -> None:
    results = [
        {
            "steps": {
                "Learn": {"status": "would_execute"},
                "Evaluate": {"status": "would_skip"},
            }
        }
    ]

    counts = count_results(results, "dry-run")

    assert counts.would_execute == 1
    assert counts.would_skip == 1
    assert format_summary(counts, "dry-run") == "1 would execute, 1 would skip"


# A completed run reports executed, skipped and failed totals.
def test_format_summary_reports_each_status() -> None:
    counts = StepCounts(executed=2, skipped=3, failed=1)
    summary = format_summary(counts, "run")
    assert summary == "2 executed, 3 skipped, 1 failed"


# An empty run reports zero steps.
def test_format_summary_empty() -> None:
    assert format_summary(StepCounts(), "run") == "0 steps"


# Entry counts are pluralised in the detail fragment.
def test_format_detail_pluralises() -> None:
    assert format_detail(StepCounts(new_entries=1)) == " (1 new entry)"
    assert format_detail(StepCounts()) == ""


# A call completion message totals its subtree.
def test_format_counts_totals_subtree() -> None:
    counts = StepCounts(executed=2, skipped=3)
    assert format_counts(counts, "run") == "5 steps: 2 executed, 3 skipped"


# A call with no steps reports a zero total.
def test_format_counts_without_steps() -> None:
    assert format_counts(StepCounts(), "run") == "0 steps"


# Short error lists are reported in full.
def test_limit_errors_keeps_short_lists() -> None:
    messages = [f"  step{i}: failed" for i in range(3)]
    assert limit_errors(messages) == messages


# Long error lists are capped with a remaining count.
def test_limit_errors_reports_remaining() -> None:
    messages = [f"  step{i}: failed" for i in range(13)]

    limited = limit_errors(messages)

    assert len(limited) == MAX_REPORTED_ERRORS + 1
    assert limited[-1] == "  ... and 3 more errors"


# A single omitted error uses the singular wording.
def test_limit_errors_singular_remaining() -> None:
    messages = [f"  step{i}: failed" for i in range(11)]

    limited = limit_errors(messages)

    assert limited[-1] == "  ... and 1 more error"


# The report limit counts are driven by the configured maximum.
@pytest.mark.parametrize("limit", [1, 5])
def test_limit_errors_respects_custom_limit(limit: int) -> None:
    messages = [f"  step{i}: failed" for i in range(limit + 2)]

    limited = limit_errors(messages, limit=limit)

    assert len(limited) == limit + 1
    assert limited[-1] == "  ... and 2 more errors"
