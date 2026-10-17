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
