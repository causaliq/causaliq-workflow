"""
Unit tests for dummy structure learning action.

Tests the action logic without filesystem operations.
All external dependencies are mocked.
"""

from unittest.mock import Mock, patch

import pytest

from causaliq_pipeline.action import ActionExecutionError
from causaliq_pipeline.actions import DummyStructureLearnerAction


# Test action metadata attributes are correctly defined
def test_action_metadata():
    """Test action metadata attributes are correctly defined."""
    action = DummyStructureLearnerAction()

    assert action.name == "dummy-structure-learner"
    assert action.version == "1.0.0"
    assert (
        action.description
        == "Dummy action that creates an empty graph file for testing"
    )
    assert action.author == "CausalIQ"


# Test action input specifications are correctly defined
def test_input_specifications():
    """Test action input specifications are correctly defined."""
    action = DummyStructureLearnerAction()

    required_inputs = {"data_path", "output_dir", "dataset", "algorithm"}
    assert set(action.inputs.keys()) == required_inputs

    # Check required inputs
    assert action.inputs["data_path"].required is True
    assert action.inputs["output_dir"].required is True
    assert action.inputs["dataset"].required is True
    assert action.inputs["algorithm"].required is True


# Test action output specifications are correctly defined
def test_output_specifications():
    """Test action output specifications are correctly defined."""
    action = DummyStructureLearnerAction()

    expected_outputs = {"graph_path", "node_count", "edge_count"}
    assert set(action.outputs.keys()) == expected_outputs


# Test successful action execution with valid inputs
@patch("causaliq_pipeline.actions.dummy_structure_learner.Path")
def test_run_with_valid_inputs(mock_path):
    """Test successful action execution with valid inputs."""
    # Setup mocks
    mock_data_path = Mock()
    mock_data_path.exists.return_value = True

    mock_output_dir = Mock()
    mock_graph_path = Mock()
    mock_output_dir.__truediv__ = Mock(return_value=mock_graph_path)

    mock_path.side_effect = [mock_data_path, mock_output_dir]

    # Execute action
    action = DummyStructureLearnerAction()
    inputs = {
        "data_path": "/data/test.csv",
        "output_dir": "/output/test",
        "dataset": "asia",
        "algorithm": "pc",
    }

    result = action.run(inputs)

    # Verify filesystem operations
    mock_data_path.exists.assert_called_once()
    mock_output_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_graph_path.write_text.assert_called_once()

    # Verify outputs
    assert result["node_count"] == 0
    assert result["edge_count"] == 0
    assert "graph_path" in result


# Test action execution fails with missing data file
@patch("causaliq_pipeline.actions.dummy_structure_learner.Path")
def test_run_with_missing_data_file(mock_path):
    """Test action execution fails with missing data file."""
    # Setup mocks
    mock_data_path = Mock()
    mock_data_path.exists.return_value = False
    mock_data_path.__str__ = Mock(return_value="/missing/data.csv")

    mock_path.return_value = mock_data_path

    # Execute action
    action = DummyStructureLearnerAction()
    inputs = {
        "data_path": "/missing/data.csv",
        "output_dir": "/output/test",
        "dataset": "asia",
        "algorithm": "pc",
    }

    with pytest.raises(
        ActionExecutionError, match="Input data file not found"
    ):
        action.run(inputs)


# Test action execution handles filesystem errors gracefully
@patch("causaliq_pipeline.actions.dummy_structure_learner.Path")
def test_run_with_filesystem_error(mock_path):
    """Test action execution handles filesystem errors gracefully."""
    # Setup mocks
    mock_data_path = Mock()
    mock_data_path.exists.return_value = True

    mock_output_dir = Mock()
    mock_output_dir.mkdir.side_effect = OSError("Permission denied")

    mock_path.side_effect = [mock_data_path, mock_output_dir]

    # Execute action
    action = DummyStructureLearnerAction()
    inputs = {
        "data_path": "/data/test.csv",
        "output_dir": "/readonly/output",
        "dataset": "asia",
        "algorithm": "pc",
    }

    with pytest.raises(
        ActionExecutionError, match="Dummy structure learning failed"
    ):
        action.run(inputs)


# Test default validate_inputs method returns True
def test_validate_inputs_default_implementation():
    """Test default validate_inputs method returns True."""
    action = DummyStructureLearnerAction()
    inputs = {
        "data_path": "/test/path.csv",
        "output_dir": "/test/output",
        "dataset": "test",
        "algorithm": "test",
    }

    result = action.validate_inputs(inputs)

    assert result is True
