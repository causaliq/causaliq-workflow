"""Unit tests for workflow YAML value handling."""

from typing import Any

import pytest

from causaliq_workflow.yaml_frontend import (
    load_workflow_text,
    parse_scalar_text,
)


# A whole-value template token needs no quotes.
def test_unquoted_token_is_a_string() -> None:
    data = load_workflow_text("with:\n  sample_size: {{sample_size}}\n")
    assert data["with"]["sample_size"] == "{{sample_size}}"


# A token embedded in text is preserved as text.
def test_embedded_token_is_preserved() -> None:
    data = load_workflow_text("with:\n  dataset: data/{{network}}.csv\n")
    assert data["with"]["dataset"] == "data/{{network}}.csv"


# A quoted token parses to the same value as an unquoted token.
def test_quoted_and_unquoted_tokens_match() -> None:
    quoted = load_workflow_text('with:\n  x: "{{x}}"\n')
    unquoted = load_workflow_text("with:\n  x: {{x}}\n")
    assert quoted == unquoted == {"with": {"x": "{{x}}"}}
    assert quoted is not unquoted


# A token inside a list is preserved.
def test_token_in_list_is_preserved() -> None:
    data = load_workflow_text("with:\n  x: [{{a}}, plain]\n")
    assert data["with"]["x"] == ["{{a}}", "plain"]


# A token inside a block scalar is preserved.
def test_token_in_block_scalar_is_preserved() -> None:
    data = load_workflow_text("with:\n  x: |\n    {{a}}\n")
    assert data["with"]["x"] == "{{a}}\n"


# A token used as a mapping key is restored.
def test_token_as_key_is_restored() -> None:
    data = load_workflow_text("{{key}}: value\n")
    assert data == {"{{key}}": "value"}


# Repeated tokens are each restored.
def test_repeated_tokens_are_restored() -> None:
    data = load_workflow_text("a: {{x}}\nb: {{x}}\nc: pre-{{x}}-post\n")
    assert data == {"a": "{{x}}", "b": "{{x}}", "c": "pre-{{x}}-post"}


# Plain text that YAML 1.1 would type is kept as text.
@pytest.mark.parametrize(
    "text",
    [
        "no",
        "yes",
        "on",
        "off",
        "01",
        "00",
        "0x10",
        "1_000",
        "10:30",
        "2020-01-01",
        "1e3",
        "1K",
        "Hello",
    ],
)
def test_plain_text_values_stay_text(text: str) -> None:
    data = load_workflow_text(f"value: {text}\n")
    assert data["value"] == text
    assert isinstance(data["value"], str)


# Numbers that need no extra typing stay numbers.
@pytest.mark.parametrize(
    "text, expected",
    [("1000", 1000), ("-1", -1), ("0", 0), ("1.5", 1.5), (".5", 0.5)],
)
def test_numeric_values_stay_numbers(text: str, expected: Any) -> None:
    data = load_workflow_text(f"value: {text}\n")
    assert data["value"] == expected
    assert type(data["value"]) is type(expected)


# Buttons and nulls keep their YAML meaning.
def test_boolean_and_null_values() -> None:
    data = load_workflow_text("a: true\nb: FALSE\nc: null\nd: ~\ne:\n")
    assert data == {"a": True, "b": False, "c": None, "d": None, "e": None}


# A float keeps its numeric value even when its spelling changes.
def test_float_trailing_zero_is_numeric() -> None:
    data = load_workflow_text("value: 1.10\n")
    assert data["value"] == 1.1


# A CLI scalar follows the same value rules.
def test_parse_scalar_text_values() -> None:
    assert parse_scalar_text("no") == "no"
    assert parse_scalar_text("01") == "01"
    assert parse_scalar_text("2020-01-01") == "2020-01-01"
    assert parse_scalar_text("1000") == 1000
    assert parse_scalar_text("true") is True
    assert parse_scalar_text("null") is None


# A CLI list value stays a list.
def test_parse_scalar_text_list() -> None:
    assert parse_scalar_text("[pc, ges]") == ["pc", "ges"]
