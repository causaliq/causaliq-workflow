"""Unit tests for WorkflowExecutor - aggregation functionality."""

import pytest
import pytest_mock

from causaliq_workflow.workflow import (
    AggregationConfig,
    WorkflowExecutor,
)

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
