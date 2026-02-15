"""
Functional tests for test action.

Tests action execution with real filesystem operations.
Uses tracked test data files and manages temporary outputs.
"""

from pathlib import Path

import pytest

# Import test_action to register it for testing
import test_action  # noqa: F401
from causaliq_core import ActionExecutionError
from test_action import ActionProvider as TestAction


def test_run_creates_valid_output_file():
    """Test action creates valid output file with real filesystem."""
    # Get test data directory
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "dummy_action"
    )
    test_csv = test_data_dir / "test_data.csv"

    # Create output directory for this test
    output_dir = test_data_dir / "output" / "test_valid_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Execute action
        action = TestAction()
        parameters = {
            "data_path": str(test_csv),
            "output_dir": str(output_dir),
            "message": "Test execution",
        }

        result = action.run("", parameters, mode="run")

        # Unpack tuple result
        status, metadata, objects = result

        # Verify output file exists
        expected_path = output_dir / "test_output.txt"
        assert expected_path.exists()

        # Verify result structure
        assert "output_file" in metadata
        assert "message_count" in metadata
        assert status == "success"
        assert metadata["message_count"] > 0

        # Verify file content
        content = expected_path.read_text()
        assert "Test Action Output" in content
        assert "Test execution" in content

    finally:
        # Cleanup
        if (output_dir / "test_output.txt").exists():
            (output_dir / "test_output.txt").unlink()


def test_run_creates_output_directory_structure():
    """Test action creates nested output directory structure."""
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "dummy_action"
    )
    test_csv = test_data_dir / "test_data.csv"

    # Setup nested output path
    output_dir = test_data_dir / "output" / "test_nested" / "structure"

    try:
        # Execute action
        action = TestAction()
        parameters = {
            "data_path": str(test_csv),
            "output_dir": str(output_dir),
            "message": "Nested test",
        }

        result = action.run("", parameters, mode="run")

        # Unpack tuple result
        status, metadata, objects = result

        # Verify directory structure created
        assert output_dir.exists()
        output_file = output_dir / "test_output.txt"
        assert output_file.exists()

        # Verify result
        assert status == "success"

    finally:
        # Cleanup
        output_file = output_dir / "test_output.txt"
        if output_file.exists():
            output_file.unlink()


def test_run_with_custom_message():
    """Test action execution with custom message."""
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "dummy_action"
    )
    test_csv = test_data_dir / "asia.csv"
    output_dir = test_data_dir / "output" / "test_custom_message"

    try:
        # Execute action with custom message
        action = TestAction()
        custom_message = "This is a custom test message!"
        parameters = {
            "data_path": str(test_csv),
            "output_dir": str(output_dir),
            "message": custom_message,
        }

        result = action.run("", parameters, mode="run")

        # Unpack tuple result
        status, metadata, objects = result

        # Verify outputs include expected values
        assert metadata["message_count"] == len(custom_message)
        assert status == "success"

        # Verify file content includes custom message
        output_file = Path(metadata["output_file"])
        content = output_file.read_text()
        assert custom_message in content

    finally:
        # Cleanup
        output_file = output_dir / "test_output.txt"
        if output_file.exists():
            output_file.unlink()


def test_run_with_nonexistent_data_file():
    """Test action fails gracefully with missing data file."""
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "dummy_action"
    )

    # Don't create the data file
    missing_file = test_data_dir / "missing.csv"
    output_dir = test_data_dir / "output" / "test_missing_data"

    try:
        action = TestAction()
        parameters = {
            "data_path": str(missing_file),
            "output_dir": str(output_dir),
            "message": "Should fail",
        }

        with pytest.raises(ActionExecutionError) as exc_info:
            action.run("", parameters, mode="run")

        # Verify error message is informative
        assert "not found" in str(exc_info.value).lower()

    finally:
        # Cleanup
        output_file = output_dir / "test_output.txt"
        if output_file and output_file.exists():
            output_file.unlink()


def test_dry_run_mode():
    """Test dry-run mode works without creating files."""
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "dummy_action"
    )
    test_csv = test_data_dir / "test_data.csv"
    output_dir = test_data_dir / "output" / "test_dry_run"

    # Execute action in dry-run mode
    action = TestAction()
    parameters = {
        "data_path": str(test_csv),
        "output_dir": str(output_dir),
        "message": "Dry run test",
    }

    result = action.run("", parameters, mode="dry-run")

    # Unpack tuple result
    status, metadata, objects = result

    # Verify dry-run results
    assert status == "skipped"
    assert metadata["message_count"] == len("Dry run test")
    assert "output_file" in metadata

    # Verify no files were actually created
    output_file = Path(metadata["output_file"])
    assert not output_file.exists()


def test_missing_required_inputs():
    """Test action fails gracefully with missing required parameters."""
    action = TestAction()

    # Test missing data_path
    with pytest.raises(ActionExecutionError) as exc_info:
        action.run("", {"output_dir": "/tmp"}, mode="dry-run")
    assert "Missing required parameter: data_path" in str(exc_info.value)

    # Test missing output_dir
    with pytest.raises(ActionExecutionError) as exc_info:
        action.run("", {"data_path": "/tmp/test.csv"}, mode="dry-run")
    assert "Missing required parameter: output_dir" in str(exc_info.value)
