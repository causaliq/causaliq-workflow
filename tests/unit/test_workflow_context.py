"""Unit tests for WorkflowContext matrix field setup and propagation."""

import pytest
from causaliq_core import ActionResult

from causaliq_workflow.registry import WorkflowContext
from causaliq_workflow.workflow import WorkflowExecutor
from tests.functional.fixtures.test_action import ActionProvider


class MatrixTestAction(ActionProvider):
    """Test action that captures WorkflowContext matrix for verification."""

    name = "matrix-test-action"
    version = "1.0.0"
    description = "Test action that captures matrix context"

    def run(self, action: str, parameters: dict, **kwargs) -> ActionResult:
        mode = kwargs.get("mode", "run")
        context = kwargs.get("context")

        metadata = {
            "mode": mode,
            "parameters": parameters,
        }

        if context:
            metadata["context_matrix"] = context.matrix
            metadata["context_mode"] = context.mode
            metadata["context_matrix_values"] = context.matrix_values
            metadata["context_matrix_key"] = context.matrix_key
            metadata["context_has_cache"] = context.cache is not None

        return ("success", metadata, [])


@pytest.fixture
def executor() -> WorkflowExecutor:
    """Pytest fixture for executor setup."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["matrix_test_action"] = MatrixTestAction
    return executor


# Test simple matrix definition storage in WorkflowContext.
def test_workflow_context_matrix_simple() -> None:
    matrix_def = {"dataset": ["asia", "cancer"]}
    context = WorkflowContext(
        mode="run",
        matrix=matrix_def,
    )
    assert context.matrix == matrix_def
    assert context.matrix["dataset"] == ["asia", "cancer"]


# Test complex multi-dimensional matrix preservation.
def test_workflow_context_matrix_complex() -> None:
    matrix_def = {
        "dataset": ["asia", "cancer", "earthquake"],
        "algorithm": ["pc", "ges", "lingam"],
        "alpha": [0.01, 0.05, 0.1],
    }
    context = WorkflowContext(
        mode="dry-run",
        matrix=matrix_def,
    )
    assert context.matrix == matrix_def
    assert len(context.matrix["dataset"]) == 3
    assert len(context.matrix["algorithm"]) == 3
    assert len(context.matrix["alpha"]) == 3


# Test empty matrix handling in WorkflowContext.
def test_workflow_context_matrix_empty() -> None:
    matrix_def = {}
    context = WorkflowContext(
        mode="run",
        matrix=matrix_def,
    )
    assert context.matrix == {}


# Test matrix_values stores current job's specific values.
def test_workflow_context_matrix_values_simple() -> None:
    context = WorkflowContext(
        mode="run",
        matrix={"algorithm": ["pc", "ges"], "network": ["asia", "cancer"]},
        matrix_values={"algorithm": "pc", "network": "asia"},
    )
    assert context.matrix_values == {"algorithm": "pc", "network": "asia"}


# Test matrix_values defaults to empty dict.
def test_workflow_context_matrix_values_default() -> None:
    context = WorkflowContext(
        mode="run",
        matrix={"algorithm": ["pc", "ges"]},
    )
    assert context.matrix_values == {}


# Test matrix_key returns 16 character hex string.
def test_matrix_key_returns_16_char_hex() -> None:
    context = WorkflowContext(
        mode="run",
        matrix={"algorithm": ["pc", "ges"]},
        matrix_values={"algorithm": "pc"},
    )
    key = context.matrix_key
    assert len(key) == 16
    assert all(c in "0123456789abcdef" for c in key)


# Test matrix_key returns empty string for empty matrix_values.
def test_matrix_key_empty_for_no_values() -> None:
    context = WorkflowContext(
        mode="run",
        matrix={"algorithm": ["pc", "ges"]},
        matrix_values={},
    )
    assert context.matrix_key == ""


# Test matrix_key is deterministic for same values.
def test_matrix_key_deterministic() -> None:
    values = {"algorithm": "pc", "network": "asia"}
    context1 = WorkflowContext(mode="run", matrix={}, matrix_values=values)
    context2 = WorkflowContext(mode="run", matrix={}, matrix_values=values)
    assert context1.matrix_key == context2.matrix_key


# Test matrix_key is order-independent (sorted keys).
def test_matrix_key_order_independent() -> None:
    values1 = {"algorithm": "pc", "network": "asia"}
    values2 = {"network": "asia", "algorithm": "pc"}
    context1 = WorkflowContext(mode="run", matrix={}, matrix_values=values1)
    context2 = WorkflowContext(mode="run", matrix={}, matrix_values=values2)
    assert context1.matrix_key == context2.matrix_key


# Test matrix_key differs for different values.
def test_matrix_key_differs_for_different_values() -> None:
    context1 = WorkflowContext(
        mode="run", matrix={}, matrix_values={"algorithm": "pc"}
    )
    context2 = WorkflowContext(
        mode="run", matrix={}, matrix_values={"algorithm": "ges"}
    )
    assert context1.matrix_key != context2.matrix_key


# Test matrix_key handles various data types.
def test_matrix_key_handles_data_types() -> None:
    context = WorkflowContext(
        mode="run",
        matrix={},
        matrix_values={
            "algorithm": "pc",
            "alpha": 0.05,
            "max_iter": 100,
            "use_cache": True,
        },
    )
    key = context.matrix_key
    assert len(key) == 16


# Test WorkflowExecutor passes matrix to WorkflowContext.
def test_workflow_executor_passes_matrix_to_context(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "id": "matrix-test-workflow",
        "matrix": {"dataset": ["asia", "cancer"], "algorithm": ["pc", "ges"]},
        "steps": [
            {
                "name": "Matrix Test Step",
                "uses": "matrix_test_action",
                "with": {
                    "data_path": "/test/{{dataset}}.csv",
                    "algorithm": "{{algorithm}}",
                },
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 4
    for result in results:
        step_result = result["steps"]["Matrix Test Step"]
        assert "context_matrix" in step_result
        received_matrix = step_result["context_matrix"]
        assert received_matrix == workflow["matrix"]
        assert "dataset" in received_matrix
        assert "algorithm" in received_matrix
        assert received_matrix["dataset"] == ["asia", "cancer"]
        assert received_matrix["algorithm"] == ["pc", "ges"]


# Test executor passes matrix_values to context for each job.
def test_workflow_executor_passes_matrix_values_to_context(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "id": "matrix-values-test",
        "matrix": {"dataset": ["asia", "cancer"], "algorithm": ["pc", "ges"]},
        "steps": [
            {
                "name": "Matrix Values Test",
                "uses": "matrix_test_action",
                "with": {"data": "{{dataset}}", "algo": "{{algorithm}}"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 4
    all_values = []
    all_keys = set()
    for result in results:
        step_result = result["steps"]["Matrix Values Test"]
        values = step_result["context_matrix_values"]
        key = step_result["context_matrix_key"]
        all_values.append(values)
        all_keys.add(key)
        assert isinstance(values.get("dataset"), str)
        assert isinstance(values.get("algorithm"), str)
        assert len(key) == 16
    assert len(all_keys) == 4
    expected = [
        {"dataset": "asia", "algorithm": "pc"},
        {"dataset": "asia", "algorithm": "ges"},
        {"dataset": "cancer", "algorithm": "pc"},
        {"dataset": "cancer", "algorithm": "ges"},
    ]
    for exp in expected:
        assert exp in all_values


# Test matrix passed to context even with single job (no matrix).
def test_workflow_executor_matrix_passed_to_single_job(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "id": "single-job-workflow",
        "steps": [
            {
                "name": "Single Job Step",
                "uses": "matrix_test_action",
                "with": {"data_path": "/test/data.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="dry-run")
    assert len(results) == 1
    step_result = results[0]["steps"]["Single Job Step"]
    assert "context_matrix" in step_result
    assert step_result["context_matrix"] == {}


# Test actions can use matrix for cross-job optimisation decisions.
def test_matrix_available_for_action_optimization(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "id": "optimization-test-workflow",
        "matrix": {
            "dataset": ["asia", "cancer", "earthquake", "sachs", "child"],
            "algorithm": ["pc", "ges", "lingam", "notears"],
        },
        "steps": [
            {
                "name": "Optimization Test",
                "uses": "matrix_test_action",
                "with": {"data_path": "/data/{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="dry-run")
    assert len(results) == 20
    expected_matrix = workflow["matrix"]
    for result in results:
        step_result = result["steps"]["Optimization Test"]
        received_matrix = step_result["context_matrix"]
        assert received_matrix == expected_matrix
        total_jobs = len(received_matrix["dataset"]) * len(
            received_matrix["algorithm"]
        )
        assert total_jobs == 20


# Test that matrix preserves various data types correctly.
def test_matrix_preserves_data_types(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "data-types-test",
        "matrix": {
            "dataset": ["asia", "cancer"],
            "alpha": [0.01, 0.05, 0.1],
            "max_iter": [100, 1000],
            "use_cache": [True, False],
        },
        "steps": [
            {
                "name": "Data Types Test",
                "uses": "matrix_test_action",
                "with": {"alpha": "{{alpha}}", "max_iter": "{{max_iter}}"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 24
    step_result = results[0]["steps"]["Data Types Test"]
    received_matrix = step_result["context_matrix"]
    assert isinstance(received_matrix["alpha"][0], float)
    assert isinstance(received_matrix["max_iter"][0], int)
    assert isinstance(received_matrix["use_cache"][0], bool)
    assert isinstance(received_matrix["dataset"][0], str)


# Test mode parameter correctly passed to actions in dry-run mode.
def test_mode_parameter_dry_run_execution(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "id": "mode-test-workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "Mode Test Step",
                "uses": "matrix_test_action",
                "with": {"data_path": "/test/{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="dry-run")
    assert len(results) == 1
    step_result = results[0]["steps"]["Mode Test Step"]
    assert step_result["mode"] == "dry-run"
    assert step_result["context_mode"] == "dry-run"


# Test mode parameter correctly passed to actions in run mode.
def test_mode_parameter_run_execution(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "mode-test-workflow",
        "matrix": {"dataset": ["cancer"]},
        "steps": [
            {
                "name": "Mode Test Step",
                "uses": "matrix_test_action",
                "with": {"data_path": "/test/{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 1
    step_result = results[0]["steps"]["Mode Test Step"]
    assert step_result["mode"] == "run"
    assert step_result["context_mode"] == "run"


# Test mode parameter consistent across all matrix job executions.
def test_mode_parameter_consistency_across_matrix_jobs(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "id": "mode-consistency-test",
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
        },
        "steps": [
            {
                "name": "Consistency Test",
                "uses": "matrix_test_action",
                "with": {"data_path": "/test/{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="dry-run")
    assert len(results) == 4
    for result in results:
        step_result = result["steps"]["Consistency Test"]
        assert step_result["mode"] == "dry-run"
        assert step_result["context_mode"] == "dry-run"


# Test mode parameter correctly passed with compare mode.
def test_mode_parameter_compare_execution(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "compare-mode-test",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "Compare Test",
                "uses": "matrix_test_action",
                "with": {"data_path": "/test/{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="compare")
    assert len(results) == 1
    step_result = results[0]["steps"]["Compare Test"]
    assert step_result["mode"] == "compare"
    assert step_result["context_mode"] == "compare"


# Test action receives mode even when no context is provided.
def test_mode_parameter_without_context() -> None:
    action = MatrixTestAction()
    status, metadata, objects = action.run(
        action="",
        parameters={"data_path": "/test/data.csv"},
        mode="dry-run",
        context=None,
    )
    assert metadata["mode"] == "dry-run"
    assert "context_mode" not in metadata


# ============================================================================
# Cache integration tests
# ============================================================================


# Test WorkflowContext cache field defaults to None.
def test_workflow_context_cache_defaults_to_none() -> None:
    context = WorkflowContext(
        mode="run",
        matrix={"dataset": ["asia"]},
    )
    assert context.cache is None


# Test WorkflowContext accepts cache parameter.
def test_workflow_context_accepts_cache() -> None:
    from causaliq_workflow.cache import WorkflowCache

    with WorkflowCache(":memory:") as cache:
        context = WorkflowContext(
            mode="run",
            matrix={"dataset": ["asia"]},
            cache=cache,
        )
        assert context.cache is cache
        assert context.cache.is_open


# Test execute_workflow without cache (default behaviour).
def test_execute_workflow_without_cache(executor: WorkflowExecutor) -> None:
    workflow = {
        "id": "no-cache-test",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "No Cache Step",
                "uses": "matrix_test_action",
                "with": {"data": "{{dataset}}"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 1
    step_result = results[0]["steps"]["No Cache Step"]
    assert step_result["context_has_cache"] is False


# Test execute_workflow passes cache to context.
def test_execute_workflow_with_cache(executor: WorkflowExecutor) -> None:
    from causaliq_workflow.cache import WorkflowCache

    workflow = {
        "id": "cache-test",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "Cache Step",
                "uses": "matrix_test_action",
                "with": {"data": "{{dataset}}"},
            }
        ],
    }
    with WorkflowCache(":memory:") as cache:
        results = executor.execute_workflow(workflow, mode="run", cache=cache)
        assert len(results) == 1
        step_result = results[0]["steps"]["Cache Step"]
        assert step_result["context_has_cache"] is True


# Test cache passed to all jobs in matrix execution.
def test_cache_passed_to_all_matrix_jobs(executor: WorkflowExecutor) -> None:
    from causaliq_workflow.cache import WorkflowCache

    workflow = {
        "id": "multi-job-cache-test",
        "matrix": {"dataset": ["asia", "cancer"], "algorithm": ["pc", "ges"]},
        "steps": [
            {
                "name": "Multi Job Step",
                "uses": "matrix_test_action",
                "with": {"data": "{{dataset}}", "algo": "{{algorithm}}"},
            }
        ],
    }
    with WorkflowCache(":memory:") as cache:
        results = executor.execute_workflow(workflow, mode="run", cache=cache)
        assert len(results) == 4
        for result in results:
            step_result = result["steps"]["Multi Job Step"]
            assert step_result["context_has_cache"] is True
