"""Binding workflow parameters to a workflow's matrix and variables.

A parameter is a value supplied by a calling workflow's ``with`` block or
by the ``--param`` CLI option. It binds to the called workflow by name:

- a name that matches a matrix dimension replaces that dimension's values;
- a name that matches a declared parameter overrides its default;
- any other name binds as a ``{{name}}`` template variable.

Declared parameters are the workflow's top-level keys other than
``matrix`` and ``steps``. A default is a scalar, a list of scalars or
``null``. A ``null`` default declares a parameter with no value: when
neither the caller nor the CLI supplies one, the parameter is omitted
from every action that would otherwise receive it, so the action's own
default applies. A list default is one value, so ``{{name}}`` delivers
the list itself; it never adds a matrix dimension. A placeholder that is
not declared is effectively required and must be supplied by the caller
or the CLI. Parameters are not part of a cache key: changing a parameter
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


def _substitute_text(text: str, variables: Dict[str, Any]) -> str:
    """Return text with every known ``{{name}}`` token expanded as text.

    The value's text form is used, so a step name always stays a string
    whatever type the bound value has. A token with no value is left as
    written, so an unresolved name stays visible.

    Args:
        text: String that may contain ``{{name}}`` tokens.
        variables: Variable values to substitute.

    Returns:
        The substituted text.
    """
    result = text
    for name in _extract_tokens(text):
        if name in variables:
            result = result.replace(f"{{{{{name}}}}}", str(variables[name]))
    return result


def _declared_parameters(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Return a workflow's declared parameter defaults."""
    return {
        key: value
        for key, value in workflow.items()
        if key not in _RESERVED_KEYS
    }


def _used_parameter_names(workflow: Dict[str, Any]) -> Set[str]:
    """Return the names a step uses as ``{{name}}`` tokens.

    A token counts wherever a step can show it: in the ``with`` block or
    in the step's ``name``. A nested workflow call's ``with`` block
    counts too, so a parameter that is only forwarded to a called
    workflow is still used.

    Args:
        workflow: Parsed workflow dictionary.

    Returns:
        Set of names referenced by a step parameter or step name.
    """
    used: Set[str] = set()
    for step in workflow.get("steps", []):
        used.update(_token_names(step.get("with", {})))
        used.update(_token_names(step.get("name")))
    return used


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
    names.update(_used_parameter_names(workflow))
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


def _null_default_names(workflow: Dict[str, Any]) -> Set[str]:
    """Return the names of parameters declared with a null default."""
    return {
        name
        for name, value in _declared_parameters(workflow).items()
        if value is None
    }


def _list_default_names(workflow: Dict[str, Any]) -> Set[str]:
    """Return the names of parameters declared with a list default."""
    return {
        name
        for name, value in _declared_parameters(workflow).items()
        if isinstance(value, list)
    }


def _null_parameter_names(
    value: Any, null_names: Set[str], whole: bool = True
) -> Set[str]:
    """Return whole-value-only parameters used where no whole value exists.

    A null-default parameter may only be the whole value of a step
    parameter. Text such as ``"data/{{name}}.csv"`` would otherwise
    become ``data/None.csv``, and a list element has no whole-value
    meaning either. A list-default parameter follows the same rule: it
    has no text form, so it may only be an entire step parameter value.

    Args:
        value: Step parameter value to inspect.
        null_names: Names of parameters that may only be whole values.
        whole: True when the value may be a whole-value token.

    Returns:
        Names used in a position that cannot accept a missing value or a
        list.
    """
    if isinstance(value, str):
        tokens = _extract_tokens(value) & null_names
        if whole and _single_token(value) in tokens:
            return set()
        return tokens
    if isinstance(value, list):
        return set().union(
            *(
                _null_parameter_names(item, null_names, whole=False)
                for item in value
            )
        )
    return set()


def _unused_parameter_errors(workflow: Dict[str, Any]) -> List[str]:
    """Return errors for declared parameters no step references.

    A default only affects a step that uses the name as a
    ``{{placeholder}}``, so an unused declaration is dead configuration.

    Args:
        workflow: Parsed workflow dictionary.

    Returns:
        One error per declared parameter that is never used.
    """
    unused = set(_declared_parameters(workflow)) - _used_parameter_names(
        workflow
    )
    return [
        f"Workflow parameter '{name}' is declared but never used as a "
        f"'{{{{{name}}}}}' placeholder in a step"
        for name in sorted(unused)
    ]


def _null_usage_step_errors(
    step_name: str,
    values: Dict[str, Any],
    null_names: Set[str],
) -> List[str]:
    """Return errors for null-default parameters misused by one step."""
    errors: List[str] = []
    for value in values.values():
        for name in sorted(_null_parameter_names(value, null_names)):
            errors.append(
                f"Step '{step_name}': parameter '{name}' is declared "
                f"null, so '{{{{{name}}}}}' may only be the whole value "
                f"of a step parameter"
            )
    return errors


def _null_parameter_usage_errors(workflow: Dict[str, Any]) -> List[str]:
    """Return errors for null-default parameters used as partial values."""
    null_names = _null_default_names(workflow)
    errors: List[str] = []
    for step in workflow.get("steps", []):
        step_name = step.get("name", "unnamed")
        errors.extend(
            _null_usage_step_errors(
                step_name, step.get("with", {}), null_names
            )
        )
    return errors


def _list_usage_step_errors(
    step_name: str, values: Dict[str, Any], list_names: Set[str]
) -> List[str]:
    """Return errors for list-default parameters used as partial values."""
    errors: List[str] = []
    for value in values.values():
        for name in sorted(_null_parameter_names(value, list_names)):
            errors.append(
                f"Step '{step_name}': parameter '{name}' is declared as "
                f"a list, so '{{{{{name}}}}}' may only be the whole value "
                f"of a step parameter"
            )
    return errors


def _list_parameter_usage_errors(workflow: Dict[str, Any]) -> List[str]:
    """Return errors for list-default parameters used as partial values.

    A list default has no text form, so interpolating it into a longer
    string or into a list element would substitute a list representation
    rather than the intended value.

    Args:
        workflow: Parsed workflow dictionary.

    Returns:
        One error per list-default parameter used where only a whole
        value is meaningful.
    """
    list_names = _list_default_names(workflow)
    errors: List[str] = []
    for step in workflow.get("steps", []):
        step_name = step.get("name", "unnamed")
        errors.extend(
            _list_usage_step_errors(
                step_name, step.get("with", {}), list_names
            )
        )
    return errors


def _parameter_errors(
    workflow: Dict[str, Any], parameters: Dict[str, Any]
) -> List[str]:
    """Return declaration and unknown-name parameter errors."""
    errors = _parameter_declaration_errors(workflow)
    errors.extend(_unknown_parameter_errors(parameters, workflow))
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


def _parameter_declaration_errors(workflow: Dict[str, Any]) -> List[str]:
    """Return clash, unused-declaration and usage errors.

    Args:
        workflow: Parsed workflow dictionary.

    Returns:
        Errors describing invalid or ineffective parameter declarations.
    """
    errors = _parameter_matrix_clash_errors(workflow)
    errors.extend(_unused_parameter_errors(workflow))
    errors.extend(_null_parameter_usage_errors(workflow))
    errors.extend(_list_parameter_usage_errors(workflow))
    return errors


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
