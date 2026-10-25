"""Binding workflow parameters to a workflow's matrix and variables.

A parameter is a value supplied by a calling workflow's ``with`` block or
by the ``--param`` CLI option. It binds to the called workflow by name:

- a name that matches a matrix dimension replaces that dimension's values;
- a name that matches a declared parameter overrides its default;
- any other name binds as a ``{{name}}`` template variable.

Declared parameters are the workflow's top-level scalar keys. A ``null``
default marks a parameter as required. Parameters never add a matrix
dimension, so they are not part of a cache key: changing a parameter
value does not invalidate existing entries.
"""

import re
from typing import Any, Dict, List, Optional, Set

from causaliq_workflow.schema import _RESERVED_KEYS

_TOKEN_PATTERN = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_-]*)\}\}")
_SINGLE_TOKEN_PATTERN = re.compile(r"^\{\{([a-zA-Z_][a-zA-Z0-9_-]*)\}\}$")
_PARAMETER_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


def _is_parameter_name(name: Any) -> bool:
    """Return True when a value is a valid parameter name."""
    if not isinstance(name, str):
        return False
    return _PARAMETER_NAME_PATTERN.match(name) is not None


def _extract_tokens(text: Any) -> Set[str]:
    """Return the ``{{name}}`` tokens used by a string."""
    if not isinstance(text, str):
        return set()
    return set(_TOKEN_PATTERN.findall(text))


def _token_names(obj: Any) -> Set[str]:
    """Return every ``{{name}}`` token used by a workflow object."""
    if isinstance(obj, dict):
        return set().union(*(_token_names(value) for value in obj.values()))
    if isinstance(obj, list):
        return set().union(*(_token_names(item) for item in obj))
    return _extract_tokens(obj)


def _single_token(text: Any) -> Optional[str]:
    """Return the name when a value is exactly one ``{{name}}`` token."""
    if not isinstance(text, str):
        return None
    match = _SINGLE_TOKEN_PATTERN.match(text)
    return match.group(1) if match else None


def _declared_parameters(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Return a workflow's declared parameter defaults."""
    return {
        key: value
        for key, value in workflow.items()
        if key not in _RESERVED_KEYS
    }


def _parameter_names(workflow: Dict[str, Any]) -> Set[str]:
    """Return the parameter names a caller may bind for a workflow.

    A name is accepted when it is a declared parameter, a matrix
    dimension, or a ``{{name}}`` token used by a step's ``with`` block,
    including a nested workflow call's ``with`` block.

    Args:
        workflow: Parsed workflow dictionary.

    Returns:
        Set of accepted parameter names.
    """
    names = set(_declared_parameters(workflow))
    names.update(workflow.get("matrix", {}))
    for step in workflow.get("steps", []):
        names.update(_token_names(step.get("with", {})))
    return names


def _unknown_parameter_errors(
    parameters: Dict[str, Any],
    workflow: Dict[str, Any],
    workflow_label: str = "",
) -> List[str]:
    """Return one error per parameter the workflow does not accept.

    Args:
        parameters: Parameter names supplied by a caller or the CLI.
        workflow: Workflow that receives the parameters.
        workflow_label: File name used in the error message, if known.

    Returns:
        Validation errors, empty when every name is accepted.
    """
    accepted = _parameter_names(workflow)
    scope = (
        f"workflow '{workflow_label}'" if workflow_label else "this workflow"
    )
    return [
        f"Parameter '{name}' is not used by {scope}. "
        f"Accepted: {sorted(accepted)}"
        for name in sorted(parameters)
        if name not in accepted
    ]


def _missing_required_errors(
    workflow: Dict[str, Any], parameters: Dict[str, Any]
) -> List[str]:
    """Return an error when a required parameter has no value."""
    required = sorted(
        name
        for name, value in _declared_parameters(workflow).items()
        if value is None and name not in parameters
    )
    if not required:
        return []
    return [
        f"Required workflow parameter(s) not provided: {required}. "
        f"Provide them with 'with:' in the calling workflow or --param."
    ]


def _parameter_errors(
    workflow: Dict[str, Any], parameters: Dict[str, Any]
) -> List[str]:
    """Return unknown-name and missing-required parameter errors."""
    errors = _unknown_parameter_errors(parameters, workflow)
    errors.extend(_missing_required_errors(workflow, parameters))
    return errors


def _parameter_matrix_clash_errors(workflow: Dict[str, Any]) -> List[str]:
    """Return errors for names declared as both parameter and matrix."""
    clash = set(_declared_parameters(workflow))
    clash &= set(workflow.get("matrix", {}))
    return [
        f"Workflow key '{name}' is declared as both a parameter and a "
        f"matrix variable"
        for name in sorted(clash)
    ]


def _call_parameters_vary(
    step: Dict[str, Any], matrix: Dict[str, Any]
) -> bool:
    """Return True when a call step's parameters differ per matrix job.

    Args:
        step: Workflow-call step configuration.
        matrix: The calling workflow's matrix definition.

    Returns:
        True when a ``with`` value references a matrix variable.
    """
    if not matrix:
        return False
    return bool(_token_names(step.get("with", {})) & set(matrix))
