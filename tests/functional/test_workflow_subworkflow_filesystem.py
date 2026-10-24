"""Functional tests for calling another workflow from a YAML file."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from causaliq_core import CausalIQActionProvider

from causaliq_workflow.cache import WorkflowCache
from causaliq_workflow.schema import load_workflow_file
from causaliq_workflow.workflow import (
    WorkflowExecutionError,
    WorkflowExecutor,
)

_DATA_DIR = Path(__file__).parent.parent / "data" / "functional" / "workflow"


class _RecordProvider(CausalIQActionProvider):
    """Provider producing one JSON object per cache entry."""

    __test__ = False

    name = "subworkflow-test"
    version = "1.0.0"
    description = "Single-object provider for sub-workflow tests"
    author = "CausalIQ"

    supported_actions = {"record"}

    def _dry_run_result(self, action: str, parameters: Dict[str, Any]) -> Any:
        """Return a dry-run placeholder result."""
        return ("skipped", {"dry_run": True}, [])

    def _execute(
        self,
        action: str,
        parameters: Dict[str, Any],
        mode: str,
        context: Optional[Any],
        logger: Optional[Any],
    ) -> Any:
        """Return one JSON object recording the action and mode."""
        payload = json.dumps({"action": action, "mode": mode})
        objects = [{"type": "json", "name": "record", "content": payload}]
        return ("success", {"recorded": True}, objects)


@pytest.fixture
def executor() -> WorkflowExecutor:
    """Return an executor with the record provider registered."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["subworkflow-test"] = _RecordProvider
    return executor


def _prepare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> Path:
    """Copy workflow-call fixtures into a temporary working directory."""
    for path in _DATA_DIR.glob("subworkflow_*.yml"):
        shutil.copy(path, tmp_path / path.name)
    monkeypatch.chdir(tmp_path)
    return tmp_path / name


# A dry-run previews the child workflow without writing caches.
def test_dry_run_previews_child(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = executor.parse_workflow(
        _prepare(tmp_path, monkeypatch, "subworkflow_parent.yml")
    )
    results = executor.execute_workflow(workflow, mode="dry-run")
    summary = results[0]["steps"]["Call child"]
    assert summary["status"] == "would_execute"
    assert summary["jobs"] == 2
    assert [step["status"] for step in summary["steps"]] == [
        "would_execute",
        "would_execute",
    ]
    assert not (tmp_path / "child.db").exists()


# A run executes the child and writes its cache entries.
def test_run_writes_child_cache(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = executor.parse_workflow(
        _prepare(tmp_path, monkeypatch, "subworkflow_parent.yml")
    )
    results = executor.execute_workflow(workflow, mode="run")
    summary = results[0]["steps"]["Call child"]
    assert summary["status"] == "success"
    with WorkflowCache(str(tmp_path / "child.db")) as cache:
        entries = cache.list_entries()
    variants = {entry["matrix_values"]["variant"] for entry in entries}
    assert variants == {"one", "two"}


# A calling matrix does not repeat the child and is not forwarded.
def test_parent_matrix_runs_child_once(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = executor.parse_workflow(
        _prepare(tmp_path, monkeypatch, "subworkflow_matrix_parent.yml")
    )
    results = executor.execute_workflow(workflow, mode="run")
    statuses = [job["steps"]["Call child"]["status"] for job in results]
    assert statuses == ["success", "skipped"]
    with WorkflowCache(str(tmp_path / "child.db")) as cache:
        assert cache.entry_count() == 2


# Validation mode validates the child without executing it.
def test_validate_mode_executes_nothing(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = executor.parse_workflow(
        _prepare(tmp_path, monkeypatch, "subworkflow_parent.yml")
    )
    assert executor.execute_workflow(workflow, mode="validate") == []
    assert not (tmp_path / "child.db").exists()


# A missing child workflow is reported against the calling step.
def test_missing_child_workflow_reports_step(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = executor.parse_workflow(
        _prepare(tmp_path, monkeypatch, "subworkflow_missing.yml")
    )
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.execute_workflow(workflow, mode="validate")
    message = str(exc_info.value)
    assert "Step 'Call missing'" in message
    assert "not found" in message.lower()


# A workflow may not call itself.
def test_self_recursion_is_rejected(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = executor.parse_workflow(
        _prepare(tmp_path, monkeypatch, "subworkflow_self_recursive.yml")
    )
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.execute_workflow(workflow, mode="validate")
    assert "recursive workflow call detected" in str(exc_info.value)


# Two workflows may not call each other in a cycle.
def test_indirect_recursion_is_rejected(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = executor.parse_workflow(
        _prepare(tmp_path, monkeypatch, "subworkflow_recursive_parent.yml")
    )
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.execute_workflow(workflow, mode="validate")
    message = str(exc_info.value)
    assert "recursive workflow call detected" in message
    assert "subworkflow_recursive_parent.yml" in message
    assert "subworkflow_recursive_child.yml" in message


# Executor-reserved parameters are rejected on a call step.
def test_reserved_parameters_are_rejected(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = executor.parse_workflow(
        _prepare(tmp_path, monkeypatch, "subworkflow_reserved.yml")
    )
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.execute_workflow(workflow, mode="validate")
    assert "do not support 'action' in 'with'" in str(exc_info.value)


# An explicit source path resolves calls without prior parsing.
def test_source_path_resolves_calls(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _prepare(tmp_path, monkeypatch, "subworkflow_parent.yml")
    workflow = load_workflow_file(path)
    results = executor.execute_workflow(
        workflow, mode="dry-run", source_path=path
    )
    assert results[0]["steps"]["Call child"]["status"] == "would_execute"
