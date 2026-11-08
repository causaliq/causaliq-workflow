"""Unit tests for workflow parsing and loading."""

import pytest

from causaliq_workflow.schema import WorkflowValidationError
from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor


# Test WorkflowExecutionError exception creation
def test_workflow_execution_error():
    """Test creating WorkflowExecutionError with message."""
    error = WorkflowExecutionError("Test error")
    assert str(error) == "Test error"


def test_parse_workflow_success(monkeypatch):
    """Test successful workflow parsing with valid YAML."""
    # Setup mocks
    workflow_data = {
        "steps": [{"name": "Test", "run": "echo hello"}],
    }

    def fake_load_workflow_file(path):
        assert path == "/path/to/workflow.yml"
        return workflow_data

    def fake_validate_workflow(data):
        assert data == workflow_data
        return True

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate_workflow
    )
    executor = WorkflowExecutor()
    result = executor.parse_workflow("/path/to/workflow.yml")
    assert result == workflow_data


def test_parse_workflow_validation_error(monkeypatch):
    """Test workflow parsing fails with validation error."""
    # Setup mocks
    workflow_data = {"name": "Test"}  # Missing steps

    def fake_load_workflow_file(path):
        assert path == "/path/to/workflow.yml"
        return workflow_data

    def fake_validate_workflow(data):
        assert data == workflow_data
        raise WorkflowValidationError("Missing steps field")

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate_workflow
    )
    executor = WorkflowExecutor()
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("/path/to/workflow.yml")
    assert "Workflow parsing failed" in str(exc_info.value)


def test_parse_workflow_valid_templates(monkeypatch):
    """Test workflow parsing with valid template variables."""
    workflow_data = {
        "id": "exp-001",
        "matrix": {"dataset": ["asia"], "algorithm": ["pc"]},
        "steps": [
            {
                "uses": "test_action",
                "with": {
                    "result": "/results/{{id}}/{{dataset}}_{{algorithm}}.xml"
                },
            }
        ],
    }

    def fake_load_workflow_file(path):
        assert path == "test.yml"
        return workflow_data

    def fake_validate_workflow(data):
        assert data == workflow_data
        return True

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate_workflow
    )
    executor = WorkflowExecutor()
    executor.action_registry.validate_workflow_actions = lambda workflow: []
    result = executor.parse_workflow("test.yml")
    assert result == workflow_data


def test_parse_workflow_invalid_templates(monkeypatch):
    """Test workflow parsing fails with invalid template variables."""
    workflow_data = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "action",
                "with": {"result": "/results/{{unknown_var}}/{{dataset}}.xml"},
            }
        ],
    }

    def fake_load_workflow_file(path):
        assert path == "test.yml"
        return workflow_data

    def fake_validate_workflow(data):
        assert data == workflow_data
        return True

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate_workflow
    )
    executor = WorkflowExecutor()
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    error_msg = str(exc_info.value)
    assert "Unknown template variables: ['unknown_var']" in error_msg
    assert "Available variables: ['dataset']" in error_msg


def test_parse_workflow_no_matrix_valid_templates(monkeypatch):
    """Test workflow parsing with declared parameters only."""
    workflow_data = {
        "id": "exp-001",
        "description": "example",
        "steps": [
            {
                "uses": "test_action",
                "with": {"output": "/results/{{id}}_{{description}}.txt"},
            }
        ],
    }

    def fake_load_workflow_file(path):
        assert path == "test.yml"
        return workflow_data

    def fake_validate_workflow(data):
        assert data == workflow_data
        return True

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate_workflow
    )
    executor = WorkflowExecutor()
    executor.action_registry.validate_workflow_actions = lambda workflow: []
    result = executor.parse_workflow("test.yml")
    assert result == workflow_data


# Test parse_workflow wraps generic exceptions.
def test_parse_workflow_wraps_generic_exception(monkeypatch):
    """Tests lines 100-101 in workflow.py - generic exception wrapping."""

    def fake_load_workflow_file(path):
        raise TypeError("Unexpected type error during parsing")

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )

    executor = WorkflowExecutor()
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("/path/to/workflow.yml")

    assert "Unexpected error parsing workflow" in str(exc_info.value)
    assert "Unexpected type error during parsing" in str(exc_info.value)
