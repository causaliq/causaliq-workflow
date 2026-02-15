"""
Unit tests for test action.

Tests the action logic without filesystem operations.
All external dependencies are mocked.
"""

import pytest
from causaliq_core import ActionExecutionError
from test_action import ActionProvider as TestAction


class MockPath:
    """Mock Path class for testing."""

    def __init__(self, path_str):
        self.path_str = path_str
        self._exists = True
        self._mkdir_should_fail = False
        self._write_text_should_fail = False

    def exists(self):
        return self._exists

    def mkdir(self, parents=True, exist_ok=True):
        if self._mkdir_should_fail:
            raise OSError("Permission denied")

    def write_text(self, content, encoding=None):
        if self._write_text_should_fail:
            raise OSError("Write failed")

    def __str__(self):
        return self.path_str

    def __truediv__(self, other):
        result = MockPath(f"{self.path_str}/{other}")
        result._exists = False  # Default for new files
        return result


# Test action metadata attributes are correctly defined
def test_action_metadata():
    """Test action metadata attributes are correctly defined."""
    action = TestAction()

    assert action.name == "test-action"
    assert action.version == "1.0.0"
    assert (
        action.description == "Test action that creates a simple output file"
    )
    assert action.author == "CausalIQ"


# Test action input specifications are correctly defined
def test_input_specifications():
    """Test action input specifications are correctly defined."""
    action = TestAction()

    required_inputs = {"data_path", "output_dir", "message"}
    assert set(action.inputs.keys()) == required_inputs

    # Check required inputs
    assert action.inputs["data_path"].required is True
    assert action.inputs["output_dir"].required is True
    assert action.inputs["message"].required is False


# Test action output specifications are correctly defined
def test_output_specifications():
    """Test action output specifications are correctly defined."""
    action = TestAction()

    expected_outputs = {"output_file", "message_count", "status"}
    assert set(action.outputs.keys()) == expected_outputs


# Test successful action execution with valid inputs
def test_run_with_valid_inputs(monkeypatch):
    """Test successful action execution with valid inputs."""
    # Setup mock Path instances
    mock_data_path = MockPath("/data/test.csv")
    mock_data_path._exists = True

    mock_output_dir = MockPath("/output/test")
    mock_graph_path = MockPath("/output/test/graph.xml")
    mock_graph_path._exists = False  # File doesn't exist, so write

    # Track Path creation calls
    path_calls = []

    def mock_path_constructor(path_str):
        path_calls.append(path_str)
        if path_str == "/data/test.csv":
            return mock_data_path
        elif path_str == "/output/test":
            return mock_output_dir
        else:
            return MockPath(path_str)

    # Monkeypatch the Path constructor
    import test_action

    monkeypatch.setattr(test_action, "Path", mock_path_constructor)

    # Execute action
    action = TestAction()
    parameters = {
        "data_path": "/data/test.csv",
        "output_dir": "/output/test",
        "message": "Test message",
    }

    status, metadata, objects = action.run("", parameters, mode="run")

    # Verify Path calls
    assert "/data/test.csv" in path_calls
    assert "/output/test" in path_calls

    # Verify outputs
    assert metadata["message_count"] == 12  # "Test message" has 12 characters
    assert status == "success"
    assert "output_file" in metadata


# Test action execution fails with missing data file
def test_run_with_missing_data_file(monkeypatch):
    """Test action execution fails with missing data file."""
    # Setup mock Path that doesn't exist
    mock_data_path = MockPath("/missing/data.csv")
    mock_data_path._exists = False

    def mock_path_constructor(path_str):
        if path_str == "/missing/data.csv":
            return mock_data_path
        return MockPath(path_str)

    # Monkeypatch the Path constructor
    import test_action

    monkeypatch.setattr(test_action, "Path", mock_path_constructor)

    # Execute action
    action = TestAction()
    parameters = {
        "data_path": "/missing/data.csv",
        "output_dir": "/output/test",
        "dataset": "asia",
        "algorithm": "pc",
    }

    with pytest.raises(
        ActionExecutionError, match="Input data file not found"
    ):
        action.run("", parameters, mode="run")


# Test action execution handles filesystem errors gracefully
def test_run_with_filesystem_error(monkeypatch):
    """Test action execution handles filesystem errors gracefully."""
    # Setup mocks
    mock_data_path = MockPath("/data/test.csv")
    mock_data_path._exists = True

    mock_output_dir = MockPath("/readonly/output")
    mock_output_dir._mkdir_should_fail = True  # Simulate permission denied

    def mock_path_constructor(path_str):
        if path_str == "/data/test.csv":
            return mock_data_path
        elif path_str == "/readonly/output":
            return mock_output_dir
        return MockPath(path_str)

    # Monkeypatch the Path constructor
    import test_action

    monkeypatch.setattr(test_action, "Path", mock_path_constructor)

    # Execute action
    action = TestAction()
    parameters = {
        "data_path": "/data/test.csv",
        "output_dir": "/readonly/output",
        "dataset": "asia",
        "algorithm": "pc",
    }

    with pytest.raises(
        ActionExecutionError, match="Test action execution failed"
    ):
        action.run("", parameters, mode="run")
