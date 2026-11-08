"""Unit tests for step filter expression validation."""

import pytest

from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor

# ---------------------------------------------------------------------------
# Filter expression validation tests
# ---------------------------------------------------------------------------


# Test _validate_step_filters with valid filter expression.
def test_validate_step_filters_valid_expression():
    """Test _validate_step_filters accepts valid filter syntax."""
    executor = WorkflowExecutor()
    workflow = {
        "steps": [
            {
                "name": "valid_step",
                "uses": "test_provider",
                "with": {"filter": "network == 'asia'"},
            }
        ]
    }
    errors = executor._validate_step_filters(workflow)
    assert errors == []


# Test _validate_step_filters catches missing quotes.
def test_validate_step_filters_missing_quotes():
    """Test _validate_step_filters - unquoted identifiers are valid syntax.

    Note: `network == asia` is syntactically valid Python (comparing two
    variables). The error only occurs at evaluation time when `asia` is
    undefined. Syntax validation can't catch this - it requires semantic
    analysis. However, invalid operators like `===` ARE caught.
    """
    executor = WorkflowExecutor()
    workflow = {
        "steps": [
            {
                "name": "unquoted_step",
                "uses": "test_provider",
                # This is valid Python syntax (comparing two variables)
                "with": {"filter": "network == asia"},
            }
        ]
    }
    # Parses OK - semantic error caught later at evaluation time
    errors = executor._validate_step_filters(workflow)
    assert errors == []


# Test _validate_step_filters catches syntax error.
def test_validate_step_filters_syntax_error():
    """Test _validate_step_filters catches invalid syntax."""
    executor = WorkflowExecutor()
    workflow = {
        "steps": [
            {
                "name": "syntax_error_step",
                "uses": "test_provider",
                "with": {"filter": "network =="},  # Incomplete expression
            }
        ]
    }
    errors = executor._validate_step_filters(workflow)
    assert len(errors) == 1
    assert "syntax_error_step" in errors[0]


# Test _validate_step_filters skips steps without filter.
def test_validate_step_filters_no_filter():
    """Test _validate_step_filters skips steps without filter param."""
    executor = WorkflowExecutor()
    workflow = {
        "steps": [
            {
                "name": "no_filter_step",
                "uses": "test_provider",
                "with": {"action": "some_action"},
            }
        ]
    }
    errors = executor._validate_step_filters(workflow)
    assert errors == []


# Test _validate_step_filters collects all errors.
def test_validate_step_filters_multiple_errors():
    """Test _validate_step_filters returns all errors."""
    executor = WorkflowExecutor()
    workflow = {
        "steps": [
            {
                "name": "bad_step_1",
                "uses": "test_provider",
                "with": {"filter": "x =="},  # Incomplete
            },
            {
                "name": "good_step",
                "uses": "test_provider",
                "with": {"filter": "x == 1"},  # Valid
            },
            {
                "name": "bad_step_2",
                "uses": "test_provider",
                "with": {"filter": "y ==="},  # Invalid operator
            },
        ]
    }
    errors = executor._validate_step_filters(workflow)
    assert len(errors) == 2
    assert any("bad_step_1" in e for e in errors)
    assert any("bad_step_2" in e for e in errors)


# Test _validate_step_filters catches TypeError for non-string filter.
def test_validate_step_filters_type_error():
    """Test _validate_step_filters catches non-string filter expression."""
    executor = WorkflowExecutor()
    workflow = {
        "steps": [
            {
                "name": "bad_type_step",
                "uses": "test_provider",
                "with": {"filter": 123},  # Integer instead of string
            },
        ]
    }
    errors = executor._validate_step_filters(workflow)
    assert len(errors) == 1
    assert "bad_type_step" in errors[0]
    assert "must be a string" in errors[0]


# Test _validate_workflow_actions raises error on invalid filter.
def test_validate_workflow_actions_raises_on_invalid_filter(executor):
    """Test that _validate_workflow_actions raises for invalid filter."""
    workflow = {
        "name": "test-workflow",
        "steps": [
            {
                "name": "filter_step",
                "uses": "mock_workflow_action",
                "with": {
                    "param": "value",
                    "filter": "x ==",  # Invalid syntax
                },
            },
        ],
    }
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor._validate_workflow_actions(workflow, "run")
    assert "Filter validation failed" in str(exc_info.value)
