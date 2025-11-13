"""
Functional tests for WorkflowExecutor.

Tests workflow parsing with real filesystem operations using tracked test data.
"""

from pathlib import Path

import pytest

from causaliq_pipeline.workflow import WorkflowExecutionError, WorkflowExecutor


# Test parsing workflow from real YAML file
def test_parse_workflow_with_real_file():
    """Test parsing workflow from tracked test data file."""
    # Get test data directory
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "workflow"
    )
    workflow_path = test_data_dir / "valid_workflow.yml"

    # Parse workflow using tracked test data
    executor = WorkflowExecutor()
    workflow = executor.parse_workflow(str(workflow_path))

    # Verify parsed content
    assert workflow["id"] == "test-001"
    assert (
        workflow["description"]
        == "Test workflow with matrix variables and flexible action parameters"
    )
    # Verify flexible action parameters
    assert len(workflow["steps"]) == 1
    step = workflow["steps"][0]
    assert step["name"] == "Structure Learning"
    assert step["with"]["dataset"] == "/experiments/data/{{dataset}}.csv"
    assert (
        step["with"]["result"]
        == "/experiments/results/{{id}}/{{algorithm}}/graph_{{dataset}}.xml"
    )


# Test parsing fails gracefully with invalid workflow file
def test_parse_workflow_with_invalid_file():
    """Test parsing fails gracefully with invalid tracked test data."""
    # Get test data directory
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "workflow"
    )
    workflow_path = test_data_dir / "invalid_workflow.yml"

    # Attempt to parse invalid workflow
    executor = WorkflowExecutor()
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow(str(workflow_path))

    assert "Workflow validation failed" in str(exc_info.value)


# Test parsing workflow with complex matrix configuration
def test_parse_workflow_with_matrix_file():
    """Test parsing complex matrix workflow from tracked test data."""
    # Get test data directory
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "workflow"
    )
    workflow_path = test_data_dir / "matrix_workflow.yml"

    # Parse workflow with matrix
    executor = WorkflowExecutor()
    workflow = executor.parse_workflow(str(workflow_path))

    # Verify matrix configuration
    assert workflow["id"] == "matrix-test-001"
    assert (
        workflow["description"]
        == "Matrix workflow testing algorithm and dataset combinations"
    )
    assert "matrix" in workflow

    matrix = workflow["matrix"]
    assert set(matrix["dataset"]) == {"asia", "cancer", "alarm"}
    assert set(matrix["algorithm"]) == {"pc", "ges"}
    assert set(matrix["alpha"]) == {0.01, 0.05}

    # Verify step configuration with flexible parameters
    assert len(workflow["steps"]) == 1
    step = workflow["steps"][0]
    assert step["name"] == "Causal Discovery"
    assert step["uses"] == "dummy-structure-learner"
    assert step["with"]["dataset"] == "/experiments/data/{{dataset}}.csv"
    expected_result = (
        "/experiments/results/{{id}}/{{algorithm}}/"
        "graph_{{dataset}}_{{alpha}}.xml"
    )
    assert step["with"]["result"] == expected_result
    assert step["with"]["alpha"] == "{{alpha}}"


# Test parsing workflow with Path object input
def test_parse_workflow_with_pathlib_path():
    """Test parsing workflow using pathlib.Path object directly."""
    # Get test data directory
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "workflow"
    )
    workflow_path = test_data_dir / "valid_workflow.yml"

    # Parse workflow using Path object (not string)
    executor = WorkflowExecutor()
    workflow = executor.parse_workflow(workflow_path)  # Pass Path directly

    # Verify parsing works with Path objects
    assert workflow["id"] == "test-001"
    assert (
        workflow["description"]
        == "Test workflow with matrix variables and flexible action parameters"
    )


# Test parsing nonexistent workflow file
def test_parse_workflow_file_not_found():
    """Test error handling when workflow file does not exist."""
    # Use nonexistent file path
    nonexistent_path = "nonexistent_workflow.yml"

    executor = WorkflowExecutor()
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow(nonexistent_path)

    assert "Workflow validation failed" in str(exc_info.value)
    # The underlying error should be about file not found
    assert "not found" in str(exc_info.value).lower()
