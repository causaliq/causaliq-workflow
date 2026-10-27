"""Unit tests for action parameter coercion at the workflow boundary."""

from typing import Any, Dict

import pytest
from causaliq_core import ActionInput

from causaliq_workflow.value_coercion import (
    _coerce_list,
    _coerce_scalar,
    _list_element_kind,
    _scalar_kinds,
    coerce_action_parameters,
)


# A provider that declares the input hints used by the tests.
class _Provider:
    inputs = {
        "seed": ActionInput("seed", "", type_hint="int"),
        "timeout": ActionInput("timeout", "", type_hint="float or int"),
        "flag": ActionInput("flag", "", type_hint="bool"),
        "label": ActionInput("label", "", type_hint="str"),
        "sample_size": ActionInput(
            "sample_size", "", type_hint="int, list[int] or str"
        ),
        "metric": ActionInput("metric", "", type_hint="list[str]"),
        "values": ActionInput("values", "", type_hint="list[float]"),
        "anything": ActionInput("anything", "", type_hint="Any"),
    }


# An integer hint converts integral text.
def test_coerce_integer_parameter() -> None:
    result = coerce_action_parameters(_Provider(), {"seed": "42"})
    assert result["seed"] == 42
    assert isinstance(result["seed"], int)


# A float hint converts decimal text.
def test_coerce_float_parameter() -> None:
    result = coerce_action_parameters(_Provider(), {"timeout": "2.5"})
    assert result["timeout"] == 2.5


# A float-or-int hint keeps an integral value as an int.
def test_coerce_numeric_union_integral() -> None:
    result = coerce_action_parameters(_Provider(), {"timeout": "2"})
    assert result["timeout"] == 2
    assert isinstance(result["timeout"], int)


# A boolean hint accepts all common spellings.
@pytest.mark.parametrize(
    "text, expected",
    [
        ("true", True),
        ("yes", True),
        ("on", True),
        ("1", True),
        ("false", False),
        ("no", False),
        ("off", False),
        ("0", False),
    ],
)
def test_coerce_boolean_parameter(text: str, expected: bool) -> None:
    result = coerce_action_parameters(_Provider(), {"flag": text})
    assert result["flag"] is expected


# A boolean hint leaves unrecognised text for the action to reject.
def test_coerce_boolean_rejects_other_text() -> None:
    result = coerce_action_parameters(_Provider(), {"flag": "maybe"})
    assert result["flag"] == "maybe"


# A string hint never coerces numeric text.
def test_string_parameter_stays_text() -> None:
    result = coerce_action_parameters(_Provider(), {"label": "1000"})
    assert result["label"] == "1000"


# An ambiguous union is left to the action.
def test_ambiguous_union_is_not_coerced() -> None:
    result = coerce_action_parameters(_Provider(), {"sample_size": "1000"})
    assert result["sample_size"] == "1000"


# A list of integers is coerced element by element.
def test_list_of_integer_elements() -> None:
    result = coerce_action_parameters(
        _Provider(), {"sample_size": ["500", 1000, "all"]}
    )
    assert result["sample_size"] == [500, 1000, "all"]


# A list of floats is coerced element by element.
def test_list_of_float_elements() -> None:
    result = coerce_action_parameters(_Provider(), {"values": ["0.5", "1"]})
    assert result["values"] == [0.5, 1]


# A list of strings is unchanged.
def test_list_of_string_elements() -> None:
    result = coerce_action_parameters(
        _Provider(), {"metric": ["f1", "precision"]}
    )
    assert result["metric"] == ["f1", "precision"]


# An undeclared parameter is left unchanged.
def test_undeclared_parameter_is_unchanged() -> None:
    result = coerce_action_parameters(_Provider(), {"extra": "42"})
    assert result["extra"] == "42"


# A provider without input declarations leaves values unchanged.
def test_provider_without_inputs() -> None:
    result = coerce_action_parameters(object(), {"seed": "42"})
    assert result == {"seed": "42"}


# A non-string value is returned unchanged.
def test_non_string_value_is_unchanged() -> None:
    result = coerce_action_parameters(_Provider(), {"seed": 42})
    assert result["seed"] == 42


# Unconvertible numeric text is returned unchanged.
def test_unconvertible_text_is_unchanged() -> None:
    result = coerce_action_parameters(_Provider(), {"seed": "many"})
    assert result["seed"] == "many"


# A scalar hint is empty when it mixes text with numbers.
def test_scalar_kinds_for_text_union() -> None:
    assert _scalar_kinds("int or str") == frozenset()
    assert _scalar_kinds("") == frozenset()


# A numeric union keeps both alternatives.
def test_scalar_kinds_for_numeric_union() -> None:
    assert _scalar_kinds("int | float") == frozenset({"int", "float"})


# A list element hint is found only for a typed list.
def test_list_element_kind() -> None:
    assert _list_element_kind("int, list[int] or str") == "int"
    assert _list_element_kind("list[str]") is None


# A scalar conversion returns the original text when it cannot convert.
def test_coerce_scalar_fallback() -> None:
    assert _coerce_scalar("many", frozenset({"int"})) == "many"


# A list without an element hint is returned unchanged.
def test_coerce_list_without_kind() -> None:
    values = ["1", "2"]
    assert _coerce_list(values, None) is values


# Coercion builds a new parameter mapping.
def test_coercion_does_not_mutate_input() -> None:
    parameters: Dict[str, Any] = {"seed": "42"}
    result = coerce_action_parameters(_Provider(), parameters)
    assert parameters == {"seed": "42"}
    assert result == {"seed": 42}


# The registry applies coercion before returning effective parameters.
def test_effective_parameters_are_coerced() -> None:
    from causaliq_workflow.registry import _effective_parameters

    parameters = _effective_parameters(
        _Provider(), "act", {"action": "act", "seed": "42"}
    )
    assert parameters == {"seed": 42}
