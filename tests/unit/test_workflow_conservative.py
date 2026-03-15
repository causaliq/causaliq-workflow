"""Unit tests for WorkflowExecutor - conservative execution and logging."""

import pytest

from causaliq_workflow.workflow import WorkflowExecutor

# ===========================================================================
# CONSERVATIVE EXECUTION TESTS
# ===========================================================================


# Test conservative execution for CREATE pattern skips when entry exists.
def test_create_pattern_conservative_skip_when_entry_exists(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create output cache with existing entry
    output_path = tmp_path / "output.db"  # type: ignore[operator]
    with WorkflowCache(str(output_path)) as cache:
        entry = CacheEntry()
        entry.metadata["existing"] = True
        cache.put({"algorithm": "pc"}, entry)

    class CreateAction:
        name = "create-action"
        action_patterns = {}

        def run(self, action, parameters, **kwargs):
            # This should NOT be called due to conservative skip
            raise AssertionError("Action should not be executed")

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["create-provider"] = CreateAction

    workflow = {
        "steps": [
            {
                "name": "create-step",
                "uses": "create-provider",
                "with": {
                    "action": "generate",
                    "output": str(output_path),
                },
            }
        ],
    }
    matrix_values = {"algorithm": "pc"}
    context = WorkflowContext(
        mode="run", matrix={"algorithm": ["pc"]}, matrix_values=matrix_values
    )

    result = executor._execute_job(workflow, matrix_values, context, {}, None)

    # Step should be skipped
    assert result["steps"]["create-step"]["status"] == "skipped"


# Test conservative execution for CREATE pattern with logger.
def test_create_pattern_conservative_skip_with_logger(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create output cache with existing entry
    output_path = tmp_path / "output.db"  # type: ignore[operator]
    with WorkflowCache(str(output_path)) as cache:
        entry = CacheEntry()
        cache.put({"network": "asia"}, entry)

    class CreateAction:
        name = "create-action"
        action_patterns = {}

        def run(self, action, parameters, **kwargs):
            raise AssertionError("Action should not be executed")

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["create-provider"] = CreateAction

    workflow = {
        "steps": [
            {
                "name": "gen-step",
                "uses": "create-provider",
                "with": {
                    "action": "generate",
                    "output": str(output_path),
                },
            }
        ],
    }
    matrix_values = {"network": "asia"}
    context = WorkflowContext(
        mode="run", matrix={"network": ["asia"]}, matrix_values=matrix_values
    )

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    result = executor._execute_job(
        workflow, matrix_values, context, {}, capture_logger
    )

    # Step should be skipped with logger called
    assert result["steps"]["gen-step"]["status"] == "skipped"
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "generate",
        "gen-step",
        "SKIPPED",
        {"network": "asia"},
    )


# Test conservative execution for AGGREGATE pattern skips when entry exists.
def test_aggregate_pattern_conservative_skip_when_entry_exists(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create input cache with entries to aggregate
    input_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(input_path)) as cache:
        entry1 = CacheEntry()
        entry1.metadata["score"] = 0.8
        cache.put({"algorithm": "pc", "network": "asia"}, entry1)

        entry2 = CacheEntry()
        entry2.metadata["score"] = 0.9
        cache.put({"algorithm": "pc", "network": "cancer"}, entry2)

    # Create output cache with existing aggregated entry
    output_path = tmp_path / "output.db"  # type: ignore[operator]
    with WorkflowCache(str(output_path)) as cache:
        entry = CacheEntry()
        entry.metadata["aggregated"] = True
        cache.put({"algorithm": "pc"}, entry)

    class AggregateAction:
        name = "aggregate-action"
        action_patterns = {}

        def run(self, action, parameters, **kwargs):
            raise AssertionError("Action should not be executed")

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["agg-provider"] = AggregateAction

    workflow = {
        "matrix": {"algorithm": ["pc"]},
        "steps": [
            {
                "name": "agg-step",
                "uses": "agg-provider",
                "with": {
                    "action": "summarise",
                    "input": str(input_path),
                    "output": str(output_path),
                },
            }
        ],
    }
    matrix_values = {"algorithm": "pc"}
    context = WorkflowContext(
        mode="run", matrix={"algorithm": ["pc"]}, matrix_values=matrix_values
    )

    result = executor._execute_job(workflow, matrix_values, context, {}, None)

    # Step should be skipped
    assert result["steps"]["agg-step"]["status"] == "skipped"


# Test conservative execution for AGGREGATE pattern with logger.
def test_aggregate_pattern_conservative_skip_with_logger(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create input cache
    input_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(input_path)) as cache:
        entry = CacheEntry()
        cache.put({"algorithm": "fges", "network": "asia"}, entry)

    # Create output cache with existing entry
    output_path = tmp_path / "output.db"  # type: ignore[operator]
    with WorkflowCache(str(output_path)) as cache:
        entry = CacheEntry()
        cache.put({"algorithm": "fges"}, entry)

    class AggregateAction:
        name = "aggregate-action"
        action_patterns = {}

        def run(self, action, parameters, **kwargs):
            raise AssertionError("Action should not be executed")

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["agg-provider"] = AggregateAction

    workflow = {
        "matrix": {"algorithm": ["fges"]},
        "steps": [
            {
                "name": "agg-step",
                "uses": "agg-provider",
                "with": {
                    "action": "merge",
                    "input": str(input_path),
                    "output": str(output_path),
                },
            }
        ],
    }
    matrix_values = {"algorithm": "fges"}
    context = WorkflowContext(
        mode="run", matrix={"algorithm": ["fges"]}, matrix_values=matrix_values
    )

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    result = executor._execute_job(
        workflow, matrix_values, context, {}, capture_logger
    )

    # Step should be skipped with logger called
    assert result["steps"]["agg-step"]["status"] == "skipped"
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "merge",
        "agg-step",
        "SKIPPED",
        {"algorithm": "fges"},
    )


