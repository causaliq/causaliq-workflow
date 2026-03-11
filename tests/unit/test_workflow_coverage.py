"""Unit tests for WorkflowExecutor coverage."""

import pytest
import pytest_mock
from causaliq_core import ActionExecutionError, ActionResult

from causaliq_workflow.workflow import (
    AggregationConfig,
    WorkflowExecutionError,
    WorkflowExecutor,
)
from tests.functional.fixtures.test_action import ActionProvider


class MockWorkflowAction(ActionProvider):
    """Mock action for workflow testing."""

    name = "mock-workflow-action"
    version = "1.0.0"
    description = "Mock action for workflow testing"

    def run(self, action: str, parameters: dict, **kwargs) -> ActionResult:
        mode = kwargs.get("mode", "run")
        context = kwargs.get("context")
        kwargs.get("logger")

        metadata = {
            "mode": mode,
            "parameters": parameters,
        }

        if context:
            metadata["context_mode"] = context.mode

        status = "validated" if mode == "dry-run" else "executed"
        return (status, metadata, [])


class MockFailingAction(ActionProvider):
    """Mock action that fails during execution."""

    name = "mock-failing-action"
    version = "1.0.0"
    description = "Mock action that always fails"

    def run(self, action: str, parameters: dict, **kwargs) -> ActionResult:
        raise ActionExecutionError("Mock action failure")


