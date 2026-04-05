"""Unit tests for WorkflowExecutor - UPDATE pattern steps."""

import pytest
import pytest_mock

from causaliq_workflow.workflow import WorkflowExecutor

# ===========================================================================
# UPDATE pattern tests
# ===========================================================================


# Test _is_update_step returns True when matrix is present.
def test_is_update_step_true_with_matrix() -> None:
    from causaliq_core import ActionPattern

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = (
        lambda p, a: ActionPattern.UPDATE
    )

    step = {
        "uses": "test-provider",
        "with": {"action": "update_action", "input": "cache.db"},
    }
    matrix = {"network": ["asia"]}  # Matrix present

    result = executor._is_update_step(step, matrix)
    assert result is True


# Test _is_update_step returns False for non-UPDATE pattern.
def test_is_update_step_false_for_create_pattern() -> None:
    from causaliq_core import ActionPattern

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = (
        lambda p, a: ActionPattern.CREATE
    )

    step = {
        "uses": "test-provider",
        "with": {"action": "create_action", "input": "cache.db"},
    }

    result = executor._is_update_step(step, {})
    assert result is False


# Test _is_update_step returns False when no input.
def test_is_update_step_false_without_input() -> None:
    from causaliq_core import ActionPattern

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = (
        lambda p, a: ActionPattern.UPDATE
    )

    step = {
        "uses": "test-provider",
        "with": {"action": "update_action"},  # No input
    }

    result = executor._is_update_step(step, {})
    assert result is False


# Test _is_update_step returns False when input not .db file.
def test_is_update_step_false_for_non_db_input() -> None:
    from causaliq_core import ActionPattern

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = (
        lambda p, a: ActionPattern.UPDATE
    )

    step = {
        "uses": "test-provider",
        "with": {"action": "update_action", "input": "data.csv"},  # Not .db
    }

    result = executor._is_update_step(step, {})
    assert result is False


# Test _is_update_step returns True for valid UPDATE step.
def test_is_update_step_true() -> None:
    from causaliq_core import ActionPattern

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = (
        lambda p, a: ActionPattern.UPDATE
    )

    step = {
        "uses": "test-provider",
        "with": {"action": "update_action", "input": "cache.db"},
    }

    result = executor._is_update_step(step, {})
    assert result is True


# Test _is_update_step returns False when no uses.
def test_is_update_step_false_without_uses() -> None:
    executor = WorkflowExecutor()
    step = {"with": {"action": "update_action", "input": "cache.db"}}
    result = executor._is_update_step(step, {})
    assert result is False


# Test _is_update_step returns False when no action name.
def test_is_update_step_false_without_action() -> None:
    from causaliq_core import ActionPattern

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = (
        lambda p, a: ActionPattern.UPDATE
    )

    step = {
        "uses": "test-provider",
        "with": {"input": "cache.db"},
    }  # No action

    result = executor._is_update_step(step, {})
    assert result is False


# Test _execute_update_step handles missing cache file.
def test_execute_update_step_missing_cache() -> None:
    from causaliq_workflow.registry import WorkflowContext

    # Create a mock action to register
    class MockUpdateAction:
        name = "mock-update"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockUpdateAction

    step = {"uses": "mock-provider"}
    resolved_inputs = {"action": "update", "input": "/nonexistent/cache.db"}
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    assert result["status"] == "error"
    assert "do not exist" in result["error"]
    assert result["entries_processed"] == 0


# Test _execute_update_step processes entries and updates cache.
def test_execute_update_step_processes_entries(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create input cache with an entry
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        cache.put({"network": "asia"}, entry)

    # Create mock action that returns metadata
    class UpdateAction:
        name = "update-action"
        action_patterns = {}

        def run(self, action, parameters, **kwargs):
            return (
                "success",
                {"f1_score": 0.95, "precision": 0.9},
                [{"type": "metrics", "format": "json", "content": "{}"}],
            )

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"uses": "update-provider"}
    resolved_inputs = {"action": "evaluate", "input": str(cache_path)}
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    assert result["status"] == "success"
    assert result["entries_processed"] == 1
    assert result["entries_updated"] == 1

    # Verify entry was updated with action metadata
    with WorkflowCache(str(cache_path)) as cache:
        entry = cache.get({"network": "asia"})
        assert entry is not None
        assert "update-action" in entry.metadata
        assert entry.metadata["update-action"]["evaluate"]["f1_score"] == 0.95
        assert "metrics" in entry.objects


