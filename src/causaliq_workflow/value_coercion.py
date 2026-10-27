"""Type coercion for action parameters at the workflow boundary.

Workflow values may be written as text or as YAML scalars. Actions
declare the shape they expect through ``ActionInput.type_hint``. Values
that are unambiguously convertible are coerced just before the action
runs, so quoting a number or a boolean never changes its meaning.

Coercion is deliberately conservative. A hint that is not exclusively
numeric or boolean, such as ``int or str``, is left to the action.
Unconvertible text is also left unchanged, so the action reports its own
validation error.
"""

import re
from typing import Any, Dict, FrozenSet, List, Optional

_TRUE_VALUES = frozenset({"true", "yes", "on", "1"})

_FALSE_VALUES = frozenset({"false", "no", "off", "0"})

_SCALAR_KINDS = frozenset({"int", "float", "bool"})

_INT_PATTERN = re.compile(r"^[-+]?[0-9]+$")

_FLOAT_PATTERN = re.compile(
    r"^[-+]?(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?$"
)


def _hint_alternatives(type_hint: str) -> List[str]:
    """Return the alternatives declared by a type hint."""
    normalised = type_hint.replace("|", " or ").lower()
    return [part.strip() for part in normalised.split(" or ") if part.strip()]


def _scalar_kinds(type_hint: str) -> FrozenSet[str]:
    """Return the scalar coercion kinds for a type hint.

    A hint that mixes a scalar type with text or another shape keeps the
    text as written, because the action already accepts a string.
    """
    kinds = frozenset(_hint_alternatives(type_hint))
    if kinds and kinds <= _SCALAR_KINDS:
        return kinds
    return frozenset()


def _coerce_scalar(value: str, kinds: FrozenSet[str]) -> Any:
    """Coerce a string to a declared scalar type when possible."""
    text = value.strip()
    if "bool" in kinds:
        lowered = text.lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
    if "int" in kinds or "float" in kinds:
        if _INT_PATTERN.match(text):
            return int(text)
        if _FLOAT_PATTERN.match(text):
            return float(text)
    return value


def _list_element_kind(type_hint: str) -> Optional[str]:
    """Return the element type declared for a list parameter."""
    lowered = type_hint.lower()
    for kind in ("int", "float", "bool"):
        if f"list[{kind}]" in lowered:
            return kind
    return None


def _coerce_list(values: List[Any], kind: Optional[str]) -> List[Any]:
    """Coerce the string elements of a list parameter."""
    if kind is None:
        return values
    kinds = frozenset({kind})
    return [
        _coerce_scalar(value, kinds) if isinstance(value, str) else value
        for value in values
    ]


def _coerce_value(value: Any, spec: Any) -> Any:
    """Coerce one value using its action input specification."""
    type_hint = getattr(spec, "type_hint", "") or ""
    if isinstance(value, list):
        return _coerce_list(value, _list_element_kind(type_hint))
    if not isinstance(value, str):
        return value
    return _coerce_scalar(value, _scalar_kinds(type_hint))


def coerce_action_parameters(
    provider: Any, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Return parameters with unambiguous values coerced for the action.

    Args:
        provider: Action provider instance that declares ``inputs``.
        parameters: Effective action parameters.

    Returns:
        A new mapping in which declared numeric and boolean values are
        converted from text. Undeclared or ambiguous parameters are
        unchanged.
    """
    specs = getattr(provider, "inputs", {}) or {}
    return {
        name: _coerce_value(value, specs[name]) if name in specs else value
        for name, value in parameters.items()
    }