@pytest.fixture
def executor() -> WorkflowExecutor:
    """Pytest fixture for executor setup."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["mock_workflow_action"] = (
        MockWorkflowAction
    )
    executor.action_registry._actions["mock_failing_action"] = (
        MockFailingAction
    )
    return executor


# Test resolving template variables in a dictionary.
def test_resolve_template_variables_dict(executor: WorkflowExecutor) -> None:
    variables = {"dataset": "asia", "algorithm": "pc"}
    obj = {
        "input": "{{dataset}}.csv",
        "output": "results/{{algorithm}}/{{dataset}}.xml",
        "nested": {"path": "/data/{{dataset}}/{{algorithm}}"},
    }
    result = executor._resolve_template_variables(obj, variables)
    assert result["input"] == "asia.csv"
    assert result["output"] == "results/pc/asia.xml"
    assert result["nested"]["path"] == "/data/asia/pc"


# Test resolving template variables in a list.
def test_resolve_template_variables_list(executor: WorkflowExecutor) -> None:
    variables = {"dataset": "asia", "num": "42"}
    obj = [
        "{{dataset}}.csv",
        "file_{{num}}.txt",
        {"name": "{{dataset}}_{{num}}"},
    ]
    result = executor._resolve_template_variables(obj, variables)
    assert result[0] == "asia.csv"
    assert result[1] == "file_42.txt"
    assert result[2]["name"] == "asia_42"


# Test resolving template variables in a string.
def test_resolve_template_variables_string(executor: WorkflowExecutor) -> None:
    variables = {"name": "test", "version": "1.0", "extra": "value"}
    obj = "{{name}}_v{{version}}_{{extra}}.log"
    result = executor._resolve_template_variables(obj, variables)
    assert result == "test_v1.0_value.log"


# Test resolving template variables with a missing variable.
def test_resolve_template_variables_missing(
    executor: WorkflowExecutor,
) -> None:
    variables = {"name": "test"}
    obj = "{{name}}_{{missing}}.log"
    result = executor._resolve_template_variables(obj, variables)
    assert result == "test_{{missing}}.log"


# Test resolving template variables with non-string types.
def test_resolve_template_variables_non_string(
    executor: WorkflowExecutor,
) -> None:
    variables = {"key": "value"}
    assert executor._resolve_template_variables(42, variables) == 42
    assert executor._resolve_template_variables(True, variables) is True
    assert executor._resolve_template_variables(None, variables) is None
    assert executor._resolve_template_variables(3.14, variables) == 3.14


# Test validation failure for unknown action.
def test_validate_workflow_actions_failure(
    executor: WorkflowExecutor,
) -> None:
    workflow = {"steps": [{"uses": "unknown-action", "name": "Test Step"}]}
    with pytest.raises(
        WorkflowExecutionError, match="Action validation failed"
    ):
        executor._validate_workflow_actions(workflow, "run")


# Test skipping validation in dry-run mode.
def test_validate_workflow_actions_dry_run_skip(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"param": "value"},
            }
        ]
    }
    executor._validate_workflow_actions(workflow, "dry-run")


# Test executing workflow in dry-run mode.
def test_execute_workflow_dry_run_mode(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"input": "{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="dry-run")
    assert len(results) == 1
    assert "job" in results[0]
    assert "steps" in results[0]
    assert "Test Step" in results[0]["steps"]
    step_result = results[0]["steps"]["Test Step"]
    assert step_result["status"] == "would_execute"


# Test executing workflow in run mode.
def test_execute_workflow_run_mode(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"input": "{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 1
    assert "job" in results[0]
    assert "steps" in results[0]
    assert "Test Step" in results[0]["steps"]
    step_result = results[0]["steps"]["Test Step"]
    assert step_result["status"] == "executed"
    assert step_result["mode"] == "run"
    assert step_result["parameters"]["input"] == "asia.csv"


# Test executing workflow with CLI parameters.
def test_execute_workflow_with_cli_params(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
                    "input": "{{dataset}}.csv",
                    "extra_param": "{{extra_param}}",
                },
            }
        ],
    }
    cli_params = {"extra_param": "cli_value"}
    results = executor.execute_workflow(
        workflow, mode="run", cli_params=cli_params
    )
    assert len(results) == 1
    step_result = results[0]["steps"]["Test Step"]
    assert "extra_param" in step_result["parameters"]
    assert step_result["parameters"]["extra_param"] == "cli_value"


# Test executing workflow with multiple matrix combinations.
def test_execute_workflow_multiple_matrix(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "test-workflow",
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
        },
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
                    "dataset": "{{dataset}}",
                    "algorithm": "{{algorithm}}",
                },
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 4
    combinations = []
    for result in results:
        step_result = result["steps"]["Test Step"]
        combinations.append(
            (
                step_result["parameters"]["dataset"],
                step_result["parameters"]["algorithm"],
            )
        )
    expected_combinations = [
        ("asia", "pc"),
        ("asia", "ges"),
        ("cancer", "pc"),
        ("cancer", "ges"),
    ]
    assert set(combinations) == set(expected_combinations)


# Test workflow execution error when action fails.
def test_execute_workflow_action_execution_error(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [{"uses": "mock_failing_action", "name": "Failing Step"}],
    }
    with pytest.raises(
        WorkflowExecutionError, match="Workflow execution failed"
    ):
        executor.execute_workflow(workflow, mode="run")


# Test workflow execution error for missing action.
def test_execute_workflow_missing_action(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {"uses": "nonexistent-action", "name": "Missing Action Step"}
        ],
    }
    with pytest.raises(
        WorkflowExecutionError, match="Action 'nonexistent-action' not found"
    ):
        executor.execute_workflow(workflow, mode="run")


# Test matrix variables are passed implicitly to actions without templates.
def test_execute_workflow_implicit_matrix_params(
    executor: WorkflowExecutor,
) -> None:
    """Matrix variables should be passed to actions even without {{var}}."""
    workflow = {
        "id": "test-workflow",
        "matrix": {
            "network": ["asia", "alarm"],
            "sample_size": [100, 500],
        },
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                # Note: no {{network}} or {{sample_size}} templates
                "with": {"explicit_param": "value"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")

    # Should have 4 combinations (2 networks × 2 sample_sizes)
    assert len(results) == 4

    # Verify each result has implicit matrix params
    for result in results:
        step_result = result["steps"]["Test Step"]
        params = step_result["parameters"]

        # Explicit param should be present
        assert params["explicit_param"] == "value"

        # Matrix variables should be implicitly passed
        assert "network" in params
        assert "sample_size" in params
        assert params["network"] in ["asia", "alarm"]
        assert params["sample_size"] in [100, 500]


# Test implicit matrix params do not override explicit params.
def test_execute_workflow_implicit_does_not_override_explicit(
    executor: WorkflowExecutor,
) -> None:
    """Explicit action params should not be overridden by matrix variables."""
    workflow = {
        "id": "test-workflow",
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                # Explicit network param should take precedence
                "with": {"network": "custom_value"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 1

    step_result = results[0]["steps"]["Test Step"]
    params = step_result["parameters"]

    # Explicit param should NOT be overridden
    assert params["network"] == "custom_value"


# ============================================================================
# Aggregation mode detection tests
# ============================================================================


# Test _is_aggregation_step returns False when no matrix.
def test_is_aggregation_step_no_matrix(executor: WorkflowExecutor) -> None:
    step = {"uses": "action", "with": {"aggregate": "cache.db"}}
    assert executor._is_aggregation_step(step, {}) is False


# Test _is_aggregation_step returns False when no aggregate param.
def test_is_aggregation_step_no_aggregate(executor: WorkflowExecutor) -> None:
    step = {"uses": "action", "with": {"other": "value"}}
    matrix = {"network": ["asia"]}
    assert executor._is_aggregation_step(step, matrix) is False


# Test _is_aggregation_step returns True when matrix and aggregate present.
def test_is_aggregation_step_true(executor: WorkflowExecutor) -> None:
    step = {"uses": "action", "with": {"aggregate": "cache.db"}}
    matrix = {"network": ["asia"]}
    assert executor._is_aggregation_step(step, matrix) is True


# Test _is_aggregation_step returns False when no with block.
def test_is_aggregation_step_no_with_block(executor: WorkflowExecutor) -> None:
    step = {"uses": "action"}
    matrix = {"network": ["asia"]}
    assert executor._is_aggregation_step(step, matrix) is False


# Test _get_aggregation_config returns None for non-aggregation step.
def test_get_aggregation_config_not_aggregation(
    executor: WorkflowExecutor,
) -> None:
    step = {"uses": "action", "with": {"other": "value"}}
    matrix = {"network": ["asia"]}
    config = executor._get_aggregation_config(step, matrix)
    assert config is None


# Test _get_aggregation_config with single aggregate cache.
def test_get_aggregation_config_single_aggregate(
    executor: WorkflowExecutor,
) -> None:
    step = {"uses": "action", "with": {"aggregate": "cache.db"}}
    matrix = {"network": ["asia", "alarm"], "sample_size": [100, 500]}
    config = executor._get_aggregation_config(step, matrix)

    assert config is not None
    assert isinstance(config, AggregationConfig)
    assert config.input_caches == ["cache.db"]
    assert config.filter_expr is None
    assert set(config.matrix_vars) == {"network", "sample_size"}


# Test _get_aggregation_config with list of aggregate caches.
def test_get_aggregation_config_multiple_aggregates(
    executor: WorkflowExecutor,
) -> None:
    step = {
        "uses": "action",
        "with": {"aggregate": ["cache1.db", "cache2.db"]},
    }
    matrix = {"network": ["asia"]}
    config = executor._get_aggregation_config(step, matrix)

    assert config is not None
    assert config.input_caches == ["cache1.db", "cache2.db"]


# Test _get_aggregation_config with filter expression.
def test_get_aggregation_config_with_filter(
    executor: WorkflowExecutor,
) -> None:
    step = {
        "uses": "action",
        "with": {
            "aggregate": "cache.db",
            "filter": "status == 'completed'",
        },
    }
    matrix = {"network": ["asia"]}
    config = executor._get_aggregation_config(step, matrix)

    assert config is not None
    assert config.filter_expr == "status == 'completed'"


# Test _get_aggregation_config with non-string/list aggregate value.
def test_get_aggregation_config_invalid_aggregate_type(
    executor: WorkflowExecutor,
) -> None:
    step = {"uses": "action", "with": {"aggregate": 123}}
    matrix = {"network": ["asia"]}
    config = executor._get_aggregation_config(step, matrix)

    assert config is not None
    assert config.input_caches == []


# Test _is_aggregation_step returns True when input contains .db file.
def test_is_aggregation_step_with_input_db(executor: WorkflowExecutor) -> None:
    step = {"uses": "action", "with": {"input": "results.db"}}
    matrix = {"network": ["asia"]}
    assert executor._is_aggregation_step(step, matrix) is True


# Test _is_aggregation_step with input list containing .db file.
def test_is_aggregation_step_with_input_db_list(
    executor: WorkflowExecutor,
) -> None:
    step = {"uses": "action", "with": {"input": ["data.json", "cache.db"]}}
    matrix = {"network": ["asia"]}
    assert executor._is_aggregation_step(step, matrix) is True


# Test _is_aggregation_step returns False when input has no .db files.
def test_is_aggregation_step_input_no_db(executor: WorkflowExecutor) -> None:
    step = {"uses": "action", "with": {"input": "data.graphml"}}
    matrix = {"network": ["asia"]}
    assert executor._is_aggregation_step(step, matrix) is False


# Test _get_aggregation_config with implicit aggregation from input .db.
def test_get_aggregation_config_implicit_from_input(
    executor: WorkflowExecutor,
) -> None:
    step = {"uses": "action", "with": {"input": "results.db"}}
    matrix = {"network": ["asia"], "seed": [1, 2]}
    config = executor._get_aggregation_config(step, matrix)

    assert config is not None
    assert config.input_caches == ["results.db"]
    assert set(config.matrix_vars) == {"network", "seed"}


# Test _get_aggregation_config with input list filters to .db only.
def test_get_aggregation_config_input_list_filters_db(
    executor: WorkflowExecutor,
) -> None:
    step = {
        "uses": "action",
        "with": {"input": ["data.graphml", "cache.db", "other.json"]},
    }
    matrix = {"network": ["asia"]}
    config = executor._get_aggregation_config(step, matrix)

    assert config is not None
    # Only .db files should be in input_caches
    assert config.input_caches == ["cache.db"]


# Test AggregationConfig dataclass defaults.
def test_aggregation_config_defaults() -> None:
    config = AggregationConfig()
    assert config.input_caches == []
    assert config.filter_expr is None
    assert config.matrix_vars == []


# Test AggregationConfig with explicit values.
def test_aggregation_config_with_values() -> None:
    config = AggregationConfig(
        input_caches=["a.db", "b.db"],
        filter_expr="x > 5",
        matrix_vars=["network", "sample_size"],
    )
    assert config.input_caches == ["a.db", "b.db"]
    assert config.filter_expr == "x > 5"
    assert config.matrix_vars == ["network", "sample_size"]


# ============================================================================
# Aggregation scan phase tests
# ============================================================================


# Test _flatten_metadata with matrix values only.
def test_flatten_metadata_matrix_only(executor: WorkflowExecutor) -> None:
    matrix_values = {"network": "asia", "sample_size": 100}
    metadata: dict = {}
    result = executor._flatten_metadata(matrix_values, metadata)
    assert result == {"network": "asia", "sample_size": 100}


# Test _flatten_metadata with nested provider metadata.
def test_flatten_metadata_nested(executor: WorkflowExecutor) -> None:
    matrix_values = {"network": "asia"}
    metadata = {
        "causaliq-research": {
            "generate_graph": {
                "node_count": 5,
                "edge_count": 8,
            }
        }
    }
    result = executor._flatten_metadata(matrix_values, metadata)

    # Simple keys available
    assert result["network"] == "asia"
    assert result["node_count"] == 5
    assert result["edge_count"] == 8

    # Fully qualified keys also available
    assert result["causaliq-research.generate_graph.node_count"] == 5


# Test _flatten_metadata handles key conflicts.
def test_flatten_metadata_key_conflict(executor: WorkflowExecutor) -> None:
    matrix_values = {"network": "asia"}
    metadata = {
        "provider1": {"action1": {"network": "overridden"}},
        "provider2": {"action2": {"network": "also_overridden"}},
    }
    result = executor._flatten_metadata(matrix_values, metadata)

    # Matrix value takes precedence for simple key
    assert result["network"] == "asia"

    # Fully qualified keys preserve all values
    assert result["provider1.action1.network"] == "overridden"
    assert result["provider2.action2.network"] == "also_overridden"


# Test _flatten_metadata with non-dict nested values.
def test_flatten_metadata_non_dict_nested(executor: WorkflowExecutor) -> None:
    matrix_values = {"network": "asia"}
    metadata = {
        "simple_key": "simple_value",
        "provider": {"action": "string_action_data"},
    }
    result = executor._flatten_metadata(matrix_values, metadata)

    assert result["simple_key"] == "simple_value"
    assert result["provider.action"] == "string_action_data"


# Test _scan_aggregation_inputs with in-memory cache.
def test_scan_aggregation_inputs_basic(
    executor: WorkflowExecutor,
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    # Create cache with entries
    cache_path = tmp_path / "test.db"  # type: ignore[operator]
    with WorkflowCache(cache_path) as cache:
        entry1 = CacheEntry(
            metadata={"provider": {"action": {"status": "ok"}}}
        )
        cache.put({"network": "asia", "sample_size": 100}, entry1)

        entry2 = CacheEntry(
            metadata={"provider": {"action": {"status": "ok"}}}
        )
        cache.put({"network": "asia", "sample_size": 500}, entry2)

        entry3 = CacheEntry(
            metadata={"provider": {"action": {"status": "ok"}}}
        )
        cache.put({"network": "alarm", "sample_size": 100}, entry3)

    config = AggregationConfig(
        input_caches=[str(cache_path)],
        matrix_vars=["network", "sample_size"],
    )

    # Scan for asia/100 entries
    results = executor._scan_aggregation_inputs(
        config,
        {"network": "asia", "sample_size": 100},
    )

    assert len(results) == 1
    assert results[0]["matrix_values"] == {
        "network": "asia",
        "sample_size": 100,
    }


# Test _scan_aggregation_inputs with filter expression.
def test_scan_aggregation_inputs_with_filter(
    executor: WorkflowExecutor,
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "test.db"  # type: ignore[operator]
    with WorkflowCache(cache_path) as cache:
        entry1 = CacheEntry(
            metadata={"provider": {"action": {"status": "completed"}}}
        )
        cache.put({"network": "asia"}, entry1)

        entry2 = CacheEntry(
            metadata={"provider": {"action": {"status": "failed"}}}
        )
        cache.put({"network": "alarm"}, entry2)

    config = AggregationConfig(
        input_caches=[str(cache_path)],
        filter_expr="status == 'completed'",
        matrix_vars=["network"],
    )

    # Scan for asia - should match filter
    results = executor._scan_aggregation_inputs(
        config,
        {"network": "asia"},
    )
    assert len(results) == 1
    assert results[0]["matrix_values"]["network"] == "asia"

    # Scan for alarm - should be filtered out
    results = executor._scan_aggregation_inputs(
        config,
        {"network": "alarm"},
    )
    assert len(results) == 0


# Test _scan_aggregation_inputs logs statistics.
def test_scan_aggregation_inputs_logging(
    executor: WorkflowExecutor,
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "test.db"  # type: ignore[operator]
    with WorkflowCache(cache_path) as cache:
        entry = CacheEntry(metadata={})
        cache.put({"network": "asia"}, entry)

    config = AggregationConfig(
        input_caches=[str(cache_path)],
        matrix_vars=["network"],
    )

    log_messages: list = []
    executor._scan_aggregation_inputs(
        config,
        {"network": "asia"},
        logger=log_messages.append,
    )

    assert len(log_messages) == 1
    assert "scanned=1" in log_messages[0]
    assert "matched=1" in log_messages[0]


# Test _scan_aggregation_inputs with missing cache.
def test_scan_aggregation_inputs_missing_cache(
    executor: WorkflowExecutor,
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    # Use absolute path that definitely doesn't exist
    missing_cache = str(tmp_path / "definitely_nonexistent.db")

    config = AggregationConfig(
        input_caches=[missing_cache],
        matrix_vars=["network"],
    )

    log_messages: list = []
    results = executor._scan_aggregation_inputs(
        config,
        {"network": "asia"},
        logger=log_messages.append,
    )

    # Should return empty but log warning
    assert results == []
    assert len(log_messages) == 2  # Warning + summary
    assert "Warning" in log_messages[0]


# Test _scan_aggregation_inputs skips entries missing matrix vars.
def test_scan_aggregation_inputs_skips_incomplete_entries(
    executor: WorkflowExecutor,
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    # Create first cache with full schema
    cache_path1 = tmp_path / "cache1.db"  # type: ignore[operator]
    with WorkflowCache(cache_path1) as cache:
        entry1 = CacheEntry(metadata={})
        cache.put({"network": "asia", "sample_size": 100}, entry1)

    # Create second cache with partial schema (different schema per cache)
    cache_path2 = tmp_path / "cache2.db"  # type: ignore[operator]
    with WorkflowCache(cache_path2) as cache:
        entry2 = CacheEntry(metadata={})
        cache.put({"network": "alarm"}, entry2)  # No sample_size

    config = AggregationConfig(
        input_caches=[str(cache_path1), str(cache_path2)],
        matrix_vars=["network", "sample_size"],
    )

    results = executor._scan_aggregation_inputs(
        config,
        {"network": "asia", "sample_size": 100},
    )

    # Only complete entry from cache1 should match
    assert len(results) == 1
    assert results[0]["matrix_values"]["sample_size"] == 100


# Test _scan_aggregation_inputs handles cache.get returning None.
def test_scan_aggregation_inputs_get_returns_none(
    executor: WorkflowExecutor,
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
    mocker: "pytest_mock.MockerFixture",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "test.db"  # type: ignore[operator]
    with WorkflowCache(cache_path) as cache:
        entry = CacheEntry(metadata={})
        cache.put({"network": "asia"}, entry)

    config = AggregationConfig(
        input_caches=[str(cache_path)],
        matrix_vars=["network"],
    )

    # Mock cache.get to return None
    mocker.patch.object(WorkflowCache, "get", return_value=None)

    results = executor._scan_aggregation_inputs(
        config,
        {"network": "asia"},
    )

    # Should return empty as get returns None
    assert results == []


# Test _scan_aggregation_inputs handles filter evaluation errors.
def test_scan_aggregation_inputs_filter_error(
    executor: WorkflowExecutor,
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "test.db"  # type: ignore[operator]
    with WorkflowCache(cache_path) as cache:
        entry = CacheEntry(metadata={})
        cache.put({"network": "asia"}, entry)

    config = AggregationConfig(
        input_caches=[str(cache_path)],
        # Invalid filter that will cause evaluation error
        filter_expr="undefined_var / 0",
        matrix_vars=["network"],
    )

    log_messages: list = []
    results = executor._scan_aggregation_inputs(
        config,
        {"network": "asia"},
        logger=log_messages.append,
    )

    # Entry filtered due to error
    assert results == []
    assert "filtered=1" in log_messages[0]


# Test _scan_aggregation_inputs handles cache read exception.
def test_scan_aggregation_inputs_cache_exception(
    executor: WorkflowExecutor,
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    # Create a file that is not a valid SQLite database
    bad_cache = tmp_path / "bad.db"  # type: ignore[operator]
    bad_cache.write_text("not a database")

    config = AggregationConfig(
        input_caches=[str(bad_cache)],
        matrix_vars=["network"],
    )

    log_messages: list = []
    results = executor._scan_aggregation_inputs(
        config,
        {"network": "asia"},
        logger=log_messages.append,
    )

    # Should return empty and log warning
    assert results == []
    assert len(log_messages) == 2  # Warning + summary
    assert "Warning" in log_messages[0]
    assert "Failed to read cache" in log_messages[0]


# Test _scan_aggregation_inputs logs filter statistics.
def test_scan_aggregation_inputs_filter_logging(
    executor: WorkflowExecutor,
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "test.db"  # type: ignore[operator]
    with WorkflowCache(cache_path) as cache:
        entry1 = CacheEntry(
            metadata={"provider": {"action": {"status": "completed"}}}
        )
        cache.put({"network": "asia"}, entry1)

        entry2 = CacheEntry(
            metadata={"provider": {"action": {"status": "failed"}}}
        )
        cache.put({"network": "alarm"}, entry2)

    config = AggregationConfig(
        input_caches=[str(cache_path)],
        filter_expr="status == 'completed'",
        matrix_vars=["network"],
    )

    log_messages: list = []
    executor._scan_aggregation_inputs(
        config,
        {"network": "asia"},
        logger=log_messages.append,
    )

    # Log should include filter stats
    assert len(log_messages) == 1
    assert "filtered=1" in log_messages[0]


# Test aggregation entries passed to action in _execute_job.
def test_execute_job_aggregation_passes_entries(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

    # Create input cache with entries
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(cache_path) as cache:
        entry = CacheEntry(metadata={"provider": {"action": {"value": 42}}})
        cache.put({"network": "asia"}, entry)

    # Create mock action that captures parameters
    captured_params: dict = {}

    class CaptureAction:
        name = "capture-action"
        version = "1.0.0"
        description = "Captures parameters"

        def run(self, action, parameters, **kwargs):
            captured_params.update(parameters)
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    # Setup executor with mock action
    executor = WorkflowExecutor()
    executor.action_registry._actions["capture-action"] = CaptureAction

    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "agg-step",
                "uses": "capture-action",
                "with": {
                    "action": "do_aggregation",
                    "aggregate": str(cache_path),
                },
            }
        ],
    }

    context = WorkflowContext(
        mode="run",
        matrix=workflow["matrix"],
        matrix_values={"network": "asia"},
    )

    executor._execute_job(workflow, {"network": "asia"}, context, {})

    # Verify aggregation entries were passed
    assert "_aggregation_entries" in captured_params
    entries = captured_params["_aggregation_entries"]
    assert len(entries) == 1
    assert entries[0]["matrix_values"]["network"] == "asia"

    # Verify 'aggregate' was removed from parameters
    assert "aggregate" not in captured_params


# Test aggregation not triggered without matrix.
def test_execute_job_no_aggregation_without_matrix(
    tmp_path: "pytest.TempPathFactory",  # type: ignore[name-defined]
) -> None:
    from causaliq_workflow.registry import WorkflowContext

    captured_params: dict = {}

    class CaptureAction:
        name = "capture-action"
        version = "1.0.0"
        description = "Captures parameters"
        action_patterns = {}  # type: ignore[var-annotated]

        def run(self, action, parameters, **kwargs):
            captured_params.update(parameters)
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["capture-action"] = CaptureAction

    cache_path = tmp_path / "input.db"  # type: ignore[operator]

    # No matrix defined - should not trigger aggregation
    workflow = {
        "steps": [
            {
                "name": "normal-step",
                "uses": "capture-action",
                "with": {
                    "action": "normal",
                    "input": str(cache_path),
                },
            }
        ],
    }

    context = WorkflowContext(
        mode="run",
        matrix={},
        matrix_values={},
    )

    executor._execute_job(workflow, {}, context, {})

    # Without matrix, no aggregation triggered
    assert "_aggregation_entries" not in captured_params
    # 'input' should remain as normal parameter
    assert "input" in captured_params


# ===========================================================================
# UPDATE pattern tests
# ===========================================================================


# Test _is_update_step returns False when matrix is present.
def test_is_update_step_false_with_matrix() -> None:
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
    assert result is False


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
    assert "does not exist" in result["error"]
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
                [{"type": "json", "name": "metrics", "content": "{}"}],
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

    # Logger should be called once after completion with EXECUTED status
    assert len(log_calls) == 1
    assert log_calls[0] == ("evaluate", "eval-step", "EXECUTED", {})


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
            return ("success", {"created": True}, [{"type": "graph"}])

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
            return ("success", {"forced": True}, [{"type": "graph"}])

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
            return ("success", {"forced": True}, [{"type": "summary"}])

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

    # Logger should be called with WOULD EXECUTE for dry-run UPDATE step
    assert len(log_calls) == 1
    assert log_calls[0] == ("evaluate", "update-step", "WOULD EXECUTE", {})


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

    # Logger should be called with FORCED status
    assert len(log_calls) == 1
    assert log_calls[0] == ("evaluate", "update-step", "FORCED", {})


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

    # Logger should be called with SKIPPED status
    assert len(log_calls) == 1
    assert log_calls[0] == ("evaluate", "update-step", "SKIPPED", {})


# Test UPDATE step logging with FAILED status.
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

    # Logger should be called with FAILED status
    assert len(log_calls) == 1
    assert log_calls[0] == ("evaluate", "update-step", "FAILED", {})


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
