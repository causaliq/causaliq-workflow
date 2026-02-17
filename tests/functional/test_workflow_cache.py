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


def _set_step_output(workflow: dict, step_name: str, output_path: str) -> None:
    """Helper to set output parameter on a step."""
    for step in workflow.get("steps", []):
        if step.get("name") == step_name:
            if "with" not in step:
                step["with"] = {}
            step["with"]["output"] = output_path
            return


# Test step with output parameter creates file-based cache.
def test_step_with_output_creates_cache(
    executor: WorkflowExecutor,
) -> None:
    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.db"
        _set_step_output(workflow, "Cache Capture Step", str(cache_path))

        results = executor.execute_workflow(workflow, mode="run")
        assert len(results) == 1
        step_result = results[0]["steps"]["Cache Capture Step"]
        assert step_result["has_cache"] is True
        assert step_result["cache_is_open"] is True
        assert cache_path.exists()


# Test step without output parameter does not create cache.
def test_step_without_output_no_cache(
    executor: WorkflowExecutor,
) -> None:
    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))
    # No output parameter set on step

    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 1
    step_result = results[0]["steps"]["Cache Capture Step"]
    assert step_result["has_cache"] is False


# Test cache persists across multiple workflow executions.
def test_cache_persists_across_executions(executor: WorkflowExecutor) -> None:
    from causaliq_workflow.cache import CacheEntry

    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "persistent_cache.db"

        # First execution - creates cache
        workflow = executor.parse_workflow(str(workflow_path))
        _set_step_output(workflow, "Cache Capture Step", str(cache_path))
        executor.execute_workflow(workflow, mode="run")

        # Manually add an entry to verify persistence
        with WorkflowCache(cache_path) as cache:
            entry = CacheEntry(metadata={"value": 42})
            cache.put({"dataset": "asia"}, entry)

        # Second execution - verify cache persisted
        with WorkflowCache(cache_path) as cache:
            assert cache.exists({"dataset": "asia"})
            result = cache.get({"dataset": "asia"})
            assert result is not None
            assert result.metadata == {"value": 42}


# Test matrix execution stores entries with correct keys.
def test_matrix_execution_with_cache(
    executor: WorkflowExecutor,
) -> None:
    workflow_path = TEST_DATA_DIR / "cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "matrix_cache.db"
        _set_step_output(workflow, "Cache Capture Step", str(cache_path))

        results = executor.execute_workflow(workflow, mode="run")
        assert len(results) == 4
        for result in results:
            step_result = result["steps"]["Cache Capture Step"]
            assert step_result["has_cache"] is True
            assert step_result["cache_is_open"] is True


# Test dry-run mode does not create cache even with output parameter.
def test_dry_run_no_cache_created(executor: WorkflowExecutor) -> None:
    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "dryrun_cache.db"
        _set_step_output(workflow, "Cache Capture Step", str(cache_path))

        results = executor.execute_workflow(workflow, mode="dry-run")
        assert len(results) == 1
        step_result = results[0]["steps"]["Cache Capture Step"]
        # Cache should not be available in dry-run mode
        assert step_result["has_cache"] is False
        # Cache file should not exist
        assert not cache_path.exists()


# =============================================================================
# Export/Import tests removed - replaced with provider-based serialisation
# See tests/unit/cache/test_export.py for new export tests
# =============================================================================
