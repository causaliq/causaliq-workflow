"""Unit tests for canonical matrix value comparison."""

from causaliq_workflow.workflow.matrix import _matrix_values_match


# A number and its text spelling match.
def test_number_and_text_match() -> None:
    entry = {"sample_size": 100}
    target = {"sample_size": "100"}
    assert _matrix_values_match(entry, target, ["sample_size"]) is True


# Numeric suffix case differences match.
def test_numeric_suffix_case_matches() -> None:
    entry = {"sample_size": "1K"}
    target = {"sample_size": "1k"}
    assert _matrix_values_match(entry, target, ["sample_size"]) is True


# Boolean values match their text spelling.
def test_boolean_and_text_match() -> None:
    entry = {"flag": True}
    target = {"flag": "true"}
    assert _matrix_values_match(entry, target, ["flag"]) is True


# Different numeric values do not match.
def test_different_numbers_do_not_match() -> None:
    entry = {"sample_size": 100}
    target = {"sample_size": "1000"}
    assert _matrix_values_match(entry, target, ["sample_size"]) is False


# A null target remains a wildcard.
def test_null_target_is_wildcard() -> None:
    entry = {"sample_size": 100}
    target = {"sample_size": None}
    assert _matrix_values_match(entry, target, ["sample_size"]) is True


# A missing entry dimension remains a wildcard.
def test_missing_entry_dimension_is_wildcard() -> None:
    entry = {}
    target = {"sample_size": "100"}
    assert _matrix_values_match(entry, target, ["sample_size"]) is True
