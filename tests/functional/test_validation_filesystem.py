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


# Test UPDATE pattern validation with cache entries.
def test_validate_update_entries_with_cache(tmp_path) -> None:
    """UPDATE validation iterates cache entries."""
    # Create cache with entries
    cache_path = tmp_path / "test.db"
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata={}))
        cache.put({"network": "alarm"}, CacheEntry(metadata={}))

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateActionProvider

    workflow = {
        "steps": [
            {
                "name": "update-step",
                "uses": "update-provider",
                "with": {
                    "action": "update_action",
                    "input": str(cache_path),
                },
            }
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert errors == []


# Test UPDATE validation detects missing required params per entry.
def test_validate_update_entries_missing_params(tmp_path) -> None:
    """UPDATE validation catches missing params for each entry."""
    cache_path = tmp_path / "test.db"
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata={}))
        cache.put({"network": "alarm"}, CacheEntry(metadata={}))

    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-update"] = StrictUpdateProvider

    workflow = {
        "steps": [
            {
                "name": "strict-step",
                "uses": "strict-update",
                "with": {
                    "action": "strict_update",
                    "input": str(cache_path),
                },
            }
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert len(errors) == 2  # One error per cache entry
    assert all("Missing required_param" in e for e in errors)


# Test _validate_update_entries with missing input parameter.
def test_validate_update_entries_missing_input(tmp_path) -> None:
    """_validate_update_entries reports missing input parameter."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateActionProvider

    # Call _validate_update_entries directly
    step = {
        "name": "no-input",
        "uses": "update-provider",
        "with": {"action": "update_action"},
    }

    errors = executor._validate_update_entries(step, {}, {})
    assert len(errors) == 1
    assert "requires 'input'" in errors[0]


# Test UPDATE validation skips non-existent cache.
def test_validate_update_entries_nonexistent_cache(tmp_path) -> None:
    """UPDATE validation skips if cache doesn't exist."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateActionProvider

    workflow = {
        "steps": [
            {
                "name": "missing-cache",
                "uses": "update-provider",
                "with": {
                    "action": "update_action",
                    "input": str(tmp_path / "nonexistent.db"),
                },
            }
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert errors == []  # Skipped - caught at execution time


# Test UPDATE validation catches semantic filter errors.
def test_validate_update_entries_filter_name_error(tmp_path) -> None:
    """UPDATE validation catches undefined variable in filter."""
    cache_path = tmp_path / "test.db"
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata={}))

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateActionProvider

    # Call _validate_update_entries directly with filter
    step = {
        "name": "bad-filter",
        "uses": "update-provider",
        "with": {
            "action": "update_action",
            "input": str(cache_path),
            "filter": "network == asia",  # Missing quotes!
        },
    }

    errors = executor._validate_update_entries(step, {}, {})
    assert len(errors) == 1
    assert "Filter" in errors[0] and "asia" in errors[0]


# Test UPDATE validation catches general filter exceptions.
def test_validate_update_entries_filter_exception(tmp_path) -> None:
    """UPDATE validation catches filter evaluation exceptions."""
    cache_path = tmp_path / "test.db"
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata={}))

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateActionProvider

    workflow = {
        "steps": [
            {
                "name": "broken-filter",
                "uses": "update-provider",
                "with": {
                    "action": "update_action",
                    "input": str(cache_path),
                    "filter": "1 / 0",  # ZeroDivisionError
                },
            }
        ],
    }

    errors = executor._validate_all_entries(workflow)
    assert len(errors) == 1
    assert "Filter evaluation failed" in errors[0]


# Test UPDATE validation with filter that excludes entries.
def test_validate_update_entries_filter_excludes(tmp_path) -> None:
    """Filtered out entries are not validated."""
    cache_path = tmp_path / "test.db"
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata={}))
        cache.put({"network": "alarm"}, CacheEntry(metadata={}))

    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-update"] = StrictUpdateProvider

    workflow = {
        "steps": [
            {
                "name": "filtered",
                "uses": "strict-update",
                "with": {
                    "action": "strict_update",
                    "input": str(cache_path),
                    "filter": "network == 'asia'",
                },
            }
        ],
    }

    errors = executor._validate_all_entries(workflow)
    # Only asia entry validated (alarm filtered out)
    assert len(errors) == 1


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


# Test UPDATE validation skips entries where cache.get returns None.
def test_validate_update_entries_get_returns_none(
    tmp_path, monkeypatch
) -> None:
    """Entries where cache.get() returns None are skipped."""
    cache_path = tmp_path / "test.db"
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata={}))

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateActionProvider

    step = {
        "name": "test-step",
        "uses": "update-provider",
        "with": {
            "action": "update_action",
            "input": str(cache_path),
        },
    }

    # Patch cache.get to return None
    def mock_get(self, matrix_values):
        return None

    monkeypatch.setattr(WorkflowCache, "get", mock_get)

    errors = executor._validate_update_entries(step, {}, {})
    # Entry skipped due to None return, no errors
    assert errors == []


# Test UPDATE validation handles generic filter exceptions.
def test_validate_update_entries_filter_generic_exception(
    tmp_path, monkeypatch
) -> None:
    """Generic filter exceptions are caught and reported."""
    cache_path = tmp_path / "test.db"
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata={}))

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateActionProvider

    step = {
        "name": "generic-error",
        "uses": "update-provider",
        "with": {
            "action": "update_action",
            "input": str(cache_path),
            "filter": "network == 'asia'",  # Valid filter
        },
    }

    # Patch evaluate_filter to raise a generic exception
    def mock_evaluate_filter(expr, metadata):
        raise TypeError("Unexpected type error")

    monkeypatch.setattr(
        "causaliq_core.utils.evaluate_filter", mock_evaluate_filter
    )

    errors = executor._validate_update_entries(step, {}, {})
    assert len(errors) == 1
    assert "Filter evaluation failed" in errors[0]
    assert "Unexpected type error" in errors[0]