# Test _execute_update_step conservative execution skips updated entries.
def test_execute_update_step_skips_already_updated(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create cache with entry already having action metadata
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.metadata["update-action"] = {"evaluate": {"f1_score": 0.9}}
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {"new_score": 1.0}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"uses": "update-provider"}
    resolved_inputs = {"action": "evaluate", "input": str(cache_path)}
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    # Entry should be skipped (conservative execution)
    assert result["status"] == "skipped"
    assert result["entries_skipped"] == 1
    assert result["entries_updated"] == 0


# Test _execute_update_step with filter expression.
def test_execute_update_step_with_filter(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create cache with multiple entries
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry1 = CacheEntry()
        entry1.metadata["sample_size"] = 100
        cache.put({"network": "asia", "sample_size": 100}, entry1)

        entry2 = CacheEntry()
        entry2.metadata["sample_size"] = 1000
        cache.put({"network": "cancer", "sample_size": 1000}, entry2)

    class UpdateAction:
        name = "update-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {"evaluated": True}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"uses": "update-provider"}
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
        "filter": "sample_size > 500",  # Only 1000 sample matches
    }
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    assert result["entries_processed"] == 2
    assert result["entries_skipped"] == 1  # asia filtered out
    assert result["entries_updated"] == 1  # Only cancer updated


