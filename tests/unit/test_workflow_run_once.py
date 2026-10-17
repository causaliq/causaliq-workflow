"""Unit tests for the output-driven run-once rule.

A step's job dimensionality comes from its output: the workflow matrix if
declared, else the output cache keys, else a single job when the step
writes no workflow cache.
"""

from typing import Any, Dict, List, Optional

from causaliq_core import (
    ActionPattern,
    ActionValidationError,
    CausalIQActionProvider,
)

from causaliq_workflow.workflow import WorkflowExecutor
from causaliq_workflow.workflow.matrix import _has_cache_output, _runs_once


class OutputActionProvider(CausalIQActionProvider):
    """Mock provider whose action may write a cache or a file."""

    name = "output-provider"
    version = "1.0.0"
    supported_actions = {"produce"}
    action_patterns = {"produce": ActionPattern.AGGREGATE}

    def _execute(
        self,
        action: str,
        parameters: Dict[str, Any],
        mode: str,
        context: Optional[Any],
        logger: Optional[Any],
    ) -> Any:
        """Execute the mock action."""
        return ("success", {"ran": True}, [])


def _make_executor() -> WorkflowExecutor:
    """Create an executor with the output provider registered."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["output-provider"] = OutputActionProvider
    return executor


def _workflow(
    output: str = "out.png",
    matrix: Optional[Dict[str, List[Any]]] = None,
) -> Dict[str, Any]:
    """Return a workflow containing one produce step."""
    workflow: Dict[str, Any] = {
        "steps": [
            {
                "name": "produce-step",
                "uses": "output-provider",
                "with": {"action": "produce", "output": output},
            }
        ]
    }
    if matrix is not None:
        workflow["matrix"] = matrix
    return workflow


# A .db output is recognised as a workflow cache.
def test_has_cache_output_true_for_db() -> None:
    """A .db output is a workflow cache."""
    assert _has_cache_output({"with": {"output": "out.db"}}) is True


# A file output is not a workflow cache.
def test_has_cache_output_false_for_file() -> None:
    """A .png output is not a workflow cache."""
    assert _has_cache_output({"with": {"output": "out.png"}}) is False


# A step with no output has no workflow cache.
def test_has_cache_output_false_without_output() -> None:
    """A step without an output has no workflow cache."""
    assert _has_cache_output({"with": {}}) is False


# A step without a cache output and without a matrix runs once.
def test_runs_once_without_cache_output_or_matrix() -> None:
    """No cache output and no matrix means a single run."""
    assert _runs_once({"with": {"output": "out.png"}}, False) is True


# A cache output gives the step a matrix dimensionality.
def test_not_runs_once_with_cache_output() -> None:
    """A cache output means the step runs per output key."""
    assert _runs_once({"with": {"output": "out.db"}}, False) is False


# A step with no output is not a single-run step.
def test_not_runs_once_without_output() -> None:
    """A step with no output is still validated as a pattern step."""
    assert _runs_once({"with": {}}, False) is False


# A declared matrix gives the step a matrix dimensionality.
def test_not_runs_once_with_matrix() -> None:
    """A file output with a matrix keeps per-job granularity."""
    assert _runs_once({"with": {"output": "out.png"}}, True) is False


# A step without a cache output runs once when there is no matrix.
def test_run_once_step_runs_once_without_matrix() -> None:
    """A single-run step executes once in a workflow without a matrix."""
    executor = _make_executor()
    results = executor.execute_workflow(_workflow(), mode="run")
    assert len(results) == 1
    assert results[0]["steps"]["produce-step"]["status"] == "success"


# A step without a cache output is skipped on later derived jobs.
def test_run_once_step_skipped_on_later_jobs(tmp_path: Any) -> None:
    """A single-run step is skipped once a cache-output step derives jobs."""
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "graphs.db"
    with WorkflowCache(cache_path) as cache:
        for network in ["asia", "sports"]:
            cache.put({"network": network}, CacheEntry())

    executor = _make_executor()
    workflow: Dict[str, Any] = {
        "steps": [
            {
                "name": "aggregate-step",
                "uses": "output-provider",
                "with": {
                    "action": "produce",
                    "input": str(cache_path),
                    "output": str(tmp_path / "out.db"),
                },
            },
            {
                "name": "once-step",
                "uses": "output-provider",
                "with": {"action": "produce", "output": "figure.png"},
            },
        ]
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 2
    assert results[0]["steps"]["once-step"]["status"] == "success"
    assert results[1]["steps"]["once-step"]["status"] == "skipped"
    assert (
        results[1]["steps"]["once-step"].get("reason")
        == "single-run-step-runs-once"
    )


# A single-run step skips pattern validation (no matrix or cache required).
def test_run_once_step_passes_pattern_validation() -> None:
    """A single-run step needs no matrix or cache requirements."""
    executor = _make_executor()
    errors = executor._validate_action_patterns(_workflow())
    assert errors == []


class StrictOutputActionProvider(OutputActionProvider):
    """Mock provider which requires a parameter."""

    name = "strict-output-provider"

    def validate_parameters(
        self, action: str, parameters: Dict[str, Any]
    ) -> None:
        """Require the required_param parameter."""
        super().validate_parameters(action, parameters)
        if "required_param" not in parameters:
            raise ActionValidationError("Missing required_param")


# A single-run step reports action parameter validation errors.
def test_run_once_step_reports_validation_error() -> None:
    """A single-run step reports its action parameter errors."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-output-provider"] = (
        StrictOutputActionProvider
    )
    workflow: Dict[str, Any] = {
        "steps": [
            {
                "name": "strict-step",
                "uses": "strict-output-provider",
                "with": {"action": "produce", "output": "out.png"},
            }
        ]
    }
    errors = executor._validate_all_entries(workflow, {})
    assert len(errors) == 1
    assert "Missing required_param" in errors[0]


# An aggregate step without a cache input derives no matrix.
def test_derive_matrix_skips_step_without_cache_input() -> None:
    """An aggregate step with a cache output but no cache input."""
    executor = _make_executor()
    workflow: Dict[str, Any] = {
        "steps": [
            {
                "name": "produce-step",
                "uses": "output-provider",
                "with": {"action": "produce", "output": "out.db"},
            }
        ]
    }
    assert executor._derive_workflow_matrix(workflow) == {}
