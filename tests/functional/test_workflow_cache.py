"""Functional tests for workflow cache integration.

Tests cache integration with workflow execution using tracked test data
files for reading and temporary directories for writing.
"""

import tempfile
from pathlib import Path

import pytest
from causaliq_core import ActionResult

from causaliq_workflow.cache import WorkflowCache
from causaliq_workflow.workflow import WorkflowExecutor
from tests.functional.fixtures.test_action import ActionProvider

# Test data directory
TEST_DATA_DIR = (
    Path(__file__).parent.parent / "data" / "functional" / "workflow"
)


class CacheCapturingAction(ActionProvider):
    """Test action that captures cache from context."""

    name = "cache-capturing-action"
    version = "1.0.0"
    description = "Test action that captures cache context"

    def run(self, action: str, parameters: dict, **kwargs) -> ActionResult:
        context = kwargs.get("context")
        metadata = {
            "parameters": parameters,
            "has_cache": context.cache is not None if context else False,
            "cache_is_open": False,
        }
        if context and context.cache:
            metadata["cache_is_open"] = context.cache.is_open
        return ("success", metadata, [])


@pytest.fixture
def executor() -> WorkflowExecutor:
    """Pytest fixture for executor setup."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["cache_capturing_action"] = (
        CacheCapturingAction
    )
    return executor


# Test workflow execution with file-based cache.
def test_workflow_with_file_cache(executor: WorkflowExecutor) -> None:
    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.db"
        with WorkflowCache(cache_path) as cache:
            results = executor.execute_workflow(
                workflow, mode="run", cache=cache
            )
            assert len(results) == 1
            step_result = results[0]["steps"]["Cache Capture Step"]
            assert step_result["has_cache"] is True
            assert step_result["cache_is_open"] is True
        assert cache_path.exists()


# Test workflow execution with in-memory cache.
def test_workflow_with_memory_cache(executor: WorkflowExecutor) -> None:
    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with WorkflowCache(":memory:") as cache:
        results = executor.execute_workflow(workflow, mode="run", cache=cache)
        assert len(results) == 1
        step_result = results[0]["steps"]["Cache Capture Step"]
        assert step_result["has_cache"] is True
        assert step_result["cache_is_open"] is True
        assert cache.is_memory


# Test cache persists across multiple workflow executions.
def test_cache_persists_across_executions(executor: WorkflowExecutor) -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "persistent_cache.db"

        # First execution - write to cache
        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"dataset": "asia"}, "json", {"value": 42})
            executor.execute_workflow(workflow, mode="run", cache=cache)

        # Second execution - verify cache persisted
        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            assert cache.exists({"dataset": "asia"}, "json")
            data = cache.get({"dataset": "asia"}, "json")
            assert data == {"value": 42}


# Test matrix execution with shared cache.
def test_matrix_execution_with_shared_cache(
    executor: WorkflowExecutor,
) -> None:
    workflow_path = TEST_DATA_DIR / "cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "matrix_cache.db"
        with WorkflowCache(cache_path) as cache:
            results = executor.execute_workflow(
                workflow, mode="run", cache=cache
            )
            assert len(results) == 4
            for result in results:
                step_result = result["steps"]["Cache Capture Step"]
                assert step_result["has_cache"] is True
                assert step_result["cache_is_open"] is True


# Test dry-run mode with cache.
def test_dry_run_with_cache(executor: WorkflowExecutor) -> None:
    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "dryrun_cache.db"
        with WorkflowCache(cache_path) as cache:
            results = executor.execute_workflow(
                workflow, mode="dry-run", cache=cache
            )
            assert len(results) == 1
            step_result = results[0]["steps"]["Cache Capture Step"]
            assert step_result["has_cache"] is True


# =============================================================================
# Export/Import tests removed - replaced with provider-based serialisation
# See tests/unit/cache/test_export.py for new export tests
# =============================================================================
