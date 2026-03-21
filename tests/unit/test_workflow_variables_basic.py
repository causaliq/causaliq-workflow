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


# =============================================================================
# Matrix variable usage validation tests
# =============================================================================


# Test unused matrix variables raise validation error.
def test_unused_matrix_variable_raises_error(executor, monkeypatch):
    """Test that unused matrix variables cause validation error."""
    from causaliq_core import ActionPattern

    def mock_get_action_pattern(provider_name, action_name):
        return ActionPattern.CREATE

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    workflow = {
        "matrix": {
            "network": ["asia", "alarm"],
            "seed": [1, 2, 3],  # Not used in any step
        },
        "steps": [
            {
                "name": "Test Step",
                "uses": "test-provider",
                "with": {
                    "action": "create_action",
                    "network": "{{network}}",  # Only network used
                    "output": "results.db",
                },
            }
        ],
    }

    with pytest.raises(Exception) as exc_info:
        executor._validate_template_variables(workflow)

    error_msg = str(exc_info.value)
    assert "seed" in error_msg
    assert "Matrix variables not used" in error_msg


# Test all matrix variables used passes validation.
def test_all_matrix_variables_used_passes(executor, monkeypatch):
    """Test validation passes when all matrix variables are used."""
    from causaliq_core import ActionPattern

    def mock_get_action_pattern(provider_name, action_name):
        return ActionPattern.CREATE

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    workflow = {
        "matrix": {
            "network": ["asia", "alarm"],
            "seed": [1, 2],
        },
        "steps": [
            {
                "name": "Test Step",
                "uses": "test-provider",
                "with": {
                    "action": "create_action",
                    "network": "{{network}}",
                    "seed": "{{seed}}",
                    "output": "results.db",
                },
            }
        ],
    }

    # Should not raise
    try:
        executor._validate_template_variables(workflow)
    except Exception as e:
        pytest.fail(f"Validation should pass: {e}")


# Test matrix variables used across multiple steps passes validation.
def test_matrix_variables_used_across_steps(executor, monkeypatch):
    """Test that matrix variables can be used across different steps."""
    from causaliq_core import ActionPattern

    def mock_get_action_pattern(provider_name, action_name):
        return ActionPattern.CREATE

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    workflow = {
        "matrix": {
            "network": ["asia"],
            "seed": [1],
            "algorithm": ["pc"],
        },
        "steps": [
            {
                "name": "Step 1",
                "uses": "test-provider",
                "with": {
                    "action": "create_action",
                    "network": "{{network}}",
                    "output": "step1.db",
                },
            },
            {
                "name": "Step 2",
                "uses": "test-provider",
                "with": {
                    "action": "create_action",
                    "seed": "{{seed}}",
                    "algorithm": "{{algorithm}}",
                    "output": "step2.db",
                },
            },
        ],
    }

    # Should not raise - all matrix vars used across steps
    try:
        executor._validate_template_variables(workflow)
    except Exception as e:
        pytest.fail(f"Validation should pass: {e}")


# Test AGGREGATE steps don't require matrix variable usage.
def test_aggregate_step_skips_matrix_usage_check(executor, monkeypatch):
    """Test AGGREGATE pattern steps don't need to use matrix variables.

    AGGREGATE steps use matrix for grouping entries, not for templating.
    """
    from causaliq_core import ActionPattern

    def mock_get_action_pattern(provider_name, action_name):
        if action_name == "merge_graphs":
            return ActionPattern.AGGREGATE
        return ActionPattern.CREATE

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    workflow = {
        "matrix": {
            "network": ["asia", "alarm"],
        },
        "steps": [
            {
                "name": "Create Step",
                "uses": "test-provider",
                "with": {
                    "action": "run_discovery",
                    "network": "{{network}}",
                    "output": "graphs.db",
                },
            },
            {
                "name": "Aggregate Step",
                "uses": "test-provider",
                "with": {
                    "action": "merge_graphs",
                    "input": "graphs.db",  # AGGREGATE step with .db input
                    "output": "merged.db",
                    # Note: {{network}} NOT used - that's OK for AGGREGATE
                },
            },
        ],
    }

    # Should pass - network is used in CREATE step
    try:
        executor._validate_template_variables(workflow)
    except Exception as e:
        pytest.fail(
            f"AGGREGATE step should not require matrix templating: {e}"
        )


# Test _is_aggregate_pattern_step detection.
def test_is_aggregate_pattern_step_true(executor, monkeypatch):
    """Test AGGREGATE pattern step is correctly detected."""
    from causaliq_core import ActionPattern

    def mock_get_action_pattern(provider_name, action_name):
        if action_name == "merge_graphs":
            return ActionPattern.AGGREGATE
        return ActionPattern.CREATE

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    workflow = {"matrix": {"network": ["asia"]}}
    step = {
        "uses": "test-provider",
        "with": {
            "action": "merge_graphs",
            "input": "cache.db",
        },
    }

    assert executor._is_aggregate_pattern_step(step, workflow) is True


