"""Functional tests for two-pass workflow validation with filesystem.

Tests that require cache files to exercise UPDATE and AGGREGATE pattern
validation paths.
"""

from causaliq_core import (
    ActionPattern,
    ActionValidationError,
    CausalIQActionProvider,
)

from causaliq_workflow.cache import CacheEntry, WorkflowCache
from causaliq_workflow.workflow import WorkflowExecutor


class UpdateActionProvider(CausalIQActionProvider):
    """UPDATE pattern action provider for testing."""

    name = "update-provider"
    version = "1.0.0"
    supported_actions = {"update_action"}
    action_patterns = {"update_action": ActionPattern.UPDATE}

    def _execute(self, action, parameters, mode, context, logger):
        return ("success", {}, [])


class StrictUpdateProvider(CausalIQActionProvider):
    """UPDATE pattern action that validates required parameters."""

    name = "strict-update"
    version = "1.0.0"
    supported_actions = {"strict_update"}
    action_patterns = {"strict_update": ActionPattern.UPDATE}

    def validate_parameters(self, action, parameters):
        super().validate_parameters(action, parameters)
        if "required_param" not in parameters:
            raise ActionValidationError("Missing required_param")

    def _execute(self, action, parameters, mode, context, logger):
        return ("success", {}, [])


class AggregateActionProvider(CausalIQActionProvider):
    """AGGREGATE pattern action provider for testing."""

    name = "agg-provider"
    version = "1.0.0"
    supported_actions = {"aggregate_action"}
    action_patterns = {"aggregate_action": ActionPattern.AGGREGATE}

    def _execute(self, action, parameters, mode, context, logger):
        return ("success", {}, [])


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
