"""
JSON Schema-based workflow validation for CausalIQ.

Uses standard JSON Schema validation with the jsonschema library.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import yaml

from causaliq_workflow.yaml_frontend import load_workflow_text

_RESERVED_KEYS = frozenset({"matrix", "steps"})


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

    Any top-level key other than ``matrix`` and ``steps`` declares a
    workflow parameter default, so it must be a scalar or a list of
    scalars. A ``null`` default declares a parameter with no value: the
    parameter is omitted from an action when nothing supplies it. A list
    default is delivered as a single value and never adds a matrix
    dimension.

    Args:
        workflow: Workflow configuration dictionary

    Raises:
        WorkflowValidationError: If workflow has common structural issues
    """
    for key, value in workflow.items():
        if key not in _RESERVED_KEYS:
            _check_parameter_default(key, value)

    steps = workflow.get("steps", [])
    if not isinstance(steps, list):
        return  # Let jsonschema handle this

    duplicate_errors = _duplicate_step_name_errors(workflow)
    if duplicate_errors:
        raise WorkflowValidationError("; ".join(duplicate_errors))

    for step in steps:
        _pre_validate_step(step)


def _duplicate_step_name_errors(workflow: Dict[str, Any]) -> List[str]:
    """Return one error per repeated step name.

    Step results are recorded by name, so a repeated name silently
    overwrites the earlier step's result and makes the completion
    summary under-count the steps that ran.

    Args:
        workflow: Workflow configuration dictionary.

    Returns:
        One error per step name that occurs more than once.
    """
    steps = workflow.get("steps", [])
    if not isinstance(steps, list):
        return []
    seen: Set[str] = set()
    repeated: Set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            continue
        name = step.get("name")
        if not isinstance(name, str):
            continue
        if name in seen:
            repeated.add(name)
        seen.add(name)
    return [
        f"Duplicate step name '{name}': step names must be unique "
        f"because results are recorded by name"
        for name in sorted(repeated)
    ]


_SCALAR_DEFAULT_TYPES = (str, int, float, bool)


def _check_list_default(key: str, values: List[Any]) -> None:
    """Reject a list parameter default whose items are not scalars.

    A list default is a single value that a workflow may pass on, so it
    accepts the same item types as a step parameter list. A null item has
    no meaning: the null default already expresses 'no value'.

    Args:
        key: Top-level workflow key that declares the default.
        values: The declared list value.

    Raises:
        WorkflowValidationError: If an item is null, a list or a mapping.
    """
    for value in values:
        if value is None:
            raise WorkflowValidationError(
                f"Unknown key '{key}': a list parameter must not contain "
                f"null; declare the parameter null to mean 'no value'"
            )
        if not isinstance(value, _SCALAR_DEFAULT_TYPES):
            raise WorkflowValidationError(
                f"Unknown key '{key}': a list parameter must contain only "
                f"strings, numbers or booleans"
            )


def _check_parameter_default(key: str, value: Any) -> None:
    """Reject a workflow key that cannot declare a parameter default.

    Args:
        key: Top-level workflow key.
        value: Declared default value for the key.

    Raises:
        WorkflowValidationError: If the value is neither a scalar, null,
            nor a list of scalars.
    """
    if isinstance(value, list):
        _check_list_default(key, value)
        return
    if value is None or isinstance(value, _SCALAR_DEFAULT_TYPES):
        return
    raise WorkflowValidationError(
        f"Unknown key '{key}': workflow parameters must be a scalar "
        f"(string, number, boolean or null) or a list of scalars"
    )


def _pre_validate_step(step: Any) -> None:
    """Validate the required structural fields of a single step."""
    if not isinstance(step, dict):
        return  # Let jsonschema handle this

    if "name" not in step:
        raise WorkflowValidationError("Step missing 'name' parameter")

    step_name = step["name"]

    if "uses" not in step and "run" not in step:
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
        text = Path(file_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise WorkflowValidationError(f"Workflow file not found: {file_path}")
    try:
        data = load_workflow_text(text)
    except yaml.YAMLError as e:
        raise WorkflowValidationError(_yaml_error_message(str(e), text))
    if not isinstance(data, dict):
        raise WorkflowValidationError(
            f"Workflow must be YAML object, got {type(data).__name__}"
        )
    return data


_YAML_HINT_TRIGGERS = (
    "unhashable key",
    "expected <block end>",
    "found unexpected",
)

_TOKEN_HINT = (
    "Hint: template tokens use {{name}}, where name contains letters, "
    "digits, '_' or '-'. Nested tokens and default(...) filters are "
    "not supported."
)


def _yaml_error_message(error: str, source: str) -> str:
    """Return an invalid-YAML message, hinting at malformed tokens.

    Args:
        error: The message from the YAML parser.
        source: Workflow file text that failed to parse.

    Returns:
        Error message, with a token hint when a template token is the
        likely cause.
    """
    message = f"Invalid YAML syntax: {error}"
    if "{{" not in source:
        return message
    if not any(trigger in error for trigger in _YAML_HINT_TRIGGERS):
        return message
    return f"{message}\n{_TOKEN_HINT}"