# Test CREATE pattern executes when no entry exists.
def test_create_pattern_executes_when_no_entry_exists(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.registry import WorkflowContext

    # Output cache doesn't exist yet
    output_path = tmp_path / "output.db"  # type: ignore[operator]

    class CreateAction:
        name = "create-action"
        action_patterns = {}

        def run(self, action, parameters, **kwargs):
            return (
                "success",
                {"created": True},
                [
                    {
                        "type": "dag",
                        "format": "graphml",
                        "content": "<graphml/>",
                    }
                ],
            )

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["create-provider"] = CreateAction

    workflow = {
        "steps": [
            {
                "name": "create-step",
                "uses": "create-provider",
                "with": {
                    "action": "generate",
                    "output": str(output_path),
                },
            }
        ],
    }
    matrix_values = {"algorithm": "pc"}
    context = WorkflowContext(
        mode="run", matrix={"algorithm": ["pc"]}, matrix_values=matrix_values
    )

    result = executor._execute_job(workflow, matrix_values, context, {}, None)

    # Step should execute successfully
    assert result["steps"]["create-step"]["status"] == "success"


# ===========================================================================
# FORCE MODE TESTS
# ===========================================================================


# Test force mode bypasses CREATE pattern conservative execution.
def test_force_mode_bypasses_create_conservative_skip(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create output cache with existing entry
    output_path = tmp_path / "output.db"  # type: ignore[operator]
    with WorkflowCache(str(output_path)) as cache:
        entry = CacheEntry()
        entry.metadata["existing"] = True
        cache.put({"algorithm": "pc"}, entry)

    class CreateAction:
        name = "create-action"
        action_patterns = {}

        def run(self, action, parameters, **kwargs):
            # This SHOULD be called despite existing entry (force mode)
            return (
                "success",
                {"forced": True},
                [
                    {
                        "type": "dag",
                        "format": "graphml",
                        "content": "<graphml/>",
                    }
                ],
            )

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["create-provider"] = CreateAction

    workflow = {
        "steps": [
            {
                "name": "create-step",
                "uses": "create-provider",
                "with": {
                    "action": "generate",
                    "output": str(output_path),
                },
            }
        ],
    }
    matrix_values = {"algorithm": "pc"}
    # Use force mode
    context = WorkflowContext(
        mode="force", matrix={"algorithm": ["pc"]}, matrix_values=matrix_values
    )

    result = executor._execute_job(workflow, matrix_values, context, {}, None)

    # Step should execute (not skipped) despite existing entry
    assert result["steps"]["create-step"]["status"] == "success"


# Test force mode bypasses AGGREGATE pattern conservative execution.
def test_force_mode_bypasses_aggregate_conservative_skip(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create input cache
    input_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(input_path)) as cache:
        entry = CacheEntry()
        cache.put({"algorithm": "pc", "network": "asia"}, entry)

    # Create output cache with existing entry
    output_path = tmp_path / "output.db"  # type: ignore[operator]
    with WorkflowCache(str(output_path)) as cache:
        entry = CacheEntry()
        entry.metadata["aggregated"] = True
        cache.put({"algorithm": "pc"}, entry)

    class AggregateAction:
        name = "aggregate-action"
        action_patterns = {}

        def run(self, action, parameters, **kwargs):
            # This SHOULD be called despite existing entry (force mode)
            return (
                "success",
                {"forced": True},
                [{"type": "summary", "format": "json", "content": "{}"}],
            )

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["agg-provider"] = AggregateAction

    workflow = {
        "matrix": {"algorithm": ["pc"]},
        "steps": [
            {
                "name": "agg-step",
                "uses": "agg-provider",
                "with": {
                    "action": "summarise",
                    "input": str(input_path),
                    "output": str(output_path),
                },
            }
        ],
    }
    matrix_values = {"algorithm": "pc"}
    # Use force mode
    context = WorkflowContext(
        mode="force",
        matrix={"algorithm": ["pc"]},
        matrix_values=matrix_values,
    )

    result = executor._execute_job(workflow, matrix_values, context, {}, None)

    # Step should execute (not skipped) despite existing entry
    assert result["steps"]["agg-step"]["status"] == "success"


# Test force mode bypasses UPDATE pattern conservative execution.
def test_force_mode_bypasses_update_conservative_skip(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

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
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            # This SHOULD be called despite existing metadata (force mode)
            return ("success", {"forced_score": 1.0}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"uses": "update-provider"}
    resolved_inputs = {"action": "evaluate", "input": str(cache_path)}
    # Use force mode
    context = WorkflowContext(mode="force", matrix={}, matrix_values={})

    result = executor._execute_update_step(step, resolved_inputs, context)

    # Entry should be updated (not skipped) despite existing metadata
    assert result["status"] == "success"
    assert result["entries_updated"] == 1
    assert result["entries_skipped"] == 0


# ===========================================================================
# STEP LOGGER COVERAGE TESTS
# ===========================================================================


# Test UPDATE step dry-run with step_logger.
def test_update_step_dry_run_with_step_logger(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create input cache with an entry
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    workflow = {
        "matrix": {},
        "steps": [
            {
                "name": "update-step",
                "uses": "update-provider",
                "with": {
                    "action": "evaluate",
                    "input": str(cache_path),
                },
            }
        ],
    }

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    context = WorkflowContext(mode="dry-run", matrix={}, matrix_values={})

    executor._execute_job(workflow, {}, context, {}, capture_logger)

    # Logger called per-entry with WOULD EXECUTE and entry matrix values
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "update-step",
        "WOULD EXECUTE",
        {"network": "asia"},
    )


# Test UPDATE step completion logging with FORCED status.
def test_update_step_logging_forced_status(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create input cache with existing entry
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {"f1": 0.9}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    workflow = {
        "matrix": {},
        "steps": [
            {
                "name": "update-step",
                "uses": "update-provider",
                "with": {
                    "action": "evaluate",
                    "input": str(cache_path),
                },
            }
        ],
    }

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    context = WorkflowContext(mode="force", matrix={}, matrix_values={})

    executor._execute_job(workflow, {}, context, {}, capture_logger)

    # Logger called per-entry with FORCED status and entry matrix values
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "update-step",
        "FORCED",
        {"network": "asia"},
    )


# Test UPDATE step logging with SKIPPED status (conservative skip).
def test_update_step_logging_skipped_status(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create input cache with entry ALREADY HAVING action metadata
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        # Add metadata for action already processed
        entry.metadata["update-action"] = {"evaluate": {"f1": 0.8}}
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {"f1": 0.9}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    workflow = {
        "matrix": {},
        "steps": [
            {
                "name": "update-step",
                "uses": "update-provider",
                "with": {
                    "action": "evaluate",
                    "input": str(cache_path),
                },
            }
        ],
    }

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    # Conservative mode should skip already-processed entry
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    executor._execute_job(workflow, {}, context, {}, capture_logger)

    # Logger called per-entry with SKIPPED status and entry matrix values
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "update-step",
        "SKIPPED",
        {"network": "asia"},
    )


# Test UPDATE step logging with FAILED status (action raises exception).
def test_update_step_logging_failed_status(
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
            # Raise exception to trigger error status
            raise RuntimeError("Action execution failed")

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    workflow = {
        "matrix": {},
        "steps": [
            {
                "name": "update-step",
                "uses": "update-provider",
                "with": {
                    "action": "evaluate",
                    "input": str(cache_path),
                },
            }
        ],
    }

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    executor._execute_job(workflow, {}, context, {}, capture_logger)

    # Logger called per-entry with FAILED status and entry matrix values
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "update-step",
        "FAILED",
        {"network": "asia"},
    )


# Test dry-run mode with existing cache entry results in WOULD SKIP.
def test_dry_run_would_skip_with_existing_entry(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create output cache with EXISTING entry for matrix values
    output_path = tmp_path / "output.db"  # type: ignore[operator]
    with WorkflowCache(str(output_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        cache.put({"network": "asia"}, entry)

    class MockAction:
        name = "mock-action"
        action_patterns = {}  # type: ignore[var-annotated]

        def run(self, action, parameters, **kwargs):
            # Should NOT be called in dry-run
            raise AssertionError("Action should not run in dry-run mode")

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "create-step",
                "uses": "mock-provider",
                "with": {
                    "action": "create",
                    "output": str(output_path),
                },
            }
        ],
    }

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    context = WorkflowContext(
        mode="dry-run",
        matrix=workflow["matrix"],
        matrix_values={"network": "asia"},
    )

    executor._execute_job(
        workflow, {"network": "asia"}, context, {}, capture_logger
    )

    # Logger should be called with WOULD SKIP (entry already exists)
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "create",
        "create-step",
        "WOULD SKIP",
        {"network": "asia"},
    )


# Test step execution logging with FORCED status in force mode.
def test_step_execution_logging_forced_status(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.registry import WorkflowContext

    class MockAction:
        name = "mock-action"
        action_patterns = {}  # type: ignore[var-annotated]

        def run(self, action, parameters, **kwargs):
            return ("success", {"result": "ok"}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    workflow = {
        "matrix": {},
        "steps": [
            {
                "name": "test-step",
                "uses": "mock-provider",
                "with": {"action": "process"},
            }
        ],
    }

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    # Use force mode
    context = WorkflowContext(mode="force", matrix={}, matrix_values={})

    executor._execute_job(workflow, {}, context, {}, capture_logger)

    # Logger should be called with FORCED status
    assert len(log_calls) == 1
    assert log_calls[0] == ("process", "test-step", "FORCED", {})


# Test step execution logging with FAILED status.
def test_step_execution_logging_failed_status(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.registry import WorkflowContext

    class MockAction:
        name = "mock-action"
        action_patterns = {}  # type: ignore[var-annotated]

        def run(self, action, parameters, **kwargs):
            # Return error status
            return ("error", {"error": "something failed"}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["mock-provider"] = MockAction

    workflow = {
        "matrix": {},
        "steps": [
            {
                "name": "test-step",
                "uses": "mock-provider",
                "with": {"action": "process"},
            }
        ],
    }

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    executor._execute_job(workflow, {}, context, {}, capture_logger)

    # Logger should be called with FAILED status
    assert len(log_calls) == 1
    assert log_calls[0] == ("process", "test-step", "FAILED", {})


# ===========================================================================
# SCAN UPDATE STEP ENTRIES TESTS
# ===========================================================================


# Test _scan_update_step_entries returns zeros when input path is None.
def test_scan_update_step_entries_no_input_path() -> None:
    from causaliq_core import ActionPattern

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "test-step", "uses": "update-provider"}
    resolved_inputs = {"action": "evaluate"}  # No input path

    result = executor._scan_update_step_entries(step, resolved_inputs)

    assert result == {"would_process": 0, "would_skip": 0}


# Test _scan_update_step_entries returns zeros when input path doesn't exist.
def test_scan_update_step_entries_nonexistent_path(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "test-step", "uses": "update-provider"}
    nonexistent = str(tmp_path / "does-not-exist.db")  # type: ignore[operator]
    resolved_inputs = {"action": "evaluate", "input": nonexistent}

    result = executor._scan_update_step_entries(step, resolved_inputs)

    assert result == {"would_process": 0, "would_skip": 0}


# Test _scan_update_step_entries skips entries with existing action metadata.
def test_scan_update_step_entries_skips_already_processed(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    # Create cache with entry that has existing action metadata
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        # Add action metadata to simulate already processed
        entry.metadata["update-action"] = {"evaluate": {"done": True}}
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "test-step", "uses": "update-provider"}
    resolved_inputs = {"action": "evaluate", "input": str(cache_path)}

    result = executor._scan_update_step_entries(step, resolved_inputs)

    # Entry already has action metadata, so it would be skipped
    assert result == {"would_process": 0, "would_skip": 1}


# Test _scan_update_step_entries handles filter expression exceptions.
def test_scan_update_step_entries_filter_exception(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    # Create cache with entry
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "test-step", "uses": "update-provider"}
    # Invalid filter that will cause exception during evaluation
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
        "filter": "nonexistent_var > 10",
    }

    result = executor._scan_update_step_entries(step, resolved_inputs)

    # Filter exception should cause entry to be skipped
    assert result == {"would_process": 0, "would_skip": 1}


# Test _scan_update_step_entries counts entries filtered out by expression.
def test_scan_update_step_entries_filter_excludes(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    # Create cache with entry that won't match filter
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        entry.metadata["score"] = 5  # Will fail filter: score > 10
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "test-step", "uses": "update-provider"}
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
        "filter": "score > 10",
    }

    result = executor._scan_update_step_entries(step, resolved_inputs)

    # Entry doesn't match filter, so it would be skipped
    assert result == {"would_process": 0, "would_skip": 1}


# Test _scan_update_step_entries handles None entry from cache.get().
def test_scan_update_step_entries_handles_none_entry(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
    monkeypatch,
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    # Create cache with entry
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.add_object("graph", "graphml", "<graphml/>")
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "test-step", "uses": "update-provider"}
    resolved_inputs = {"action": "evaluate", "input": str(cache_path)}

    # Mock cache.get to return None (simulate missing entry)
    def mock_get(self, matrix_values):
        return None

    monkeypatch.setattr(WorkflowCache, "get", mock_get)

    result = executor._scan_update_step_entries(step, resolved_inputs)

    # Entry is None, so should be skipped (no process, no skip counted)
    assert result == {"would_process": 0, "would_skip": 0}


# ===========================================================================
# PER-ENTRY LOGGING WITH FILTER TESTS
# ===========================================================================


# Test UPDATE step filter skip logs per-entry with step_logger.
def test_update_step_filter_skip_logs_per_entry(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.metadata["score"] = 5  # Won't match filter: score > 10
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "filter-step", "uses": "update-provider"}
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
        "filter": "score > 10",
    }
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    executor._execute_update_step(
        step, resolved_inputs, context, capture_logger
    )

    # Step_logger called per-entry with IGNORED for filter mismatch
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "filter-step",
        "IGNORED",
        {"network": "asia"},
    )


# Test UPDATE step filter exception logs per-entry with step_logger.
def test_update_step_filter_exception_logs_per_entry(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        # No 'score' in metadata - filter will raise exception
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "filter-step", "uses": "update-provider"}
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
        "filter": "nonexistent_var > 10",
    }
    context = WorkflowContext(mode="run", matrix={}, matrix_values={})

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    executor._execute_update_step(
        step, resolved_inputs, context, capture_logger
    )

    # Step_logger called per-entry with IGNORED for filter exception
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "filter-step",
        "IGNORED",
        {"network": "asia"},
    )


