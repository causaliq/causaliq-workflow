"""Functional tests for two-pass workflow validation with filesystem.

Tests that require cache files to exercise AGGREGATE pattern validation
paths.
"""

import pytest
from causaliq_core import (
    ActionPattern,
    ActionValidationError,
    CausalIQActionProvider,
)

from causaliq_workflow.cache import CacheEntry, WorkflowCache
from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor


class StrictAggregateProvider(CausalIQActionProvider):
    """AGGREGATE pattern action that validates required parameters."""

    name = "strict-agg"
    version = "1.0.0"
    supported_actions = {"strict_agg"}
    action_patterns = {"strict_agg": ActionPattern.AGGREGATE}

    def validate_parameters(self, action, parameters):
        super().validate_parameters(action, parameters)
        if "required_param" not in parameters:
            raise ActionValidationError("Missing required_param for agg")

    def _execute(self, action, parameters, mode, context, logger):
        return ("success", {}, [])


# Test AGGREGATE pattern validation catches errors.
def test_validate_aggregation_entries_missing_params(tmp_path) -> None:
    """AGGREGATE validation catches missing params per matrix combo."""
    cache_path = tmp_path / "test.db"
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata={}))

    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-agg"] = StrictAggregateProvider

    workflow = {
        "matrix": {"network": ["asia", "alarm"]},
        "steps": [
            {
                "name": "agg-step",
                "uses": "strict-agg",
                "with": {
                    "action": "strict_agg",
                    "input": str(cache_path),
                    "output": str(tmp_path / "output.db"),
                },
            }
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert len(errors) == 2  # One error per matrix combo
    assert all("Missing required_param for agg" in e for e in errors)


# AGGREGATE templates may use matrix keys derived from the input cache.
def test_aggregate_template_uses_derived_matrix_keys(tmp_path) -> None:
    """AGGREGATE steps derive template variables from input cache keys."""
    cache_path = tmp_path / "graphs.db"
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata={}))

    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-agg"] = StrictAggregateProvider
    workflow = {
        "steps": [
            {
                "name": "agg-step",
                "uses": "strict-agg",
                "with": {
                    "action": "strict_agg",
                    "input": str(cache_path),
                    "output": str(tmp_path / "output.db"),
                    "reference": "networks/{{network}}/true.xdsl",
                },
            }
        ],
    }

    executor._validate_template_variables(workflow)


# AGGREGATE templates defer when the input cache does not exist yet.
def test_aggregate_template_defers_missing_cache(tmp_path) -> None:
    """Variables resolve at runtime when the input cache is not created."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-agg"] = StrictAggregateProvider
    workflow = {
        "steps": [
            {
                "name": "agg-step",
                "uses": "strict-agg",
                "with": {
                    "action": "strict_agg",
                    "input": str(tmp_path / "missing.db"),
                    "output": str(tmp_path / "output.db"),
                    "reference": "networks/{{network}}/true.xdsl",
                },
            }
        ],
    }

    executor._validate_template_variables(workflow)


# AGGREGATE templates reject keys absent from the input cache.
def test_aggregate_template_rejects_unknown_cache_key(tmp_path) -> None:
    """A template variable missing from the cache is still an error."""
    cache_path = tmp_path / "graphs.db"
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata={}))

    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-agg"] = StrictAggregateProvider
    workflow = {
        "steps": [
            {
                "name": "agg-step",
                "uses": "strict-agg",
                "with": {
                    "action": "strict_agg",
                    "input": str(cache_path),
                    "output": str(tmp_path / "output.db"),
                    "reference": "networks/{{dataset}}/true.xdsl",
                },
            }
        ],
    }

    with pytest.raises(WorkflowExecutionError, match="dataset"):
        executor._validate_template_variables(workflow)
