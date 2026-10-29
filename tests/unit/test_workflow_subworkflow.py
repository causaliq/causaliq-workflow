"""Tests for invoking another workflow from a step."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from causaliq_workflow.cli_report import _count_results
from causaliq_workflow.registry import WorkflowContext
from causaliq_workflow.schema import WorkflowValidationError
from causaliq_workflow.workflow import (
    WorkflowExecutionError,
    WorkflowExecutor,
)
from causaliq_workflow.workflow.execution import _JobState
from causaliq_workflow.workflow.frames import workflow_frame
from causaliq_workflow.workflow.matrix import _runs_once
from causaliq_workflow.workflow.subworkflow import _summarise_call


def _frames(tmp_path: Path) -> Any:
    """Return a call stack seeded with a parent workflow."""
    return (workflow_frame(tmp_path / "parent.yml"),)


def _state(
    tmp_path: Path,
    job_index: int = 0,
    mode: str = "run",
    logger: Optional[Any] = None,
) -> _JobState:
    """Build per-job execution state for a sub-workflow test."""
    context = WorkflowContext(
        mode=mode,
        matrix={},
        matrix_values={},
        job_index=job_index,
        total_jobs=job_index + 1,
    )
    return _JobState(
        workflow={"steps": []},
        job={},
        context=context,
        cli_params={},
        step_logger=logger,
        variables={},
        frames=_frames(tmp_path),
    )


# A workflow call needs a YAML target.
def test_call_target_requires_workflow_suffix(
    executor: WorkflowExecutor,
) -> None:
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor._workflow_call_target({"uses": "./child.txt"}, "Call", ())
    assert "must be a .yml or .yaml file" in str(exc_info.value)


# A workflow may not call itself.
def test_call_target_rejects_recursive_call(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor._workflow_call_target(
            {"uses": "./parent.yml"}, "Call", _frames(tmp_path)
        )
    assert "recursive workflow call detected" in str(exc_info.value)
    assert "parent.yml -> parent.yml" in str(exc_info.value)


# Call targets resolve against the calling workflow's directory.
def test_call_target_resolves_against_calling_directory(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    target = executor._workflow_call_target(
        {"uses": "./child.yml"}, "Call", _frames(tmp_path)
    )
    assert target == (tmp_path / "child.yml").resolve()


# Reserved executor parameters are rejected in a call's with block.
def test_validate_call_step_reports_reserved_parameters(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    step = {
        "uses": "./child.yml",
        "with": {"action": "record", "output": "x.db"},
    }
    errors = executor._validate_workflow_call_step(
        step, "Call", _frames(tmp_path)
    )
    assert errors == [
        "Step 'Call': workflow calls do not support 'action' in 'with'",
        "Step 'Call': workflow calls do not support 'output' in 'with'",
    ]


# Load failures are reported against the calling step.
def test_validate_call_step_wraps_load_errors(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_error(path: Any) -> Dict[str, Any]:
        raise WorkflowValidationError("Workflow file not found: x")

    monkeypatch.setattr(
        "causaliq_workflow.workflow.subworkflow.load_workflow_file",
        raise_error,
    )
    errors = executor._validate_workflow_call_step(
        {"uses": "./missing.yml"}, "Call", _frames(tmp_path)
    )
    assert errors == [
        "Step 'Call' (workflow 'missing.yml'): " "Workflow file not found: x"
    ]


# Validation recurses into the called workflow.
def test_validate_call_step_recurses_into_child(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = {"steps": [{"name": "inner"}]}
    captured: Dict[str, Any] = {}

    def load_child(
        target: Any, step_name: str, parameter_names: Any = frozenset()
    ) -> Dict[str, Any]:
        return child

    def record_entries(
        workflow: Dict[str, Any], cli_params: Dict[str, Any], frames: Any
    ) -> List[str]:
        captured.update(workflow=workflow, frames=frames)
        return ["inner error"]

    monkeypatch.setattr(executor, "_load_child_workflow", load_child)
    monkeypatch.setattr(executor, "_validate_all_entries", record_entries)
    errors = executor._validate_workflow_call_step(
        {"uses": "./child.yml"}, "Call", _frames(tmp_path)
    )
    assert errors == ["inner error"]
    assert captured["workflow"] is child
    assert captured["frames"][-1].path == (tmp_path / "child.yml").resolve()


# A null default in the child is optional and needs no caller value.
def test_validate_call_step_accepts_null_default(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child: Dict[str, Any] = {
        "network": None,
        "steps": [
            {"name": "inner", "with": {"output": "{{network}}"}},
        ],
    }

    def load_child(
        target: Any, step_name: str, parameter_names: Any = frozenset()
    ) -> Dict[str, Any]:
        return child

    monkeypatch.setattr(executor, "_load_child_workflow", load_child)
    errors = executor._validate_workflow_call_step(
        {"uses": "./child.yml"}, "Call", _frames(tmp_path)
    )
    assert errors == []


# An undeclared child placeholder still requires a caller value.
def test_validate_call_step_reports_required_placeholder(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child: Dict[str, Any] = {
        "steps": [
            {"name": "inner", "with": {"output": "{{network}}.db"}},
        ],
    }

    def load_child(
        target: Any, step_name: str, parameter_names: Any = frozenset()
    ) -> Dict[str, Any]:
        return child

    monkeypatch.setattr(executor, "_load_child_workflow", load_child)
    errors = executor._validate_workflow_call_step(
        {"uses": "./child.yml"}, "Call", _frames(tmp_path)
    )
    assert len(errors) == 1
    assert "Unknown template variables: ['network']" in errors[0]


# An unused parameter is reported with the names the child accepts.
def test_validate_call_step_reports_unused_parameter(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child: Dict[str, Any] = {
        "matrix": {"variant": ["one"]},
        "steps": [{"name": "inner", "with": {"output": "{{variant}}"}}],
    }

    def load_child(
        target: Any, step_name: str, parameter_names: Any = frozenset()
    ) -> Dict[str, Any]:
        return child

    monkeypatch.setattr(executor, "_load_child_workflow", load_child)
    errors = executor._validate_workflow_call_step(
        {"uses": "./child.yml", "with": {"labl": "x"}},
        "Call",
        _frames(tmp_path),
    )
    assert len(errors) == 1
    assert "Parameter 'labl' is not used by workflow 'child.yml'" in errors[0]
    assert "Accepted: ['variant']" in errors[0]


# A workflow call runs once per workflow, not once per matrix job.
def test_run_call_step_skips_later_jobs(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path, job_index=1)
    loaded: List[Any] = []

    def load_child(
        target: Any, step_name: str, parameter_names: Any = frozenset()
    ) -> Dict[str, Any]:
        loaded.append(target)
        return {}

    monkeypatch.setattr(executor, "_load_child_workflow", load_child)
    executor._run_workflow_call_step(
        state, {"name": "Call", "uses": "./child.yml"}, "Call"
    )
    assert loaded == []
    assert state.step_results["Call"]["status"] == "skipped"


# A call step runs the child with its own parameters only.
def test_run_call_step_executes_child(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    child = {"steps": [{"name": "inner"}]}
    captured: Dict[str, Any] = {}

    def load_child(
        target: Any, step_name: str, parameter_names: Any = frozenset()
    ) -> Dict[str, Any]:
        return child

    def record_jobs(
        workflow: Dict[str, Any],
        mode: str,
        cli_params: Dict[str, Any],
        step_logger: Any,
        frames: Any,
    ) -> List[Dict[str, Any]]:
        captured.update(
            workflow=workflow,
            mode=mode,
            cli_params=cli_params,
            frames=frames,
        )
        return [{"steps": {"inner": {"status": "success"}}}]

    monkeypatch.setattr(executor, "_load_child_workflow", load_child)
    monkeypatch.setattr(executor, "_execute_jobs", record_jobs)
    executor._run_workflow_call_step(
        state,
        {"name": "Call", "uses": "./child.yml", "with": {"x": 1}},
        "Call",
    )
    summary = state.step_results["Call"]
    assert captured["workflow"] is child
    assert captured["mode"] == "run"
    assert captured["cli_params"] == {"x": 1}
    assert captured["frames"][-1].path == (tmp_path / "child.yml").resolve()
    assert summary["status"] == "success"
    assert summary["jobs"] == 1
    assert summary["parameters"] == {"x": 1}
    assert summary["steps"] == [{"name": "inner", "status": "success"}]


# A matrix parameter replaces the child's dimension.
def test_run_call_step_overrides_child_matrix(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    child = {"matrix": {"variant": ["one", "two"]}, "steps": []}
    captured: Dict[str, Any] = {}

    def load_child(
        target: Any, step_name: str, parameter_names: Any = frozenset()
    ) -> Dict[str, Any]:
        return child

    def record_jobs(
        workflow: Dict[str, Any], *args: Any
    ) -> List[Dict[str, Any]]:
        captured.update(workflow=workflow, variables=args[1])
        return []

    monkeypatch.setattr(executor, "_load_child_workflow", load_child)
    monkeypatch.setattr(executor, "_execute_jobs", record_jobs)
    executor._run_workflow_call_step(
        state,
        {"name": "Call", "uses": "./child.yml", "with": {"variant": "two"}},
        "Call",
    )
    assert captured["workflow"]["matrix"] == {"variant": ["two"]}
    assert captured["variables"] == {}
    assert child["matrix"] == {"variant": ["one", "two"]}


# A caller's list parameter fans out the called workflow's matrix.
def test_run_call_step_forwards_list_parameter(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    state.variables = {"network": ["asia", "sports"]}
    child = {"matrix": {"network": ["asia"]}, "steps": []}
    captured: Dict[str, Any] = {}

    def load_child(
        target: Any, step_name: str, parameter_names: Any = frozenset()
    ) -> Dict[str, Any]:
        return child

    def record_jobs(
        workflow: Dict[str, Any], *args: Any
    ) -> List[Dict[str, Any]]:
        captured.update(workflow=workflow, variables=args[1])
        return []

    monkeypatch.setattr(executor, "_load_child_workflow", load_child)
    monkeypatch.setattr(executor, "_execute_jobs", record_jobs)
    executor._run_workflow_call_step(
        state,
        {
            "name": "Call",
            "uses": "./child.yml",
            "with": {"network": "{{network}}"},
        },
        "Call",
    )
    assert captured["workflow"]["matrix"] == {"network": ["asia", "sports"]}
    assert captured["variables"] == {}


# Call summaries report the aggregate child status.
@pytest.mark.parametrize(
    ("mode", "child_status", "expected"),
    [
        ("run", "success", "success"),
        ("run", "skipped", "success"),
        ("run", "error", "error"),
        ("dry-run", "would_execute", "would_execute"),
        ("dry-run", "would_skip", "would_skip"),
    ],
)
def test_summarise_call_status(
    tmp_path: Path, mode: str, child_status: str, expected: str
) -> None:
    results = [{"steps": {"inner": {"status": child_status}}}]
    summary = _summarise_call(tmp_path / "child.yml", results, mode, {})
    assert summary["status"] == expected


# Failed child steps are reported as call errors.
def test_summarise_call_collects_errors(tmp_path: Path) -> None:
    results = [
        {
            "steps": {
                "inner": {
                    "status": "error",
                    "reason": "boom",
                    "errors": ["boom detail"],
                }
            }
        }
    ]
    summary = _summarise_call(tmp_path / "child.yml", results, "run", {})
    assert summary["errors"] == ["inner: boom"]
    assert summary["steps"][0]["errors"] == ["boom detail"]


# A call is announced before the called workflow's steps are logged.
def test_run_call_step_announces_before_child(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logged: List[Any] = []
    state = _state(tmp_path, logger=lambda *args: logged.append(args))

    def load_child(
        target: Any, step_name: str, parameter_names: Any = frozenset()
    ) -> Dict[str, Any]:
        return {"steps": []}

    def run_jobs(*args: Any) -> List[Dict[str, Any]]:
        logged.append(("child", "inner", "SUCCESS", {}))
        return [{"steps": {"inner": {"status": "success"}}}]

    monkeypatch.setattr(executor, "_load_child_workflow", load_child)
    monkeypatch.setattr(executor, "_execute_jobs", run_jobs)
    executor._run_workflow_call_step(
        state, {"name": "Call", "uses": "./child.yml"}, "Call"
    )
    assert logged[0][0] == "./child.yml"
    assert logged[0][1] == "Call"
    assert logged[0][2] == "CALLING"
    assert logged[0][3] == {}
    assert logged[1][0] == "child"


# The CLI summary counts a called workflow's steps, not the call step.
def test_count_results_counts_called_steps() -> None:
    results = [
        {
            "steps": {
                "Call child": {
                    "status": "would_skip",
                    "workflow": "child.yml",
                    "jobs": 2,
                    "steps": [
                        {"name": "Child record", "status": "would_skip"},
                        {"name": "Child record", "status": "would_skip"},
                    ],
                }
            }
        }
    ]
    counts = _count_results(results, "dry-run")
    assert counts.would_skip == 2
    assert counts.total == 2


# Every call step's nested steps are counted across the whole run.
def test_count_results_counts_all_call_steps() -> None:
    def call_step(status: str) -> Dict[str, Any]:
        return {
            "status": status,
            "workflow": "child.yml",
            "jobs": 2,
            "steps": [
                {"name": "Child record", "status": status},
                {"name": "Child record", "status": status},
            ],
        }

    results = [
        {
            "steps": {
                "Call one": call_step("would_skip"),
                "Call two": call_step("would_execute"),
                "Call three": call_step("would_execute"),
            }
        }
    ]
    counts = _count_results(results, "dry-run")
    assert counts.would_skip == 2
    assert counts.would_execute == 4
    assert counts.new_entries == 4
    assert counts.total == 6


# The CLI summary reports failures from a called workflow.
def test_count_results_reports_called_failures() -> None:
    results = [
        {
            "steps": {
                "Call child": {
                    "status": "error",
                    "workflow": "child.yml",
                    "steps": [
                        {
                            "name": "Child record",
                            "status": "error",
                            "errors": ["boom"],
                        }
                    ],
                }
            }
        }
    ]
    counts = _count_results(results, "run")
    assert counts.failed == 1
    assert counts.errors == ["  Child record: boom"]


# Workflow calls run once when their parameters are constant.
def test_runs_once_for_workflow_call() -> None:
    assert _runs_once({"uses": "./child.yml"}, {}) is True


# A call whose parameters vary per combination runs per combination.
def test_not_runs_once_for_matrix_parameter_call() -> None:
    step = {"uses": "./child.yml", "with": {"variant": "{{variant}}"}}
    assert _runs_once(step, {"variant": ["one", "two"]}) is False


# A call with a literal parameter still runs once per workflow.
def test_runs_once_for_literal_parameter_call() -> None:
    step = {"uses": "./child.yml", "with": {"variant": "one"}}
    assert _runs_once(step, {"variant": ["one", "two"]}) is True


# Call parameters are resolved in the caller's context.
def test_run_call_step_resolves_caller_variables(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    state.variables.update({"variant": "two"})
    captured: Dict[str, Any] = {}

    def load_child(
        target: Any, step_name: str, parameter_names: Any = frozenset()
    ) -> Dict[str, Any]:
        captured["names"] = set(parameter_names)
        return {"matrix": {"variant": ["one"]}, "steps": []}

    def record_jobs(
        workflow: Dict[str, Any], *args: Any
    ) -> List[Dict[str, Any]]:
        captured["matrix"] = workflow["matrix"]
        return []

    monkeypatch.setattr(executor, "_load_child_workflow", load_child)
    monkeypatch.setattr(executor, "_execute_jobs", record_jobs)
    executor._run_workflow_call_step(
        state,
        {
            "name": "Call",
            "uses": "./child.yml",
            "with": {"variant": "{{variant}}"},
        },
        "Call",
    )
    assert captured["names"] == {"variant"}
    assert captured["matrix"] == {"variant": ["two"]}


# A workflow file named without a dot prefix is reported clearly.
def test_missing_prefix_reports_workflow_file(
    executor: WorkflowExecutor,
) -> None:
    workflow = {"steps": [{"name": "Call", "uses": "workflows/child.yml"}]}
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor._validate_workflow_actions(workflow, "validate")
    assert "require a './' or '../' prefix" in str(exc_info.value)


# Call steps are not validated as cache filters.
def test_call_step_filter_is_not_validated(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "steps": [
            {
                "name": "Call",
                "uses": "./child.yml",
                "with": {"filter": "unquoted == value"},
            }
        ]
    }
    assert executor._validate_step_filters(workflow) == []


# Per-entry validation dispatches call steps to the call validator.
def test_validate_step_entries_dispatches_calls(
    executor: WorkflowExecutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    def validate_call(step: Any, step_name: str, frames: Any) -> List[str]:
        return ["call error"]

    monkeypatch.setattr(
        executor, "_validate_workflow_call_step", validate_call
    )
    errors = executor._validate_step_entries(
        {"name": "Call", "uses": "./child.yml"}, [{}], {}, {}, {}
    )
    assert errors == ["call error"]
