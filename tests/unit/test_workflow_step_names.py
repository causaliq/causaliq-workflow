"""Unit tests for template placeholders in workflow step names."""

from pathlib import Path
from typing import Any, Dict, List

import pytest

from causaliq_workflow.workflow import (
    WorkflowExecutionError,
    WorkflowExecutor,
)
from causaliq_workflow.workflow.parameters import _unused_parameter_errors


def _single_step(name: str, **parameters: Any) -> Dict[str, Any]:
    """Return a one-step workflow whose step uses a single token name."""
    return {
        **parameters,
        "steps": [
            {
                "name": name,
                "uses": "mock_workflow_action",
                "with": {"action": "test"},
            }
        ],
    }


# A declared parameter default is expanded in the step name.
def test_step_name_expands_declared_parameter_default(
    executor: WorkflowExecutor,
) -> None:
    workflow = _single_step("Learn for {{series}}", series="asia")

    results = executor.execute_workflow(workflow, mode="dry-run")

    assert list(results[0]["steps"]) == ["Learn for asia"]


# A matrix variable gives each job its own expanded step name.
def test_step_name_expands_matrix_value_per_job(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "matrix": {"series": ["asia", "cancer"]},
        "steps": [
            {
                "name": "Learn for {{series}}",
                "uses": "mock_workflow_action",
                "with": {
                    "action": "test",
                    "series": "{{series}}",
                    "output": "graphs.db",
                },
            }
        ],
    }

    results = executor.execute_workflow(workflow, mode="dry-run")

    assert list(results[0]["steps"]) == ["Learn for asia"]
    assert list(results[1]["steps"]) == ["Learn for cancer"]


# A name that is exactly one token becomes the value's text form.
def test_step_name_expands_whole_token_name(
    executor: WorkflowExecutor,
) -> None:
    workflow = _single_step("{{series}}", series="asia")

    results = executor.execute_workflow(workflow, mode="dry-run")

    assert list(results[0]["steps"]) == ["asia"]


# A caller may supply the value for a name-only placeholder.
def test_step_name_expands_supplied_parameter(
    executor: WorkflowExecutor,
) -> None:
    workflow = _single_step("Learn for {{series}}")

    results = executor.execute_workflow(
        workflow, mode="dry-run", cli_params={"series": "asia"}
    )

    assert list(results[0]["steps"]) == ["Learn for asia"]


# A numeric value is expanded as its text form.
def test_step_name_expands_numeric_value_as_text(
    executor: WorkflowExecutor,
) -> None:
    workflow = _single_step("Learn with {{sample_size}}", sample_size=1000)

    results = executor.execute_workflow(workflow, mode="dry-run")

    assert list(results[0]["steps"]) == ["Learn with 1000"]


# A null value has no text form, so it renders as 'None'.
def test_step_name_renders_null_value_as_none(
    executor: WorkflowExecutor,
) -> None:
    workflow = _single_step("Learn for {{reference}}", reference=None)

    results = executor.execute_workflow(workflow, mode="dry-run")

    assert list(results[0]["steps"]) == ["Learn for None"]


# A list value renders as its Python list representation.
def test_step_name_renders_list_value(executor: WorkflowExecutor) -> None:
    workflow = _single_step("Learn for {{networks}}", networks=["asia"])

    results = executor.execute_workflow(workflow, mode="dry-run")

    assert list(results[0]["steps"]) == ["Learn for ['asia']"]


# A name without tokens is unchanged.
def test_step_name_without_tokens_is_unchanged(
    executor: WorkflowExecutor,
) -> None:
    results = executor.execute_workflow(
        _single_step("Learn for asia"), mode="dry-run"
    )

    assert list(results[0]["steps"]) == ["Learn for asia"]


# A placeholder in a name counts as a use of the declared parameter.
def test_step_name_token_counts_as_parameter_use() -> None:
    workflow = _single_step("Learn for {{series}}", series="asia")

    assert _unused_parameter_errors(workflow) == []


# An undeclared placeholder in a name is still reported.
def test_step_name_unknown_token_still_rejected(
    executor: WorkflowExecutor,
) -> None:
    workflow = _single_step("Learn for {{series}}")

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.execute_workflow(workflow, mode="dry-run")

    assert "Unknown template variables: ['series']" in str(exc_info.value)


# The step logger receives the expanded name.
def test_step_logger_receives_expanded_step_name(
    executor: WorkflowExecutor,
) -> None:
    logged: List[str] = []

    def step_logger(
        action: str, name: str, status: str, values: Dict[str, Any]
    ) -> None:
        logged.append(name)

    executor.execute_workflow(
        _single_step("Learn for {{series}}", series="asia"),
        mode="dry-run",
        step_logger=step_logger,
    )

    assert logged == ["Learn for asia"]


# Two steps that expand to the same name are rejected.
def test_duplicate_resolved_step_name_raises(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "series": "asia",
        "steps": [
            {
                "name": "Learn {{series}}",
                "uses": "mock_workflow_action",
                "with": {"action": "test"},
            },
            {
                "name": "Learn asia",
                "uses": "mock_workflow_action",
                "with": {"action": "test"},
            },
        ],
    }

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.execute_workflow(workflow, mode="dry-run")

    assert "already used by an earlier step" in str(exc_info.value)


# A step without a name falls back to its position.
def test_unnamed_step_uses_positional_name(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "steps": [
            {"uses": "mock_workflow_action", "with": {"action": "test"}},
        ],
    }

    results = executor.execute_workflow(workflow, mode="dry-run")

    assert list(results[0]["steps"]) == ["step-0"]


# A workflow-call step's name is expanded in the calling workflow.
def test_workflow_call_step_name_expands(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    (tmp_path / "child.yml").write_text(
        "steps:\n"
        '  - name: "Child"\n'
        '    uses: "mock_workflow_action"\n'
        "    with:\n"
        '      action: "test"\n',
        encoding="utf-8",
    )
    workflow = {
        "matrix": {"series": ["asia"]},
        "steps": [
            {
                "name": "Run child for {{series}}",
                "uses": "./child.yml",
                "with": {},
            }
        ],
    }

    results = executor.execute_workflow(
        workflow, mode="dry-run", source_path=tmp_path / "parent.yml"
    )

    assert list(results[0]["steps"]) == ["Run child for asia"]
