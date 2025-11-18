"""
Test workflow variables functionality - start with basic defaults testing.
"""

import pytest

from causaliq_workflow.workflow import WorkflowExecutor


@pytest.fixture
def executor():
    """Create a workflow executor for testing."""
    return WorkflowExecutor()


def test_workflow_variables_in_template_validation(executor):
    """Test that workflow variables are included in template validation."""
    workflow = {
        "id": "test-workflow",
        "description": "Test workflow",
        "custom_var": "custom_value",
        "steps": [
            {
                "name": "Test Step",
                "uses": "dummy_action",
                "with": {
                    "output": "/results/{{custom_var}}/{{id}}.xml",
                },
            }
        ],
    }

    # Should NOT raise an error since custom_var exists as workflow variable
    try:
        executor._validate_template_variables(workflow)
    except Exception as e:
        pytest.fail(f"Template validation should pass but failed: {e}")


def test_workflow_variables_unknown_template_validation(executor):
    """Test unknown workflow variables cause template validation errors."""
    workflow = {
        "id": "test-workflow",
        "description": "Test workflow",
        "custom_var": "custom_value",
        "steps": [
            {
                "name": "Test Step",
                "uses": "dummy_action",
                "with": {
                    "output": "/results/{{unknown_var}}/{{id}}.xml",
                },
            }
        ],
    }

    # Should raise error for unknown_var
    with pytest.raises(Exception) as exc_info:
        executor._validate_template_variables(workflow)

    error_msg = str(exc_info.value)
    assert "unknown_var" in error_msg


def test_validate_required_variables_none_values(executor):
    """Test _validate_required_variables method with None values."""
    workflow = {
        "id": "test-workflow",
        "description": "Test workflow",
        "required_var": None,  # Required variable
        "optional_var": "default_value",  # Optional variable
        "steps": [],
    }

    # Should fail without CLI params
    with pytest.raises(Exception) as exc_info:
        executor._validate_required_variables(workflow, {})

    error_msg = str(exc_info.value)
    assert "required_var" in error_msg
    assert "Required workflow variables not provided" in error_msg


def test_validate_required_variables_with_cli_params(executor):
    """Test _validate_required_variables passes when CLI params provided."""
    workflow = {
        "id": "test-workflow",
        "description": "Test workflow",
        "required_var": None,  # Required variable
        "steps": [],
    }

    cli_params = {"required_var": "provided_value"}

    # Should NOT raise error
    try:
        executor._validate_required_variables(workflow, cli_params)
    except Exception as e:
        pytest.fail(f"Validation should pass when CLI params provided: {e}")
