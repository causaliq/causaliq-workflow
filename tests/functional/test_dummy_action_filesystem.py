"""
Functional tests for dummy structure learning action.

Tests action execution with real filesystem operations.
Uses tracked test data files and manages temporary outputs.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from causaliq_pipeline.action import ActionExecutionError
from causaliq_pipeline.actions import DummyStructureLearnerAction


# Test action creates valid GraphML file with real filesystem
def test_run_creates_valid_graphml_file():
    """Test action creates valid GraphML file with real filesystem."""
    # Get test data directory
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "dummy_action"
    )
    test_csv = test_data_dir / "test_data.csv"

    # Create output directory for this test
    output_dir = test_data_dir / "output" / "test_valid_graphml"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Execute action
        action = DummyStructureLearnerAction()
        inputs = {
            "data_path": str(test_csv),
            "output_dir": str(output_dir),
            "dataset": "test_dataset",
            "algorithm": "dummy",
        }

        result = action.run(inputs)

        # Verify output file exists
        expected_path = output_dir / "learned_graph.graphml"
        assert expected_path.exists()
        assert result["graph_path"] == str(expected_path)

        # Verify GraphML structure is valid XML
        tree = ET.parse(expected_path)
        root = tree.getroot()
        assert root.tag.endswith("graphml")

        # Find graph element
        graph_elem = root.find(
            ".//{http://graphml.graphdrawing.org/xmlns}graph"
        )
        assert graph_elem is not None
        assert graph_elem.get("id") == "dummy_graph"
    finally:
        # Clean up output directory
        if output_dir.exists():
            for file in output_dir.rglob("*"):
                if file.is_file():
                    file.unlink()
            for dir_path in sorted(output_dir.rglob("*"), reverse=True):
                if dir_path.is_dir():
                    dir_path.rmdir()


# Test action creates nested output directory structure
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
        action = DummyStructureLearnerAction()
        inputs = {
            "data_path": str(test_csv),
            "output_dir": str(output_dir),
            "dataset": "test",
            "algorithm": "pc",
        }

        result = action.run(inputs)

        # Verify directory structure created
        assert output_dir.exists()
        assert output_dir.is_dir()

        # Verify GraphML file created in correct location
        graph_file = output_dir / "learned_graph.graphml"
        assert graph_file.exists()
        assert result["graph_path"] == str(graph_file)
    finally:
        # Clean up output directory
        base_output = test_data_dir / "output" / "test_nested"
        if base_output.exists():
            for file in base_output.rglob("*"):
                if file.is_file():
                    file.unlink()
            for dir_path in sorted(base_output.rglob("*"), reverse=True):
                if dir_path.is_dir():
                    dir_path.rmdir()


# Test action execution preserves matrix variable information
def test_run_with_matrix_variables():
    """Test action execution preserves matrix variable information."""
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "dummy_action"
    )
    test_csv = test_data_dir / "asia.csv"
    output_dir = test_data_dir / "output" / "test_matrix_vars"

    try:
        # Execute action with matrix variables
        action = DummyStructureLearnerAction()
        inputs = {
            "data_path": str(test_csv),
            "output_dir": str(output_dir),
            "dataset": "asia",
            "algorithm": "pc",
        }

        result = action.run(inputs)

        # Verify outputs include expected values
        assert result["node_count"] == 0
        assert result["edge_count"] == 0
        assert "graph_path" in result

        # Verify file was created
        assert Path(result["graph_path"]).exists()
    finally:
        # Clean up output directory
        if output_dir.exists():
            for file in output_dir.rglob("*"):
                if file.is_file():
                    file.unlink()
            for dir_path in sorted(output_dir.rglob("*"), reverse=True):
                if dir_path.is_dir():
                    dir_path.rmdir()


# Test action fails gracefully with missing data file
def test_run_with_nonexistent_data_file():
    """Test action fails gracefully with missing data file."""
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "dummy_action"
    )

    # Don't create the data file
    missing_file = test_data_dir / "missing.csv"
    output_dir = test_data_dir / "output" / "test_missing_data"

    try:
        action = DummyStructureLearnerAction()
        inputs = {
            "data_path": str(missing_file),
            "output_dir": str(output_dir),
            "dataset": "missing",
            "algorithm": "pc",
        }

        with pytest.raises(ActionExecutionError) as exc_info:
            action.run(inputs)

        assert "Input data file not found" in str(exc_info.value)
        assert str(missing_file) in str(exc_info.value)
    finally:
        # Clean up output directory
        if output_dir.exists():
            for file in output_dir.rglob("*"):
                if file.is_file():
                    file.unlink()
            for dir_path in sorted(output_dir.rglob("*"), reverse=True):
                if dir_path.is_dir():
                    dir_path.rmdir()


# Test generated GraphML file has correct content structure
def test_graphml_content_structure():
    """Test generated GraphML file has correct content structure."""
    test_data_dir = (
        Path(__file__).parent.parent / "data" / "functional" / "dummy_action"
    )
    test_csv = test_data_dir / "test_data.csv"
    output_dir = test_data_dir / "output" / "test_graphml_content"

    try:
        # Execute action
        action = DummyStructureLearnerAction()
        inputs = {
            "data_path": str(test_csv),
            "output_dir": str(output_dir),
            "dataset": "sample",
            "algorithm": "ges",
        }

        result = action.run(inputs)

        # Read and verify GraphML content
        graph_path = Path(result["graph_path"])
        content = graph_path.read_text(encoding="utf-8")

        # Check XML declaration and namespace
        assert content.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        assert 'xmlns="http://graphml.graphdrawing.org/xmlns"' in content

        # Check graph structure
        assert 'id="dummy_graph"' in content
        assert 'edgedefault="directed"' in content
        assert "Empty graph - no nodes or edges" in content
    finally:
        # Clean up output directory
        if output_dir.exists():
            for file in output_dir.rglob("*"):
                if file.is_file():
                    file.unlink()
            for dir_path in sorted(output_dir.rglob("*"), reverse=True):
                if dir_path.is_dir():
                    dir_path.rmdir()
