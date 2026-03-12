"""Unit tests for schema validation - no filesystem access."""

import sys

import pytest

from causaliq_workflow.schema import WorkflowValidationError, validate_workflow


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
        "steps": [
            {"name": "Test", "run": "echo hello"},
            {"name": "Test", "uses": "action@v1"},
        ],
    }
    result = validate_workflow(valid_workflow)
    assert result is True


# Test workflow validation with minimal valid workflow
def test_minimal_valid_workflow():
    """Test validation passes with only required fields."""
    minimal_workflow = {
        "steps": [{"name": "Test", "run": "echo hello"}],
    }
    result = validate_workflow(minimal_workflow)
    assert result is True


# Test workflow validation missing steps field
def test_missing_steps_field():
    """Test validation fails when required steps field missing."""
    invalid_workflow = {}
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation with empty steps array
def test_empty_steps_array():
    """Test validation fails when steps array is empty."""
    invalid_workflow = {
        "steps": [],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation with invalid step structure
def test_step_missing_run_and_uses():
    """Test validation fails when step has neither run nor uses."""
    invalid_workflow = {
        "steps": [{"name": "Invalid step"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "Missing 'uses' or 'run' parameter" in str(exc_info.value)


# Test workflow validation with missing step name.
def test_step_missing_name():
    """Test validation fails when step has no name."""
    invalid_workflow = {
        "steps": [{"uses": "test_action"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "Step missing 'name' parameter" in str(exc_info.value)


# Test pre-validation skips when steps is not a list.
def test_pre_validate_skips_non_list_steps():
    """Test pre-validation defers to jsonschema when steps is not a list."""
    invalid_workflow = {
        "steps": "not-a-list",
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    # jsonschema handles this - error mentions type mismatch
    assert "validation failed" in str(exc_info.value).lower()


# Test pre-validation skips non-dict step items.
def test_pre_validate_skips_non_dict_step():
    """Test pre-validation defers to jsonschema when step is not a dict."""
    invalid_workflow = {
        "steps": ["not-a-dict"],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    # jsonschema handles this - error mentions type mismatch
    assert "validation failed" in str(exc_info.value).lower()


# Test pre-validation catches unknown top-level keys.
def test_pre_validate_catches_unknown_keys():
    """Test pre-validation catches unknown top-level keys."""
    invalid_workflow = {
        "matrixx": {"dataset": ["asia"]},
        "steps": [{"name": "Test", "uses": "test_action"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "Unknown key 'matrixx'" in str(exc_info.value)


# Test workflow validation with matrix variables
def test_valid_workflow_with_matrix():
    """Test validation passes with matrix variables."""
    valid_workflow = {
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
            "alpha": [0.01, 0.05],
        },
        "steps": [{"name": "Test", "uses": "test_action"}],
    }
    result = validate_workflow(valid_workflow)
    assert result is True


# Test workflow validation with with parameters
def test_valid_workflow_with_parameters():
    """Test validation passes with action parameters."""
    valid_workflow = {
        "steps": [
            {
                "name": "Test",
                "uses": "test_action",
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
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
        },
        "steps": [
            {
                "name": "Structure Learning",
                "uses": "test_action",
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
        "matrix": {
            "dataset": [],  # Empty array not allowed
        },
        "steps": [{"name": "Test", "run": "echo hello"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation fails with invalid matrix variable name
def test_invalid_matrix_variable_name():
    """Test validation fails with invalid matrix variable name."""
    invalid_workflow = {
        "matrix": {
            "123invalid": ["value"],  # Invalid variable name
        },
        "steps": [{"name": "Test", "run": "echo hello"}],
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        validate_workflow(invalid_workflow)
    assert "validation failed" in str(exc_info.value).lower()


# Test workflow validation fails with invalid with parameter name
def test_invalid_with_parameter_name():
    """Test validation fails with invalid with parameter name."""
    invalid_workflow = {
        "steps": [
            {
                "name": "Test",
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
    """Test validation fails gracefully when jsonschema not available."""
    valid_workflow = {
        "steps": [{"name": "Test", "run": "echo hello"}],
    }

    import builtins

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError("Mock: jsonschema not available")
        return original_import(name, *args, **kwargs)

    builtins.__import__ = mock_import
    try:
        with pytest.raises(WorkflowValidationError) as exc_info:
            validate_workflow(valid_workflow)
        assert "jsonschema library required" in str(exc_info.value)
    finally:
        builtins.__import__ = original_import


# Test jsonschema ImportError handling
def test_schema_jsonschema_import_error():
    # Temporarily replace the import to simulate ImportError
    original_modules = dict(sys.modules)

    try:
        # Remove jsonschema from modules if present
        if "jsonschema" in sys.modules:
            del sys.modules["jsonschema"]

        # Mock __import__ to raise ImportError for jsonschema
        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if name == "jsonschema":
                raise ImportError("Mock: jsonschema not available")
            return original_import(name, *args, **kwargs)

        __builtins__["__import__"] = mock_import

        # This should trigger the ImportError handling at lines 81-82
        with pytest.raises(
            WorkflowValidationError, match="jsonschema library required"
        ):
            validate_workflow(
                {"name": "test", "version": "1.0", "actions": []}
            )

    finally:
        # Restore original state
        __builtins__["__import__"] = original_import
        sys.modules.clear()
        sys.modules.update(original_modules)