# Test dry-run scan logs WOULD SKIP per-entry for filter mismatch.
def test_scan_update_step_filter_skip_logs_per_entry(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        entry.metadata["score"] = 5  # Won't match filter: score > 10
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "filter-step", "uses": "update-provider"}
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
        "filter": "score > 10",
    }

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    executor._scan_update_step_entries(step, resolved_inputs, capture_logger)

    # Step_logger called per-entry with WOULD IGNORE for filter mismatch
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "filter-step",
        "WOULD IGNORE",
        {"network": "asia"},
    )


# Test dry-run scan logs WOULD SKIP per-entry for filter exception.
def test_scan_update_step_filter_exception_logs_per_entry(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "filter-step", "uses": "update-provider"}
    resolved_inputs = {
        "action": "evaluate",
        "input": str(cache_path),
        "filter": "nonexistent_var > 10",
    }

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    executor._scan_update_step_entries(step, resolved_inputs, capture_logger)

    # Step_logger called per-entry with WOULD IGNORE for filter exception
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "filter-step",
        "WOULD IGNORE",
        {"network": "asia"},
    )


# Test dry-run scan logs WOULD SKIP per-entry for conservative skip.
def test_scan_update_step_conservative_skip_logs_per_entry(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(str(cache_path)) as cache:
        entry = CacheEntry()
        # Add action metadata to simulate already processed
        entry.metadata["update-action"] = {"evaluate": {"done": True}}
        cache.put({"network": "asia"}, entry)

    class UpdateAction:
        name = "update-action"
        action_patterns = {"evaluate": ActionPattern.UPDATE}

        def run(self, action, parameters, **kwargs):
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["update-provider"] = UpdateAction

    step = {"name": "eval-step", "uses": "update-provider"}
    resolved_inputs = {"action": "evaluate", "input": str(cache_path)}

    log_calls: list = []

    def capture_logger(action_method, step_name, status, matrix_values):
        log_calls.append((action_method, step_name, status, matrix_values))

    executor._scan_update_step_entries(step, resolved_inputs, capture_logger)

    # Step_logger called per-entry with WOULD SKIP for conservative skip
    assert len(log_calls) == 1
    assert log_calls[0] == (
        "evaluate",
        "eval-step",
        "WOULD SKIP",
        {"network": "asia"},
    )


# ===========================================================================
# NON-CACHE OUTPUT HANDLING TESTS
# ===========================================================================


# Test non-.db output (e.g., .csv) is passed to action, not used as cache.
def test_non_cache_output_passed_to_action(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    """Test that non-.db outputs like .csv are passed to the action."""
    from causaliq_workflow.registry import WorkflowContext

    captured_params: dict = {}

    class CsvOutputAction:
        name = "csv-action"
        action_patterns = {}  # type: ignore[var-annotated]

        def run(self, action, parameters, **kwargs):
            # Capture what parameters the action receives
            captured_params.update(parameters)
            return ("success", {"result": "ok"}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["csv-provider"] = CsvOutputAction

    csv_path = str(tmp_path / "output.csv")  # type: ignore[operator]
    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "summarise-step",
                "uses": "csv-provider",
                "with": {
                    "action": "summarise",
                    "output": csv_path,
                },
            }
        ],
    }

    context = WorkflowContext(
        mode="run",
        matrix=workflow["matrix"],
        matrix_values={"network": "asia"},
    )

    executor._execute_job(workflow, {"network": "asia"}, context, {}, None)

    # Action should receive output parameter (not consumed by cache)
    assert "output" in captured_params
    assert captured_params["output"] == csv_path