# Test _resolve_filter resolves random() from cache entries.
def test_resolve_filter_with_random(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        for i in range(20):
            e = CacheEntry()
            e.metadata["seed"] = i
            cache.put({"seed": str(i)}, e)

    executor = WorkflowExecutor()

    with WorkflowCache(str(cache_path)) as cache:
        entries = cache.list_entries()
        resolved, extra = executor._resolve_filter(
            "seed in random(5, 0)", cache, entries
        )

    assert "random(" not in resolved
    assert len(extra) == 1
    key = list(extra.keys())[0]
    assert key.startswith("_random_")
    assert len(extra[key]) == 5


# Test _resolve_filter returns expression unchanged without random().
def test_resolve_filter_without_random(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        e = CacheEntry()
        cache.put({"network": "asia"}, e)

    executor = WorkflowExecutor()

    with WorkflowCache(str(cache_path)) as cache:
        entries = cache.list_entries()
        resolved, extra = executor._resolve_filter(
            "network == 'asia'", cache, entries
        )

    assert resolved == "network == 'asia'"
    assert extra == {}


# Test _resolve_filter returns None unchanged when no filter.
def test_resolve_filter_none() -> None:
    executor = WorkflowExecutor()
    resolved, extra = executor._resolve_filter(
        None, None, []  # type: ignore[arg-type]
    )
    assert resolved is None
    assert extra == {}


# Test _execute_update_step with random() filter expression.
def test_execute_update_step_with_random_filter(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        for i in range(20):
            e = CacheEntry()
            e.metadata["seed"] = i
            cache.put({"seed": str(i)}, e)

    class UpdateAction:
        name = "update-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["prov"] = UpdateAction

    step = {"uses": "prov"}
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
        "filter": "seed in random(5, 0)",
    }
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    assert result["entries_processed"] == 20
    assert result["entries_skipped"] == 15
    assert result["entries_updated"] == 5


# Test _execute_job routes UPDATE step to _execute_update_step.
def test_execute_job_routes_update_step(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create input cache with entry
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {"score": 0.9}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    workflow = {
        "steps": [
            {
                "name": "eval-step",
                "uses": "update-provider",
                "with": {
                    "action": "evaluate",
                    "input": str(cache_path),
                },
            }
        ],
    }

    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_job(workflow, {}, context, {})

    # Verify UPDATE step was executed
    assert "eval-step" in result["steps"]
    assert result["steps"]["eval-step"]["status"] == "success"
    assert result["steps"]["eval-step"]["entries_updated"] == 1


# Test _execute_update_step returns error when input_path is None.
def test_execute_update_step_no_input_path() -> None:
    from causaliq_workflow.registry import WorkflowContext

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    step = {"uses": "mock-provider"}
    resolved_inputs = {"action": "update"}  # No input parameter
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    assert result["status"] == "error"
    assert "requires 'input'" in result["error"]


# Test _execute_update_step handles entry get returning None.
def test_execute_update_step_entry_get_returns_none(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
    mocker: "pytest_mock.MockerFixture",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        cache.put({"network": "asia"}, entry)

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    step = {"uses": "mock-provider"}
    resolved_inputs = {"action": "update", "input": str(cache_path)}
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    # Mock cache.get to return None
    def mock_get(self, key_data):
        return None

    mocker.patch.object(WorkflowCache, "get", mock_get)

    result = executor._execute_update_step(step, resolved_inputs, context)

    # Entry skipped because get returned None (continues to next entry)
    assert result["entries_processed"] == 1
    assert result["entries_updated"] == 0


# Test _execute_update_step handles filter evaluation exception.
def test_execute_update_step_filter_exception(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        cache.put({"network": "asia"}, entry)

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    step = {"uses": "mock-provider"}
    resolved_inputs = {
        "action": "update",
        "input": str(cache_path),
        "filter": "undefined_variable > 0",  # Will raise exception
    }
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    # Entry skipped due to filter exception
    assert result["entries_processed"] == 1
    assert result["entries_skipped"] == 1
    assert result["entries_updated"] == 0


# Test _execute_update_step handles action returning non-success status.
def test_execute_update_step_action_not_success(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        cache.put({"network": "asia"}, entry)

    class FailingAction:
        name = "failing-action"

        def run(self, action, parameters, **kwargs):
            return ("skipped", {"reason": "nothing to do"}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["failing-provider"] = FailingAction

    step = {"uses": "failing-provider"}
    resolved_inputs = {"action": "update", "input": str(cache_path)}
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    # Not updated because action did not return success
    assert result["entries_processed"] == 1
    assert result["entries_updated"] == 0


# Test _execute_update_step handles action raising exception.
def test_execute_update_step_action_raises_exception(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        cache.put({"network": "asia"}, entry)

    class ExceptionAction:
        name = "exception-action"

        def run(self, action, parameters, **kwargs):
            raise RuntimeError("Action failed unexpectedly")

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["exception-provider"] = ExceptionAction

    step = {"uses": "exception-provider"}
    resolved_inputs = {"action": "update", "input": str(cache_path)}
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    # Entry errored, recorded in errors list
    assert result["entries_processed"] == 1
    assert result["entries_updated"] == 0
    assert result["status"] == "error"
    assert "errors" in result
    assert len(result["errors"]) == 1


# Test _execute_update_step handles update_entry returning False.
def test_execute_update_step_update_entry_returns_false(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
    mocker: "pytest_mock.MockerFixture",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        cache.put({"network": "asia"}, entry)

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {"score": 0.9}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    step = {"uses": "mock-provider"}
    resolved_inputs = {"action": "update", "input": str(cache_path)}
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    # Mock update_entry to return False
    mocker.patch.object(WorkflowCache, "update_entry", return_value=False)

    result = executor._execute_update_step(step, resolved_inputs, context)

    # Entry processed but not updated
    assert result["entries_processed"] == 1
    assert result["entries_updated"] == 0


# Test _execute_job calls step_logger for UPDATE steps.
def test_execute_job_update_step_with_logger(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {"score": 0.9}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    workflow = {
        "steps": [
            {
                "name": "eval-step",
                "uses": "update-provider",
                "with": {
                    "action": "evaluate",
                    "input": str(cache_path),
                },
            }
        ],
    }

    context = WorkflowContext(mode="run", matrix={}, matrix_values={})
    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    executor._execute_job(workflow, {}, context, {}, capture_logger)

    # Logger called per-entry with EXECUTED status and entry matrix values
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "eval-step",
        "EXECUTED",
        {"network": "asia"},
    )


# Test _execute_update_step with multiple input caches.
def test_execute_update_step_multiple_caches(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create two input caches with entries
    cache1_path = tmp_path / "cache1.db"  # type: ignore[operator]
    cache2_path = tmp_path / "cache2.db"  # type: ignore[operator]

    with WorkflowCache(str(cache1_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        cache.put({"network": "asia"}, entry)

    with WorkflowCache(str(cache2_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        cache.put({"network": "alarm"}, entry)

    # Create mock action that returns metadata
    class UpdateAction:
        name = "update-action"
        action_patterns = {}

        def run(self, action, parameters, **kwargs):
            return ("success", {"f1_score": 0.95}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"uses": "update-provider"}
    resolved_inputs = {
        "action": "evaluate",
        "input": [str(cache1_path), str(cache2_path)],
    }
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    assert result["status"] == "success"
    assert result["entries_processed"] == 2
    assert result["entries_updated"] == 2

    # Verify both caches have updated entries
    with WorkflowCache(str(cache1_path)) as cache:
        entry = cache.get({"network": "asia"})
        assert entry is not None
        assert "update-action" in entry.metadata

    with WorkflowCache(str(cache2_path)) as cache:
        entry = cache.get({"network": "alarm"})
        assert entry is not None
        assert "update-action" in entry.metadata


# Test _execute_update_step reports error for all missing caches.
def test_execute_update_step_multiple_missing_caches(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.registry import WorkflowContext

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    step = {"uses": "mock-provider"}
    resolved_inputs = {
        "action": "update",
        "input": ["/nonexistent/cache1.db", "/nonexistent/cache2.db"],
    }
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    assert result["status"] == "error"
    assert "cache1.db" in result["error"]
    assert "cache2.db" in result["error"]


# Test _execute_update_step rejects invalid input type.
def test_execute_update_step_invalid_input_type() -> None:
    from causaliq_workflow.registry import WorkflowContext

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    step = {"uses": "mock-provider"}
    resolved_inputs = {"action": "update", "input": 12345}  # Invalid type
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    assert result["status"] == "error"
    assert "must be string or list" in result["error"]


# Test _scan_update_step_entries with multiple caches.
def test_scan_update_step_entries_multiple_caches(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create two caches with entries
    cache1_path = tmp_path / "cache1.db"  # type: ignore[operator]
    cache2_path = tmp_path / "cache2.db"  # type: ignore[operator]

    with WorkflowCache(str(cache1_path)) as cache:
        cache.put({"network": "asia"}, CacheEntry())

    with WorkflowCache(str(cache2_path)) as cache:
        cache.put({"network": "alarm"}, CacheEntry())
        cache.put({"network": "sachs"}, CacheEntry())

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    step = {"uses": "mock-provider"}
    resolved_inputs = {
        "action": "update",
        "input": [str(cache1_path), str(cache2_path)],
    }

    context = WorkflowContext(mode="dry-run", matrix={}, matrix_values={})

    result = executor._scan_update_step_entries(step, resolved_inputs, context)

    # Total 3 entries across both caches
    assert result["would_process"] == 3
    assert result["would_skip"] == 0


# Test _scan_update_step_entries returns zeros for invalid input type.
def test_scan_update_step_entries_invalid_input_type() -> None:
    from causaliq_workflow.registry import WorkflowContext

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    step = {"uses": "mock-provider"}
    resolved_inputs = {"action": "update", "input": 12345}  # Invalid type
    context = WorkflowContext(mode="dry-run", matrix={}, matrix_values={})

    result = executor._scan_update_step_entries(step, resolved_inputs, context)

    assert result["would_process"] == 0
    assert result["would_skip"] == 0


# ===========================================================================
# MATRIX-AWARE UPDATE TESTS
# ===========================================================================


# Test _execute_update_step targets only the matching matrix entry.
def test_execute_update_step_targets_matrix_entry(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry1 = CacheEntry()
        entry1.add_object("graph", "graphml", "<asia/>")
        cache.put({"network": "asia"}, entry1)

        entry2 = CacheEntry()
        entry2.add_object("graph", "graphml", "<alarm/>")
        cache.put({"network": "alarm"}, entry2)

    class UpdateAction:
        name = "update-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {"score": 0.9}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-prov"] = UpdateAction

    step = {"uses": "update-prov"}
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
    }
    # Context targets only the "asia" entry
    context = WorkflowContext(
        mode="run",
        matrix={"network": ["asia", "alarm"]},
        matrix_values={"network": "asia"},
    )

    result = executor._execute_update_step(step, resolved_inputs, context)

    assert result["status"] == "success"
    assert result["entries_processed"] == 1
    assert result["entries_updated"] == 1

    # Only the asia entry should have action metadata
    with WorkflowCache(str(cache_path)) as cache:
        asia = cache.get({"network": "asia"})
        assert asia is not None
        assert "update-action" in asia.metadata

        alarm = cache.get({"network": "alarm"})
        assert alarm is not None
        assert "update-action" not in alarm.metadata


# Test _scan_update_step_entries targets only the matching matrix entry.
def test_scan_update_step_entries_targets_matrix_entry(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        cache.put({"network": "asia"}, CacheEntry())
        cache.put({"network": "alarm"}, CacheEntry())

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-prov"] = MockAction

    step = {"uses": "mock-prov"}
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
    }
    # Context targets only "asia"
    context = WorkflowContext(
        mode="dry-run",
        matrix={"network": ["asia", "alarm"]},
        matrix_values={"network": "asia"},
    )

    result = executor._scan_update_step_entries(step, resolved_inputs, context)

    # Only the asia entry should be counted
    assert result["would_process"] == 1
    assert result["would_skip"] == 0


# Test _execute_job routes UPDATE step correctly within matrix.
def test_execute_job_update_step_with_matrix(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry1 = CacheEntry()
        entry1.add_object("graph", "graphml", "<asia/>")
        cache.put({"network": "asia"}, entry1)

        entry2 = CacheEntry()
        entry2.add_object("graph", "graphml", "<alarm/>")
        cache.put({"network": "alarm"}, entry2)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {"f1": 0.95}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-prov"] = UpdateAction

    workflow = {
        "matrix": {"network": ["asia", "alarm"]},
        "steps": [
            {
                "name": "eval-step",
                "uses": "update-prov",
                "with": {
                    "action": "evaluate",
                    "input": str(cache_path),
                },
            }
        ],
    }

    # Run for the "asia" matrix combination
    context = WorkflowContext(
        mode="run",
        matrix={"network": ["asia", "alarm"]},
        matrix_values={"network": "asia"},
    )
    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    executor._execute_job(workflow, {}, context, {}, capture_logger)

    # Logger called once for the asia entry only
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "eval-step",
        "EXECUTED",
        {"network": "asia"},
    )

    # Only asia should have metadata
    with WorkflowCache(str(cache_path)) as cache:
        asia = cache.get({"network": "asia"})
        assert asia is not None
        assert "update-action" in asia.metadata

        alarm = cache.get({"network": "alarm"})
        assert alarm is not None
        assert "update-action" not in alarm.metadata


# Test scan logs WOULD EXECUTE when cache does not exist yet.
def test_scan_update_entries_missing_cache_with_matrix(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.registry import WorkflowContext

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-prov"] = MockAction

    step = {"name": "eval-step", "uses": "mock-prov"}
    nonexistent = str(tmp_path / "not-yet.db")  # type: ignore[operator]
    resolved_inputs = {
        "action": "evaluate",
        "input": nonexistent,
    }
    context = WorkflowContext(
        mode="dry-run",
        matrix={"network": ["asia"]},
        matrix_values={"network": "asia"},
    )
    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    result = executor._scan_update_step_entries(
        step, resolved_inputs, context, capture_logger
    )

    assert result["would_process"] == 1
    assert result["would_skip"] == 0
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "eval-step",
        "WOULD EXECUTE",
        {"network": "asia"},
    )


# Test scan logs WOULD EXECUTE when entry does not exist yet.
def test_scan_update_entries_missing_entry_with_matrix(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create cache with no entries
    cache_path = tmp_path / "empty.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)):
        pass  # empty cache

    class MockAction:
        name = "mock-action"

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-prov"] = MockAction

    step = {"name": "eval-step", "uses": "mock-prov"}
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
    }
    context = WorkflowContext(
        mode="dry-run",
        matrix={"network": ["asia"]},
        matrix_values={"network": "asia"},
    )
    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    result = executor._scan_update_step_entries(
        step, resolved_inputs, context, capture_logger
    )

    assert result["would_process"] == 1
    assert result["would_skip"] == 0
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "eval-step",
        "WOULD EXECUTE",
        {"network": "asia"},
    )
