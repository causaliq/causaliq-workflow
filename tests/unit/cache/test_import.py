"""Unit tests for cache import module."""

from causaliq_workflow.cache.export import TYPE_EXTENSIONS
from causaliq_workflow.cache.import_ import (
    EXTENSION_TYPES,
    get_type_for_extension,
)

# =============================================================================
# EXTENSION_TYPES tests
# =============================================================================


# Test EXTENSION_TYPES is reverse of TYPE_EXTENSIONS.
def test_extension_types_is_reverse_mapping() -> None:
    """Test EXTENSION_TYPES correctly reverses TYPE_EXTENSIONS."""
    for obj_type, ext in TYPE_EXTENSIONS.items():
        assert EXTENSION_TYPES[ext] == obj_type


# Test EXTENSION_TYPES has same number of entries as TYPE_EXTENSIONS.
def test_extension_types_same_length() -> None:
    """Test EXTENSION_TYPES has same count as TYPE_EXTENSIONS."""
    assert len(EXTENSION_TYPES) == len(TYPE_EXTENSIONS)


# =============================================================================
# get_type_for_extension tests
# =============================================================================


# Test get_type_for_extension returns correct type for .graphml.
def test_get_type_for_extension_graphml() -> None:
    """Test .graphml extension returns graphml type."""
    assert get_type_for_extension(".graphml") == "graphml"


# Test get_type_for_extension returns correct type for .json.
def test_get_type_for_extension_json() -> None:
    """Test .json extension returns json type."""
    assert get_type_for_extension(".json") == "json"


# Test get_type_for_extension returns dat for unknown extension.
def test_get_type_for_extension_unknown() -> None:
    """Test unknown extension returns dat type."""
    assert get_type_for_extension(".unknown") == "dat"


# Test get_type_for_extension returns dat for empty string.
def test_get_type_for_extension_empty() -> None:
    """Test empty extension returns dat type."""
    assert get_type_for_extension("") == "dat"


# Test get_type_for_extension handles extension without dot.
def test_get_type_for_extension_no_dot() -> None:
    """Test extension without leading dot returns dat."""
    # The function expects extensions with dots, so 'json' won't match
    assert get_type_for_extension("json") == "dat"
