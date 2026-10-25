"""Functional tests for schema file operations - filesystem access."""

from pathlib import Path

import pytest

# Import test_action to register it for schema tests
import test_action  # noqa: F401

from causaliq_workflow.schema import (
    WorkflowValidationError,
    load_schema,
    load_workflow_file,
)

# Test data directory path
TEST_DATA_DIR = Path(__file__).parent.parent / "data" / "functional" / "schema"


# Test loading the default CausalIQ workflow schema
def test_load_default_schema():
    """Test loading default schema from package data."""
    schema = load_schema()
    assert schema["title"] == "CausalIQ Workflow Schema"
    # Only steps is required
    assert "steps" in schema["required"]
    assert len(schema["required"]) == 1


# Test loading schema when file does not exist
def test_schema_file_not_found():
    """Test error handling when schema file not found."""
    with pytest.raises(WorkflowValidationError) as exc_info:
        load_schema("nonexistent-file.json")
    assert "Schema file not found" in str(exc_info.value)


# Test loading schema from test data directory
def test_invalid_json_schema():
    """Test loading semantically invalid but syntactically valid schema."""
    invalid_schema_path = TEST_DATA_DIR / "invalid-schema.json"
    # Invalid schema loads fine, but would fail during validation
    schema = load_schema(str(invalid_schema_path))
    assert schema["title"] == "Invalid Test Schema"
    # The schema is syntactically valid JSON, just semantically invalid


# Test loading schema using Path object
def test_load_schema_with_path_object():
    """Test loading schema using pathlib.Path object directly."""
    schema_path = TEST_DATA_DIR / "invalid-schema.json"
    schema = load_schema(schema_path)  # Pass Path object directly
    assert schema["title"] == "Invalid Test Schema"


# Test loading malformed JSON schema file
def test_malformed_json_file():
    """Test error handling when JSON file has syntax errors."""
    malformed_json = TEST_DATA_DIR / "malformed.json"
    malformed_json.write_text('{"title": "incomplete json"')

    try:
        with pytest.raises(WorkflowValidationError) as exc_info:
            load_schema(str(malformed_json))
        assert "Invalid JSON in schema" in str(exc_info.value)
    finally:
        malformed_json.unlink()  # Clean up test file


# Test loading non-object JSON schema
def test_non_object_json_schema():
    """Test error handling when schema is not a JSON object."""
    invalid_schema = TEST_DATA_DIR / "non-object-schema.json"
    invalid_schema.write_text('["not", "an", "object"]')

    try:
        with pytest.raises(WorkflowValidationError) as exc_info:
            load_schema(str(invalid_schema))
        assert "Schema must be JSON object" in str(exc_info.value)
    finally:
        invalid_schema.unlink()  # Clean up test file


# Test loading valid workflow YAML file
def test_load_valid_workflow_file():
    """Test loading valid workflow from YAML file."""
    workflow_path = TEST_DATA_DIR / "valid-workflow.yml"
    workflow = load_workflow_file(str(workflow_path))

    assert workflow["name"] == "Valid Basic Workflow"
    assert len(workflow["steps"]) == 2
    assert workflow["steps"][0]["run"] == "echo hello"
    assert workflow["steps"][1]["uses"] == "some-action@v1"


# Test loading workflow file using Path object
def test_load_workflow_file_with_path_object():
    """Test loading workflow using pathlib.Path object directly."""
    workflow_path = TEST_DATA_DIR / "valid-workflow.yml"
    workflow = load_workflow_file(workflow_path)  # Pass Path object directly

    assert workflow["name"] == "Valid Basic Workflow"
    assert len(workflow["steps"]) == 2


# Test loading workflow when file does not exist
def test_workflow_file_not_found():
    """Test error handling when workflow file not found."""
    with pytest.raises(WorkflowValidationError) as exc_info:
        load_workflow_file("nonexistent-workflow.yml")
    assert "Workflow file not found" in str(exc_info.value)


# Test loading YAML file with syntax errors
def test_invalid_yaml_syntax():
    """Test error handling when YAML file has syntax errors."""
    # Create a file with invalid YAML for this test
    invalid_yaml = TEST_DATA_DIR / "invalid-yaml.yml"
    invalid_yaml.write_text("name: [invalid: yaml: syntax")

    try:
        with pytest.raises(WorkflowValidationError) as exc_info:
            load_workflow_file(str(invalid_yaml))
        assert "Invalid YAML syntax" in str(exc_info.value)
    finally:
        invalid_yaml.unlink()  # Clean up test file


# Test loading non-object YAML workflow
def test_non_object_yaml_workflow():
    """Test error handling when workflow is not a YAML object."""
    invalid_workflow = TEST_DATA_DIR / "non-object-workflow.yml"
    invalid_workflow.write_text("- not\n- an\n- object")

    try:
        with pytest.raises(WorkflowValidationError) as exc_info:
            load_workflow_file(str(invalid_workflow))
        assert "Workflow must be YAML object" in str(exc_info.value)
    finally:
        invalid_workflow.unlink()  # Clean up test file


# Test unquoted template tokens are reported with a quoting hint.
def test_unquoted_template_token_reports_hint():
    """An unquoted {{token}} is invalid YAML and carries a hint."""
    workflow_path = TEST_DATA_DIR / "unquoted-token.yml"
    workflow_path.write_text(
        "steps:\n"
        "  - name: Test\n"
        "    uses: some-action\n"
        "    with:\n"
        "      randomise: {{randomise}}\n",
        encoding="utf-8",
    )

    try:
        with pytest.raises(WorkflowValidationError) as exc_info:
            load_workflow_file(str(workflow_path))
        message = str(exc_info.value)
        assert "Invalid YAML syntax" in message
        assert "must be quoted" in message
    finally:
        workflow_path.unlink()


# Test the hint is omitted when no template token is involved.
def test_invalid_yaml_without_token_has_no_hint():
    """Plain YAML errors are reported without the quoting hint."""
    workflow_path = TEST_DATA_DIR / "bad-indent.yml"
    workflow_path.write_text(
        "steps:\n  - name: Test\n      uses: some-action\n",
        encoding="utf-8",
    )

    try:
        with pytest.raises(WorkflowValidationError) as exc_info:
            load_workflow_file(str(workflow_path))
        assert "must be quoted" not in str(exc_info.value)
    finally:
        workflow_path.unlink()


# Test an unrelated YAML error in a file that also uses a token.
def test_token_present_unrelated_yaml_error_has_no_hint():
    """An unrelated YAML error is not hinted as a quoting problem."""
    workflow_path = TEST_DATA_DIR / "tab-indent.yml"
    workflow_path.write_text(
        "steps:\n"
        "  - name: Test\n"
        "    with:\n"
        '      sample_size: "{{sample_size}}"\n'
        "\tuses: some-action\n",
        encoding="utf-8",
    )

    try:
        with pytest.raises(WorkflowValidationError) as exc_info:
            load_workflow_file(str(workflow_path))
        message = str(exc_info.value)
        assert "Invalid YAML syntax" in message
        assert "must be quoted" not in message
    finally:
        workflow_path.unlink()
