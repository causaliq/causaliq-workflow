"""Unit tests for WorkflowActionProvider (echo action)."""

import json

import pytest
from causaliq_core import ActionValidationError

from causaliq_workflow.action import WorkflowActionProvider


# Test WorkflowActionProvider has correct metadata.
def test_workflow_action_provider_metadata() -> None:
    """Test provider has correct name and supported actions."""
    provider = WorkflowActionProvider()

    assert provider.name == "causaliq-workflow"
    assert provider.supported_actions == {"echo"}
    assert "action" in provider.inputs
    assert "message" in provider.inputs
    assert "nodes" in provider.inputs


# Test echo action dry-run returns skipped status.
def test_echo_dry_run_returns_skipped() -> None:
    """Test dry-run mode returns skipped status with metadata."""
    provider = WorkflowActionProvider()

    status, metadata, objects = provider.run(
        "echo",
        {"message": "Test message", "nodes": 3},
        mode="dry-run",
    )

    assert status == "skipped"
    assert metadata["message"] == "Test message"
    assert metadata["node_count"] == 3
    assert metadata["edge_count"] == 2
    assert metadata["dry_run"] is True
    assert objects == []


# Test echo action run mode creates objects.
def test_echo_run_creates_objects() -> None:
    """Test run mode creates JSON and GraphML objects."""
    provider = WorkflowActionProvider()

    status, metadata, objects = provider.run(
        "echo",
        {"message": "Hello World", "nodes": 3},
        mode="run",
    )

    assert status == "success"
    assert metadata["message"] == "Hello World"
    assert metadata["node_count"] == 3
    assert metadata["edge_count"] == 2
    assert len(objects) == 2

    # Check JSON object
    json_obj = next(o for o in objects if o["type"] == "json")
    assert json_obj["name"] == "echo_data"
    json_data = json.loads(json_obj["content"])
    assert json_data["message"] == "Hello World"
    assert json_data["nodes"] == ["A", "B", "C"]
    assert len(json_data["edges"]) == 2

    # Check GraphML object
    graphml_obj = next(o for o in objects if o["type"] == "graphml")
    assert graphml_obj["name"] == "graph"
    assert "<graphml" in graphml_obj["content"]
    assert '<node id="A"/>' in graphml_obj["content"]
    assert '<node id="B"/>' in graphml_obj["content"]
    assert '<node id="C"/>' in graphml_obj["content"]
    assert 'source="A" target="B"' in graphml_obj["content"]


# Test echo action with default parameters.
def test_echo_default_parameters() -> None:
    """Test echo action uses defaults when parameters not provided."""
    provider = WorkflowActionProvider()

    status, metadata, objects = provider.run(
        "echo",
        {},
        mode="run",
    )

    assert status == "success"
    assert metadata["message"] == "Hello from causaliq-workflow!"
    assert metadata["node_count"] == 3
    assert metadata["edge_count"] == 2


# Test echo action rejects unknown action.
def test_echo_rejects_unknown_action() -> None:
    """Test validation fails for unknown action."""
    provider = WorkflowActionProvider()

    with pytest.raises(ActionValidationError) as exc_info:
        provider.run("unknown", {}, mode="dry-run")

    assert "unknown action" in str(exc_info.value).lower()


# Test echo action validates nodes parameter.
def test_echo_validates_nodes_range() -> None:
    """Test validation fails for nodes outside valid range."""
    provider = WorkflowActionProvider()

    with pytest.raises(ActionValidationError) as exc_info:
        provider.run("echo", {"nodes": 1}, mode="dry-run")

    assert "nodes" in str(exc_info.value).lower()

    with pytest.raises(ActionValidationError) as exc_info:
        provider.run("echo", {"nodes": 11}, mode="dry-run")

    assert "nodes" in str(exc_info.value).lower()


# Test echo action validates nodes is convertible to int.
def test_echo_validates_nodes_type() -> None:
    """Test validation fails for nodes that cannot be converted to int."""
    provider = WorkflowActionProvider()

    with pytest.raises(ActionValidationError) as exc_info:
        provider.run("echo", {"nodes": "abc"}, mode="dry-run")

    assert "nodes" in str(exc_info.value).lower()

    with pytest.raises(ActionValidationError) as exc_info:
        provider.run("echo", {"nodes": None}, mode="dry-run")

    assert "nodes" in str(exc_info.value).lower()


# Test echo action creates correct graph structure.
def test_echo_graph_structure() -> None:
    """Test graph has correct chain structure A->B->C->D."""
    provider = WorkflowActionProvider()

    status, metadata, objects = provider.run(
        "echo",
        {"nodes": 4},
        mode="run",
    )

    assert metadata["node_count"] == 4
    assert metadata["edge_count"] == 3

    json_obj = next(o for o in objects if o["type"] == "json")
    json_data = json.loads(json_obj["content"])

    assert json_data["nodes"] == ["A", "B", "C", "D"]
    assert json_data["edges"] == [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "D"},
    ]
