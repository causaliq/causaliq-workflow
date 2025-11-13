"""Unit tests for WorkflowExecutor - no filesystem access."""

from unittest.mock import patch

import pytest

from causaliq_pipeline.schema import WorkflowValidationError
from causaliq_pipeline.workflow import WorkflowExecutionError, WorkflowExecutor


# Test WorkflowExecutionError exception creation
def test_workflow_execution_error():
    """Test creating WorkflowExecutionError with message."""
    error = WorkflowExecutionError("Test error")
    assert str(error) == "Test error"


# Test successful workflow parsing with mocked dependencies
@patch("causaliq_pipeline.workflow.validate_workflow")
@patch("causaliq_pipeline.workflow.load_workflow_file")
def test_parse_workflow_success(mock_load, mock_validate):
    """Test successful workflow parsing with valid YAML."""
    # Setup mocks
    workflow_data = {"name": "Test", "steps": [{"run": "echo hello"}]}
    mock_load.return_value = workflow_data
    mock_validate.return_value = True

    # Execute
    executor = WorkflowExecutor()
    result = executor.parse_workflow("/path/to/workflow.yml")

    # Verify
    assert result == workflow_data
    mock_load.assert_called_once_with("/path/to/workflow.yml")
    mock_validate.assert_called_once_with(workflow_data)


# Test workflow parsing failure with validation error
@patch("causaliq_pipeline.workflow.validate_workflow")
@patch("causaliq_pipeline.workflow.load_workflow_file")
def test_parse_workflow_validation_error(mock_load, mock_validate):
    """Test workflow parsing fails with validation error."""
    # Setup mocks
    workflow_data = {"name": "Test"}  # Missing steps
    mock_load.return_value = workflow_data
    mock_validate.side_effect = WorkflowValidationError("Missing steps field")

    # Execute and verify exception
    executor = WorkflowExecutor()
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("/path/to/workflow.yml")

    assert "Workflow validation failed" in str(exc_info.value)


# Test matrix expansion with simple variables
def test_expand_matrix_simple():
    """Test matrix expansion with simple variable combinations."""
    matrix = {
        "algorithm": ["pc", "ges"],
        "dataset": ["asia", "cancer"],
    }

    executor = WorkflowExecutor()
    jobs = executor.expand_matrix(matrix)

    # Should generate 4 combinations (2 × 2)
    expected_jobs = [
        {"algorithm": "pc", "dataset": "asia"},
        {"algorithm": "pc", "dataset": "cancer"},
        {"algorithm": "ges", "dataset": "asia"},
        {"algorithm": "ges", "dataset": "cancer"},
    ]

    assert len(jobs) == 4
    assert jobs == expected_jobs


# Test matrix expansion with empty matrix
def test_expand_matrix_empty():
    """Test matrix expansion returns empty job for empty matrix."""
    executor = WorkflowExecutor()
    jobs = executor.expand_matrix({})

    assert jobs == [{}]


# Test matrix expansion with single variable
def test_expand_matrix_single_variable():
    """Test matrix expansion with single variable."""
    matrix = {"algorithm": ["pc", "ges", "lingam"]}

    executor = WorkflowExecutor()
    jobs = executor.expand_matrix(matrix)

    expected_jobs = [
        {"algorithm": "pc"},
        {"algorithm": "ges"},
        {"algorithm": "lingam"},
    ]

    assert len(jobs) == 3
    assert jobs == expected_jobs


# Test matrix expansion exception handling
@patch("causaliq_pipeline.workflow.itertools.product")
def test_expand_matrix_exception_handling(mock_product):
    """Test matrix expansion fails gracefully with unexpected errors."""
    # Setup mock to raise exception
    mock_product.side_effect = RuntimeError("Unexpected error in itertools")

    matrix = {"algorithm": ["pc", "ges"]}

    executor = WorkflowExecutor()
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.expand_matrix(matrix)

    assert "Matrix expansion failed" in str(exc_info.value)
    assert "Unexpected error in itertools" in str(exc_info.value)


# Test matrix expansion with realistic workflow data
def test_expand_matrix_with_realistic_data():
    """Test matrix expansion with realistic multi-dimensional matrix."""
    # Setup realistic matrix data
    matrix = {
        "dataset": ["asia", "cancer", "alarm"],
        "algorithm": ["pc", "ges"],
        "alpha": [0.01, 0.05],
    }

    executor = WorkflowExecutor()
    jobs = executor.expand_matrix(matrix)

    # Should generate 12 combinations (3 × 2 × 2)
    assert len(jobs) == 12

    # Verify all combinations are present
    datasets = {job["dataset"] for job in jobs}
    algorithms = {job["algorithm"] for job in jobs}
    alphas = {job["alpha"] for job in jobs}

    assert datasets == {"asia", "cancer", "alarm"}
    assert algorithms == {"pc", "ges"}
    assert alphas == {0.01, 0.05}

    # Verify specific combination exists
    expected_job = {"dataset": "asia", "algorithm": "pc", "alpha": 0.01}
    assert expected_job in jobs


# Test matrix expansion maintains consistent ordering
def test_matrix_expansion_preserves_order():
    """Test matrix expansion produces deterministic job ordering."""
    matrix = {
        "algorithm": ["pc", "ges"],
        "dataset": ["asia", "cancer"],
    }

    executor = WorkflowExecutor()
    jobs1 = executor.expand_matrix(matrix)
    jobs2 = executor.expand_matrix(matrix)

    # Multiple expansions should produce identical results
    assert jobs1 == jobs2

    # First job should be first combination of first variable
    assert jobs1[0] == {"algorithm": "pc", "dataset": "asia"}
