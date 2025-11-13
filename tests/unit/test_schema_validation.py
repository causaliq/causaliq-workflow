"""Unit tests for schema validation - no filesystem access."""

from unittest.mock import patch

import pytest

from causaliq_pipeline.schema import WorkflowValidationError, validate_workflow


# Test WorkflowValidationError exception creation
def test_error_with_message_only():
    """Test creating error with message only."""
    error = WorkflowValidationError("Test error")
    assert str(error) == "Test error"
    assert error.schema_path == ""


# Test WorkflowValidationError with schema path
def test_error_with_schema_path():
    """Test creating error with schema path information."""
    error = WorkflowValidationError(
        "Validation failed", schema_path="steps[0].run"
    )
    assert str(error) == "Validation failed"
    assert error.schema_path == "steps[0].run"


# Test workflow validation with valid workflow data
def test_valid_workflow():
    """Test validating a properly structured workflow."""
    valid_workflow = {
        "id": "test-workflow",
        "description": "Test workflow for validation",
        "steps": [{"run": "echo hello"}, {"uses": "action@v1"}],
    }
    result = validate_workflow(valid_workflow)
    assert result is True


# Test workflow validation with minimal valid workflow
def test_minimal_valid_workflow():
    """Test validation passes with only required fields."""
    minimal_workflow = {
        "id": "minimal-test",
        "description": "Minimal test workflow",
        "steps": [{"run": "echo hello"}],
    }
    result = validate_workflow(minimal_workflow)
    assert result is True


# Test workflow validation missing id field
def test_missing_id_field():
    """Test validation fails when required id field missing."""
    invalid_workflow = {
        "description": "Test workflow without id",
        "steps": [{"run": "echo hello"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation missing description field
def test_missing_description_field():
    """Test validation fails when required description field missing."""
    invalid_workflow = {
        "id": "test-workflow",
        "steps": [{"run": "echo hello"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation missing steps field
def test_missing_steps_field():
    """Test validation fails when required steps field missing."""
    invalid_workflow = {
        "id": "test-workflow",
        "description": "Test workflow without steps",
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation with empty steps array
def test_empty_steps_array():
    """Test validation fails when steps array is empty."""
    invalid_workflow = {
        "id": "test-workflow",
        "description": "Test workflow with empty steps",
        "steps": [],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation with invalid step structure
def test_step_missing_run_and_uses():
    """Test validation fails when step has neither run nor uses."""
    invalid_workflow = {
        "id": "test-workflow",
        "description": "Test workflow with invalid step",
        "steps": [{"name": "Invalid step"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation with matrix variables
def test_valid_workflow_with_matrix():
    """Test validation passes with matrix variables."""
    valid_workflow = {
        "id": "matrix-workflow",
        "description": "Workflow with matrix variables",
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
            "alpha": [0.01, 0.05],
        },
        "steps": [{"uses": "dummy-structure-learner"}],
    }
    result = validate_workflow(valid_workflow)
    assert result is True


# Test workflow validation with with parameters
def test_valid_workflow_with_parameters():
    """Test validation passes with action parameters."""
    valid_workflow = {
        "id": "parameterized-workflow",
        "description": "Workflow with action parameters",
        "steps": [
            {
                "uses": "dummy-structure-learner",
                "with": {
                    "dataset": "asia",
                    "algorithm": "pc",
                    "alpha": 0.05,
                },
            }
        ],
    }
    result = validate_workflow(valid_workflow)
    assert result is True


# Test workflow validation with all new features combined
def test_valid_workflow_with_all_features():
    """Test validation passes with all new schema features."""
    valid_workflow = {
        "id": "complete-test-001",
        "description": "Complete workflow with all features",
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
        },
        "steps": [
            {
                "name": "Structure Learning",
                "uses": "dummy-structure-learner",
                "with": {
                    "dataset": "/experiments/data/{{dataset}}.csv",
                    "result": (
                        "/experiments/results/{{id}}/{{algorithm}}/"
                        "graph_{{dataset}}.xml"
                    ),
                    "alpha": 0.05,
                    "max_iter": 1000,
                },
            }
        ],
    }
    result = validate_workflow(valid_workflow)
    assert result is True


# Test workflow validation fails with invalid matrix format
def test_invalid_matrix_format():
    """Test validation fails with invalid matrix structure."""
    invalid_workflow = {
        "id": "invalid-matrix",
        "description": "Workflow with invalid matrix structure",
        "matrix": {
            "dataset": [],  # Empty array not allowed
        },
        "steps": [{"run": "echo hello"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation fails with invalid matrix variable name
def test_invalid_matrix_variable_name():
    """Test validation fails with invalid matrix variable name."""
    invalid_workflow = {
        "id": "invalid-matrix-var",
        "description": "Workflow with invalid matrix variable name",
        "matrix": {
            "123invalid": ["value"],  # Invalid variable name
        },
        "steps": [{"run": "echo hello"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation fails with invalid with parameter name
def test_invalid_with_parameter_name():
    """Test validation fails with invalid with parameter name."""
    invalid_workflow = {
        "id": "invalid-with-param",
        "description": "Workflow with invalid with parameter name",
        "steps": [
            {
                "uses": "action",
                "with": {
                    "123invalid": "value",  # Invalid parameter name
                },
            }
        ],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation when jsonschema import fails
def test_missing_jsonschema_import():
    """Test validation fails gracefully when jsonschema not available."""
    valid_workflow = {
        "id": "test-workflow",
        "description": "Test workflow for import error handling",
        "steps": [{"run": "echo hello"}],
    }

    # Mock import to raise ImportError
    with patch.dict("sys.modules", {"jsonschema": None}):
        with pytest.raises(WorkflowValidationError) as exc_info:
            validate_workflow(valid_workflow)
        assert "jsonschema library required" in str(exc_info.value)
