"""Unit tests for cache export module."""

from pathlib import Path

from causaliq_workflow.cache.export import (
    TYPE_EXTENSIONS,
    build_entry_path,
    get_extension_for_type,
    serialise_objects,
)

# =============================================================================
# get_extension_for_type tests
# =============================================================================


# Test get_extension_for_type returns correct extension for graphml type.
def test_get_extension_for_type_graphml() -> None:
    """Test graphml type returns .graphml extension."""
    assert get_extension_for_type("graphml") == ".graphml"


# Test get_extension_for_type returns correct extension for json type.
def test_get_extension_for_type_json() -> None:
    """Test json type returns .json extension."""
    assert get_extension_for_type("json") == ".json"


# Test get_extension_for_type returns .dat for unknown type.
def test_get_extension_for_type_unknown() -> None:
    """Test unknown type returns .dat extension."""
    assert get_extension_for_type("unknown") == ".dat"


# Test TYPE_EXTENSIONS contains expected mappings.
def test_type_extensions_contains_expected() -> None:
    """Test TYPE_EXTENSIONS has all expected entries."""
    assert "graphml" in TYPE_EXTENSIONS
    assert "json" in TYPE_EXTENSIONS
    assert len(TYPE_EXTENSIONS) == 2


# =============================================================================
# build_entry_path tests
# =============================================================================


# Test build_entry_path creates correct path with matrix keys.
def test_build_entry_path_with_matrix_keys() -> None:
    """Test path created correctly with specified matrix keys."""
    matrix_values = {"dataset": "asia", "method": "pc"}

    result = build_entry_path(
        matrix_values,
        matrix_keys=["dataset", "method"],
    )

    assert result == Path("asia/pc")


# Test build_entry_path uses alphabetical order without matrix keys.
def test_build_entry_path_alphabetical_order() -> None:
    """Test path uses alphabetical key order when no keys specified."""
    matrix_values = {"method": "pc", "dataset": "asia"}

    result = build_entry_path(matrix_values)

    # Should be dataset/method (alphabetical)
    assert result == Path("asia/pc")


# Test build_entry_path sanitises special characters.
def test_build_entry_path_sanitises_characters() -> None:
    """Test path sanitises slashes in values."""
    matrix_values = {"dataset": "path/to/data"}

    result = build_entry_path(matrix_values)

    assert result == Path("path_to_data")


# Test build_entry_path handles empty matrix values.
def test_build_entry_path_empty_matrix() -> None:
    """Test path with no matrix values."""
    result = build_entry_path({})

    assert result == Path("default")


# =============================================================================
# serialise_objects tests
# =============================================================================


# Test serialise_objects extracts content from objects spec.
def test_serialise_objects_extracts_content() -> None:
    """Test serialise_objects extracts content from objects spec."""
    objects_spec = [
        {
            "type": "graphml",
            "name": "graph",
            "content": "<graphml>content</graphml>",
        },
    ]

    result = serialise_objects(None, objects_spec)

    assert "graph.graphml" in result
    assert result["graph.graphml"] == "<graphml>content</graphml>"


# Test serialise_objects skips objects with missing content.
def test_serialise_objects_skips_missing_content() -> None:
    """Test objects without content are skipped."""
    objects_spec = [
        {"type": "graphml", "name": "graph"},  # No content
    ]

    result = serialise_objects({}, objects_spec)

    assert result == {}


# Test serialise_objects skips objects with missing type.
def test_serialise_objects_skips_missing_type() -> None:
    """Test objects without type are skipped."""
    objects_spec = [
        {"name": "graph", "content": "<graphml/>"},  # No type
    ]

    result = serialise_objects({}, objects_spec)

    assert result == {}


# Test serialise_objects uses type as default name.
def test_serialise_objects_uses_type_as_default_name() -> None:
    """Test name defaults to type if not specified."""
    objects_spec = [
        {"type": "graphml", "content": "<graphml>content</graphml>"},
    ]

    result = serialise_objects({}, objects_spec)

    # Should use "graphml" as the name
    assert "graphml.graphml" in result


# Test serialise_objects handles multiple objects.
def test_serialise_objects_multiple_objects() -> None:
    """Test multiple objects in spec are processed."""
    objects_spec = [
        {
            "type": "graphml",
            "name": "result",
            "content": "<graphml>1</graphml>",
        },
        {"type": "json", "name": "metadata", "content": '{"data": "raw"}'},
    ]

    result = serialise_objects({}, objects_spec)

    assert "result.graphml" in result
    assert "metadata.json" in result
    assert len(result) == 2
