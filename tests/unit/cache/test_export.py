"""Unit tests for cache export module."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from causaliq_workflow.cache.export import (
    TYPE_EXTENSIONS,
    build_entry_path,
    get_extension_for_type,
    sanitise_path_segment,
    serialise_objects,
    store_action_result,
    store_failure_result,
)

# =============================================================================
# get_extension_for_type tests
# =============================================================================


# Test get_extension_for_type returns correct extension for graphml type.
def test_get_extension_for_type_graphml() -> None:
    """Test graphml type returns .graphml extension."""
    assert get_extension_for_type("graphml") == ".graphml"


# Test get_extension_for_type returns .dat for unknown type including pdg.
def test_get_extension_for_type_pdg() -> None:
    """Test pdg type returns .dat (pdg is semantic type, not format)."""
    assert get_extension_for_type("pdg") == ".dat"


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


# Test build_entry_path sanitises Windows-invalid colon in values.
def test_build_entry_path_sanitises_colon() -> None:
    """Test path sanitises colon characters for Windows compatibility."""
    matrix_values = {"model": "ollama_qwen3:1.7b"}

    result = build_entry_path(matrix_values)

    assert result == Path("ollama_qwen3_1.7b")


# Test sanitise_path_segment returns underscore when value cleans empty.
def test_sanitise_path_segment_empty_after_cleaning() -> None:
    """Test segment falls back to underscore when all chars are invalid."""
    result = sanitise_path_segment("...")

    assert result == "_"


# Test sanitise_path_segment wraps reserved Windows device names.
def test_sanitise_path_segment_reserved_windows_name() -> None:
    """Test reserved Windows names are made safe."""
    result = sanitise_path_segment("con")

    assert result == "_con_"


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


# =============================================================================
# store_action_result tests
# =============================================================================


# Test store_action_result returns None when cache is None.
def test_store_action_result_returns_none_when_no_cache() -> None:
    """Test that store_action_result returns None when cache is None."""
    context = MagicMock()
    context.matrix_values = {"dataset": "asia"}

    result = store_action_result(
        cache=None,
        context=context,
        metadata={"status": "success"},
        objects=[{"type": "json", "name": "result", "content": "{}"}],
    )

    assert result is None


# Test store_action_result writes one typed object and returns its hash.
def test_store_action_result_writes_typed_entry() -> None:
    """Test that store_action_result stores the entry in the cache."""
    from causaliq_workflow.cache import WorkflowCache

    context = MagicMock()
    context.matrix_values = {"dataset": "asia"}
    metadata = {"status": "success", "node_count": 5}
    objects = [{"type": "dag", "format": "graphml", "content": "<graphml/>"}]

    with WorkflowCache(":memory:") as cache:
        hash_key = store_action_result(cache, context, metadata, objects)
        assert hash_key == cache.compute_hash({"dataset": "asia"})
        entry = cache.get({"dataset": "asia"})
        assert entry is not None
        assert entry.metadata["result"]["node_count"] == 5
        assert entry.has_object("dag")


# Test store_failure_result returns None when cache is None.
def test_store_failure_result_returns_none_when_no_cache() -> None:
    """store_failure_result returns None when there is no cache."""
    context = MagicMock()
    context.matrix_values = {"dataset": "asia"}

    result = store_failure_result(
        cache=None,
        context=context,
        metadata={"provider": {"action": {"status": "error"}}},
    )

    assert result is None


# Metadata-only entries are exported so their _meta.json is produced.
def test_export_entries_metadata_only(tmp_path: Path) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.cache.export import export_entries

    with WorkflowCache(":memory:") as cache:
        entry = CacheEntry()
        entry.metadata["provider"] = {
            "learn_graph": {"status": "input", "error": "bad data"}
        }
        cache.put({"dataset": "asia"}, entry)

        count = export_entries(cache, tmp_path, ["dataset"])

        assert count == 1
        meta_path = tmp_path / "asia" / "_meta.json"
        assert meta_path.exists()
        saved = json.loads(meta_path.read_text())
        assert set(saved) == {
            "schema_version",
            "matrix_values",
            "metadata",
        }
        assert saved["schema_version"] == 2
        metadata = saved["metadata"]
        assert metadata["provenance"]["provider"] == "provider"
        assert metadata["provenance"]["action"] == "learn_graph"
        assert metadata["result"]["status"] == "input"
        assert metadata["result"]["error"] == "bad data"
        assert "objects" not in saved


# Entries with neither objects nor metadata are skipped on export.
def test_export_entries_skips_truly_empty_entries(
    tmp_path: Path,
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache
    from causaliq_workflow.cache.export import export_entries

    with WorkflowCache(":memory:") as cache:
        cache.put({"dataset": "asia"}, CacheEntry())

        count = export_entries(cache, tmp_path, ["dataset"])

        assert count == 0
        assert not (tmp_path / "asia").exists()
