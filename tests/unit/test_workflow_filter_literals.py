"""Unit tests for bare filter literals in workflows."""

from typing import Any, Dict

from causaliq_workflow.workflow import WorkflowExecutor
from causaliq_workflow.workflow.filters import (
    relax_step_filter_literals,
)


# A bare comparison value is rewritten as a string literal.
def test_relax_step_filter_value() -> None:
    workflow = {
        "steps": [
            {"name": "s", "with": {"filter": "status == ok"}},
        ]
    }
    relax_step_filter_literals(workflow)
    assert workflow["steps"][0]["with"]["filter"] == "status == 'ok'"


# A declared parameter stays a reference on the right.
def test_declared_parameter_is_not_quoted() -> None:
    workflow = {
        "description": "text",
        "steps": [
            {
                "name": "s",
                "with": {"filter": "description == description"},
            }
        ],
    }
    relax_step_filter_literals(workflow)
    assert (
        workflow["steps"][0]["with"]["filter"] == "description == description"
    )


# A matrix variable stays a reference on the right.
def test_matrix_variable_is_not_quoted() -> None:
    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {"name": "s", "with": {"filter": "flag == network"}},
        ],
    }
    relax_step_filter_literals(workflow)
    assert workflow["steps"][0]["with"]["filter"] == "flag == network"


# A supplied parameter stays a reference on the right.
def test_supplied_parameter_is_not_quoted() -> None:
    workflow = {
        "steps": [
            {"name": "s", "with": {"filter": "flag == seed"}},
        ]
    }
    relax_step_filter_literals(workflow, {"seed"})
    assert workflow["steps"][0]["with"]["filter"] == "flag == seed"


# A name used as a left side is not quoted on the right.
def test_left_hand_name_is_not_quoted() -> None:
    workflow = {
        "steps": [
            {"name": "s", "with": {"filter": "a == b and b == c"}},
        ]
    }
    relax_step_filter_literals(workflow)
    assert workflow["steps"][0]["with"]["filter"] == "a == b and b == 'c'"


# A non-string filter is left untouched for validation.
def test_non_string_filter_is_untouched() -> None:
    workflow = {"steps": [{"name": "s", "with": {"filter": 3}}]}
    relax_step_filter_literals(workflow)
    assert workflow["steps"][0]["with"]["filter"] == 3


# An empty filter is left untouched.
def test_empty_filter_is_untouched() -> None:
    workflow = {"steps": [{"name": "s", "with": {"filter": "  "}}]}
    relax_step_filter_literals(workflow)
    assert workflow["steps"][0]["with"]["filter"] == "  "


# Invalid filter syntax is left untouched for validation to report.
def test_invalid_filter_is_untouched() -> None:
    workflow = {"steps": [{"name": "s", "with": {"filter": "a =="}}]}
    relax_step_filter_literals(workflow)
    assert workflow["steps"][0]["with"]["filter"] == "a =="


# A non-list steps value is ignored.
def test_non_list_steps_is_ignored() -> None:
    workflow: Dict[str, Any] = {"steps": "bad"}
    relax_step_filter_literals(workflow)
    assert workflow["steps"] == "bad"


# A step or with block of the wrong shape is ignored.
def test_malformed_step_is_ignored() -> None:
    workflow: Dict[str, Any] = {"steps": ["bad", {"name": "s", "with": "bad"}]}
    relax_step_filter_literals(workflow)
    assert workflow["steps"][0] == "bad"


# A non-dictionary matrix is ignored when collecting reserved names.
def test_non_dict_matrix_is_ignored() -> None:
    workflow: Dict[str, Any] = {
        "matrix": "bad",
        "steps": [{"name": "s", "with": {"filter": "a == b"}}],
    }
    relax_step_filter_literals(workflow)
    assert workflow["steps"][0]["with"]["filter"] == "a == 'b'"


# Relaxing twice produces the same expression.
def test_relaxation_is_idempotent() -> None:
    workflow = {"steps": [{"name": "s", "with": {"filter": "a == b"}}]}
    relax_step_filter_literals(workflow)
    first = workflow["steps"][0]["with"]["filter"]
    relax_step_filter_literals(workflow)
    assert workflow["steps"][0]["with"]["filter"] == first


# Parsing a workflow relaxes its filters before validation.
def test_parse_workflow_relaxes_filters(monkeypatch) -> None:
    workflow: Dict[str, Any] = {
        "description": "text",
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "s",
                "uses": "provider",
                "with": {
                    "action": "act",
                    "filter": "network == asia and description == description",
                },
            }
        ],
    }
    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        lambda path: workflow,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow",
        lambda data: True,
    )
    executor = WorkflowExecutor()
    monkeypatch.setattr(
        executor, "_validate_template_variables", lambda *args: None
    )
    monkeypatch.setattr(
        executor, "_validate_workflow_actions", lambda *args: None
    )
    result = executor.parse_workflow("workflow.yml")
    assert result["steps"][0]["with"]["filter"] == (
        "network == 'asia' and description == description"
    )


# Executing a workflow dictionary relaxes its filters too.
def test_execute_workflow_relaxes_filters(monkeypatch) -> None:
    captured: Dict[str, Any] = {}

    def fake_execute(workflow, mode, cli_params, step_logger, frames):
        captured["filter"] = workflow["steps"][0]["with"]["filter"]
        return []

    executor = WorkflowExecutor()
    monkeypatch.setattr(executor, "_validate_execution", lambda *args: None)
    monkeypatch.setattr(executor, "_execute_jobs", fake_execute)
    workflow = {
        "steps": [
            {"name": "s", "uses": "provider", "with": {"filter": "a == b"}},
        ]
    }
    executor.execute_workflow(workflow, mode="run")
    assert captured["filter"] == "a == 'b'"
