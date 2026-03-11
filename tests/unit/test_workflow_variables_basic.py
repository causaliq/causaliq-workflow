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


# Test UPDATE pattern steps allow deferred template variable resolution.
def test_update_pattern_allows_deferred_template_variables(
    executor, monkeypatch
):
    """Test UPDATE pattern steps allow variables resolved from entry metadata.

    UPDATE steps process cache entries one at a time, resolving template
    variables from each entry's metadata. This test verifies that unknown
    template variables (like {{network}}) are allowed for UPDATE steps.
    """
    from causaliq_core import ActionPattern

    # Mock the registry to return UPDATE pattern for test action
    def mock_get_action_pattern(provider_name, action_name):
        if provider_name == "test-provider" and action_name == "update_action":
            return ActionPattern.UPDATE
        return None

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    # Workflow with UPDATE step using metadata variable {{network}}
    workflow = {
        "id": "test-workflow",
        "description": "Test UPDATE pattern",
        # No matrix - UPDATE pattern prohibits matrix
        "steps": [
            {
                "name": "Update Step",
                "uses": "test-provider",
                "with": {
                    "action": "update_action",
                    "input": "results/graphs.db",
                    # {{network}} will be resolved from entry metadata
                    "reference": "networks/{{network}}/true.graphml",
                },
            }
        ],
    }

    # Should NOT raise error - {{network}} is allowed for UPDATE steps
    try:
        executor._validate_template_variables(workflow)
    except Exception as e:
        pytest.fail(
            f"UPDATE step should allow deferred template variables: {e}"
        )


# Test non-UPDATE patterns still reject unknown template variables.
def test_non_update_pattern_rejects_unknown_template_variables(
    executor, monkeypatch
):
    """Test that non-UPDATE steps still reject unknown template variables."""
    from causaliq_core import ActionPattern

    # Mock the registry to return CREATE pattern for test action
    def mock_get_action_pattern(provider_name, action_name):
        if provider_name == "test-provider" and action_name == "create_action":
            return ActionPattern.CREATE
        return None

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    # CREATE pattern workflow with unknown variable
    workflow = {
        "id": "test-workflow",
        "description": "Test CREATE pattern",
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "Create Step",
                "uses": "test-provider",
                "with": {
                    "action": "create_action",
                    "output": "results/{{network}}/{{unknown_var}}.graphml",
                },
            }
        ],
    }

    # Should raise error for unknown_var
    with pytest.raises(Exception) as exc_info:
        executor._validate_template_variables(workflow)

    error_msg = str(exc_info.value)
    assert "unknown_var" in error_msg


# Test _is_update_pattern_step handles registry exceptions gracefully.
def test_is_update_pattern_step_handles_registry_exception(
    executor, monkeypatch
):
    """Test that registry exceptions return False instead of propagating."""

    def mock_get_action_pattern(provider_name, action_name):
        raise RuntimeError("Registry failure")

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    workflow = {"steps": []}  # No matrix
    step = {
        "uses": "test-provider",
        "with": {"action": "test_action"},
    }

    # Should return False (not raise) when registry fails
    result = executor._is_update_pattern_step(step, workflow)
    assert result is False


# Test _collect_template_variables handles list values.
def test_collect_template_variables_from_list(executor):
    """Test template variable collection from list values in workflow."""
    used_vars: set = set()

    # Workflow with list containing template variables
    obj = {
        "metrics": ["{{metric1}}", "{{metric2}}", "plain_value"],
        "nested": [{"path": "{{nested_var}}"}],
    }

    executor._collect_template_variables(obj, used_vars)

    assert "metric1" in used_vars
    assert "metric2" in used_vars
    assert "nested_var" in used_vars
    assert len(used_vars) == 3