# Test _is_aggregate_pattern_step returns False without .db input.
def test_is_aggregate_pattern_step_no_db_input(executor, monkeypatch):
    """Test AGGREGATE detection requires .db input."""
    from causaliq_core import ActionPattern

    def mock_get_action_pattern(provider_name, action_name):
        return ActionPattern.AGGREGATE

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    workflow = {"matrix": {"network": ["asia"]}}
    step = {
        "uses": "test-provider",
        "with": {
            "action": "merge_graphs",
            "input": "data.graphml",  # Not a .db file
        },
    }

    assert executor._is_aggregate_pattern_step(step, workflow) is False


# Test _is_aggregate_pattern_step handles registry exception.
def test_is_aggregate_pattern_step_handles_exception(executor, monkeypatch):
    """Test AGGREGATE detection handles registry errors gracefully."""

    def mock_get_action_pattern(provider_name, action_name):
        raise RuntimeError("Registry failure")

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    workflow = {"matrix": {"network": ["asia"]}}
    step = {
        "uses": "test-provider",
        "with": {
            "action": "merge_graphs",
            "input": "cache.db",
        },
    }

    # Should return False (not raise)
    assert executor._is_aggregate_pattern_step(step, workflow) is False


# Test _is_aggregate_pattern_step with invalid input type.
def test_is_aggregate_pattern_step_invalid_input_type(executor, monkeypatch):
    """Test AGGREGATE detection handles non-string/list input types."""
    from causaliq_core import ActionPattern

    def mock_get_action_pattern(provider_name, action_name):
        return ActionPattern.AGGREGATE

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    workflow = {"matrix": {"network": ["asia"]}}
    # Input is a number (neither string nor list)
    step = {
        "uses": "test-provider",
        "with": {
            "action": "merge_graphs",
            "input": 12345,
        },
    }

    # Should return False due to no valid .db input
    assert executor._is_aggregate_pattern_step(step, workflow) is False


# Test _is_aggregate_pattern_step with missing provider.
def test_is_aggregate_pattern_step_missing_provider(executor):
    """Test AGGREGATE detection returns False when provider is missing."""
    workflow = {"matrix": {"network": ["asia"]}}
    step = {
        # "uses" is missing
        "with": {
            "action": "merge_graphs",
            "input": "cache.db",
        },
    }

    assert executor._is_aggregate_pattern_step(step, workflow) is False


# Test _is_aggregate_pattern_step with missing action.
def test_is_aggregate_pattern_step_missing_action(executor):
    """Test AGGREGATE detection returns False when action is missing."""
    workflow = {"matrix": {"network": ["asia"]}}
    step = {
        "uses": "test-provider",
        "with": {
            # "action" is missing
            "input": "cache.db",
        },
    }

    assert executor._is_aggregate_pattern_step(step, workflow) is False


# Test _get_step_action_pattern with missing provider.
def test_get_step_action_pattern_missing_provider(executor):
    """Test _get_step_action_pattern returns None when provider missing."""
    step = {
        # "uses" is missing
        "with": {
            "action": "some_action",
        },
    }

    assert executor._get_step_action_pattern(step) is None


# Test _get_step_action_pattern with missing action.
def test_get_step_action_pattern_missing_action(executor):
    """Test _get_step_action_pattern returns None when action missing."""
    step = {
        "uses": "test-provider",
        "with": {
            # "action" is missing
        },
    }

    assert executor._get_step_action_pattern(step) is None


# Test _get_step_action_pattern handles registry exception.
def test_get_step_action_pattern_handles_exception(executor, monkeypatch):
    """Test _get_step_action_pattern returns None on registry exception."""

    def mock_get_action_pattern(provider_name, action_name):
        raise RuntimeError("Registry failure")

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    step = {
        "uses": "test-provider",
        "with": {
            "action": "some_action",
        },
    }

    # Should return None (not raise)
    assert executor._get_step_action_pattern(step) is None


# Test _is_aggregate_pattern_step with list input type.
def test_is_aggregate_pattern_step_list_input(executor, monkeypatch):
    """Test AGGREGATE detection with input as a list of files."""
    from causaliq_core import ActionPattern

    def mock_get_action_pattern(provider_name, action_name):
        return ActionPattern.AGGREGATE

    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        mock_get_action_pattern,
    )

    workflow = {"matrix": {"network": ["asia"]}}
    step = {
        "uses": "test-provider",
        "with": {
            "action": "merge_graphs",
            "input": ["cache1.db", "cache2.db"],  # List of .db files
        },
    }

    assert executor._is_aggregate_pattern_step(step, workflow) is True