# Test terminal output ("-") is passed to action.
def test_terminal_output_passed_to_action() -> None:
    """Test that output='-' for terminal is passed to the action."""
    from causaliq_workflow.registry import WorkflowContext

    captured_params: dict = {}

    class TerminalOutputAction:
        name = "terminal-action"
        action_patterns = {}  # type: ignore[var-annotated]

        def run(self, action, parameters, **kwargs):
            captured_params.update(parameters)
            return ("success", {"result": "ok"}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["terminal-provider"] = (
        TerminalOutputAction
    )

    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "summarise-step",
                "uses": "terminal-provider",
                "with": {
                    "action": "summarise",
                    "output": "-",
                },
            }
        ],
    }

    context = WorkflowContext(
        mode="run",
        matrix=workflow["matrix"],
        matrix_values={"network": "asia"},
    )

    executor._execute_job(workflow, {"network": "asia"}, context, {}, None)

    # Action should receive output="-" parameter
    assert "output" in captured_params
    assert captured_params["output"] == "-"


# Test .db output is NOT passed to action (consumed by cache).
def test_db_output_not_passed_to_action(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    """Test that .db outputs are consumed by cache, not passed to action."""
    from causaliq_workflow.registry import WorkflowContext

    captured_params: dict = {}

    class CacheOutputAction:
        name = "cache-action"
        action_patterns = {}  # type: ignore[var-annotated]

        def run(self, action, parameters, **kwargs):
            captured_params.update(parameters)
            return ("success", {"result": "ok"}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["cache-provider"] = CacheOutputAction

    db_path = str(tmp_path / "output.db")  # type: ignore[operator]
    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "create-step",
                "uses": "cache-provider",
                "with": {
                    "action": "create",
                    "output": db_path,
                },
            }
        ],
    }

    context = WorkflowContext(
        mode="run",
        matrix=workflow["matrix"],
        matrix_values={"network": "asia"},
    )

    executor._execute_job(workflow, {"network": "asia"}, context, {}, None)

    # Action should NOT receive output parameter (.db is consumed by cache)
    assert "output" not in captured_params
