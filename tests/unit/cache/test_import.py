"""Unit tests for cache import module."""

from causaliq_workflow.cache.import_ import (
    EXTENSION_TYPES,
    get_type_for_extension,
)

# =============================================================================
# EXTENSION_TYPES tests
# =============================================================================


# Test EXTENSION_TYPES maps extensions back to types.
def test_extension_types_maps_graphml() -> None:
    """Test EXTENSION_TYPES maps .graphml to a valid type."""
    # Note: Multiple types can map to .graphml (graphml, pdg)
    # EXTENSION_TYPES picks one (whichever is last in dict iteration)
    assert EXTENSION_TYPES[".graphml"] in ("graphml", "pdg")


# Test EXTENSION_TYPES maps json extension.
def test_extension_types_maps_json() -> None:
    """Test EXTENSION_TYPES maps .json to json type."""
    assert EXTENSION_TYPES[".json"] == "json"


# =============================================================================
# get_type_for_extension tests
# =============================================================================


# Test get_type_for_extension returns valid type for .graphml.
def test_get_type_for_extension_graphml() -> None:
    """Test .graphml extension returns a valid graphml-related type."""
    # Could be "graphml" or "pdg" depending on dict ordering
    result = get_type_for_extension(".graphml")
    assert result in ("graphml", "pdg")


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
