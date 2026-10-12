"""Focused tests for helpers extracted by the workflow package split."""

from typing import Any, List

import pytest

from causaliq_workflow.workflow import WorkflowExecutor
from causaliq_workflow.workflow.matrix import _cache_input_paths


# _cache_input_paths returns an empty list for empty inputs.
@pytest.mark.parametrize("value", [None, "", []])
def test_cache_input_paths_empty(value: Any) -> None:
    assert _cache_input_paths(value) == []


# _expand_range_value leaves a descending range unchanged.
def test_expand_range_value_descending(executor: WorkflowExecutor) -> None:
    assert executor._expand_range_value("5-3") == ["5-3"]


# _aggregate_step_matrix returns empty for an AGGREGATE step without input.
def test_aggregate_step_matrix_without_cache_input(
    executor: WorkflowExecutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    from causaliq_core import ActionPattern

    step = {"uses": "provider", "with": {"action": "agg"}}
    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        lambda provider, action: ActionPattern.AGGREGATE,
    )
    assert executor._aggregate_step_matrix(step) == {}


# _deduplicate_errors removes repeated step errors.
def test_deduplicate_errors_removes_duplicates(
    executor: WorkflowExecutor,
) -> None:
    errors: List[str] = ["Step 'a': boom", "Step 'a': boom"]
    assert executor._deduplicate_errors(errors) == ["Step 'a': boom"]
