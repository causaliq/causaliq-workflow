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
        "name": "Test Workflow",
        "steps": [{"run": "echo hello"}, {"uses": "action@v1"}],
    }
    result = validate_workflow(valid_workflow)
    assert result is True


# Test workflow validation missing name field
def test_missing_name_field():
    """Test validation fails when required name field missing."""
    invalid_workflow = {"steps": [{"run": "echo hello"}]}
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation missing steps field
def test_missing_steps_field():
    """Test validation fails when required steps field missing."""
    invalid_workflow = {"name": "Test Workflow"}
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation with empty steps array
def test_empty_steps_array():
    """Test validation fails when steps array is empty."""
    invalid_workflow = {"name": "Test Workflow", "steps": []}
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation with invalid step structure
def test_step_missing_run_and_uses():
    """Test validation fails when step has neither run nor uses."""
    invalid_workflow = {
        "name": "Test Workflow",
        "steps": [{"name": "Invalid step"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation with optional id field
def test_valid_workflow_with_id():
    """Test validation passes with optional id field."""
    valid_workflow = {
        "name": "Test Workflow",
        "id": "test-workflow-001",
        "steps": [{"run": "echo hello"}],
    }
    result = validate_workflow(valid_workflow)
    assert result is True


# Test workflow validation with data_root and output_root
def test_valid_workflow_with_roots():
    """Test validation passes with data_root and output_root fields."""
    valid_workflow = {
        "name": "Test Workflow",
        "data_root": "/path/to/data",
        "output_root": "/path/to/output",
        "steps": [{"run": "echo hello"}],
    }
    result = validate_workflow(valid_workflow)
    assert result is True


# Test workflow validation with matrix variables
def test_valid_workflow_with_matrix():
    """Test validation passes with matrix variables."""
    valid_workflow = {
        "name": "Matrix Workflow",
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
        "name": "Parameterized Workflow",
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
        "name": "Complete Workflow",
        "id": "complete-test-001",
        "data_root": "/data",
        "output_root": "/results",
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
        },
        "steps": [
            {
                "name": "Structure Learning",
                "uses": "dummy-structure-learner",
                "with": {
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
        "name": "Invalid Matrix",
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
        "name": "Invalid Matrix Variable",
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
        "name": "Invalid With Parameter",
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
        "name": "Test Workflow",
        "steps": [{"run": "echo hello"}],
    }

    # Mock import to raise ImportError
    with patch.dict("sys.modules", {"jsonschema": None}):
        with pytest.raises(WorkflowValidationError) as exc_info:
            validate_workflow(valid_workflow)
        assert "jsonschema library required" in str(exc_info.value)
