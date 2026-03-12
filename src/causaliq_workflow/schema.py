"""
JSON Schema-based workflow validation for CausalIQ.

Uses standard JSON Schema validation with the jsonschema library.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml


class WorkflowValidationError(Exception):
    """Raised when workflow validation against JSON Schema fails."""

    def __init__(self, message: str, schema_path: str = "") -> None:
        """Initialise validation error.

        Args:
            message: Validation error description
            schema_path: JSON Schema path where validation failed
        """
        super().__init__(message)
        self.schema_path = schema_path


def load_schema(
    schema_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Load CausalIQ workflow JSON Schema.

    Args:
        schema_path: Optional path to custom schema file.
                    If None, loads default package schema.

    Returns:
        Parsed JSON Schema dictionary

    Raises:
        WorkflowValidationError: If schema file cannot be loaded
    """
    if schema_path is None:
        file_path = (
            Path(__file__).parent / "schemas" / "causaliq-workflow.json"
        )
    else:
        file_path = Path(schema_path)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise WorkflowValidationError(
                    f"Schema must be JSON object, got {type(data).__name__}"
                )
            return data
    except FileNotFoundError:
        raise WorkflowValidationError(f"Schema file not found: {file_path}")
    except json.JSONDecodeError as e:
        raise WorkflowValidationError(f"Invalid JSON in schema: {e}")


def _pre_validate_workflow(workflow: Dict[str, Any]) -> None:
    """Pre-validate workflow for common issues with clear error messages.

    This runs before JSON Schema validation to provide clearer errors
    for common mistakes.

    Args:
        workflow: Workflow configuration dictionary

    Raises:
        WorkflowValidationError: If workflow has common structural issues
    """
    # Check for unknown top-level keys
    known_keys = {"matrix", "steps"}
    for key in workflow:
        if key not in known_keys:
            raise WorkflowValidationError(f"Unknown key '{key}'")

    steps = workflow.get("steps", [])
    if not isinstance(steps, list):
        return  # Let jsonschema handle this

    for step in steps:
        if not isinstance(step, dict):
            continue  # Let jsonschema handle this

        has_name = "name" in step
        has_uses = "uses" in step
        has_run = "run" in step

        if not has_name:
            raise WorkflowValidationError("Step missing 'name' parameter")

        step_name = step["name"]

        if not has_uses and not has_run:
            raise WorkflowValidationError(
                f"Step '{step_name}': Missing 'uses' or 'run' parameter"
            )


def validate_workflow(
    workflow: Dict[str, Any], schema_path: Optional[Union[str, Path]] = None
) -> bool:
    """Validate workflow against CausalIQ JSON Schema.

    Args:
        workflow: Workflow configuration dictionary
        schema_path: Optional path to custom schema file

    Returns:
        True if workflow is valid

    Raises:
        WorkflowValidationError: If workflow validation fails
    """
    try:
        import jsonschema
    except ImportError:
        raise WorkflowValidationError(
            "jsonschema library required: pip install jsonschema"
        )

    # Pre-validate for common issues with clear error messages
    _pre_validate_workflow(workflow)

    schema = load_schema(schema_path)

    try:
        jsonschema.validate(workflow, schema)
        return True
    except jsonschema.ValidationError as e:
        # Convert absolute_path to string for error reporting
        path_str = ".".join(str(p) for p in e.absolute_path)
        raise WorkflowValidationError(
            f"Workflow validation failed: {e.message}",
            schema_path=path_str,
        )


def load_workflow_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Load workflow from YAML file.

    Args:
        file_path: Path to workflow YAML file

    Returns:
        Parsed workflow dictionary

    Raises:
        WorkflowValidationError: If file cannot be loaded
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise WorkflowValidationError(
                    f"Workflow must be YAML object, got {type(data).__name__}"
                )
            return data
    except FileNotFoundError:
        raise WorkflowValidationError(f"Workflow file not found: {file_path}")
    except yaml.YAMLError as e:
        raise WorkflowValidationError(f"Invalid YAML syntax: {e}")
