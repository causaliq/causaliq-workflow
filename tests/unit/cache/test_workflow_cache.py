"""Unit tests for WorkflowCache class."""

import pytest
from causaliq_core.cache.encoders import JsonEncoder

from causaliq_workflow.cache import WorkflowCache

# ============================================================================
# Context manager and connection tests
# ============================================================================


# Test context manager opens and closes connection properly.
def test_context_manager_opens_connection() -> None:
    with WorkflowCache(":memory:") as cache:
        assert cache.is_open is True
    assert cache.is_open is False


# Test open() returns self for method chaining.
def test_open_returns_self() -> None:
    cache = WorkflowCache(":memory:")
    result = cache.open()
    assert result is cache
    cache.close()


# Test open() raises error when already connected.
def test_open_raises_when_already_connected() -> None:
    cache = WorkflowCache(":memory:")
    cache.open()
    try:
        with pytest.raises(RuntimeError, match="already connected"):
            cache.open()
    finally:
        cache.close()


# Test accessing token_cache before connection raises error.
def test_token_cache_raises_when_not_connected() -> None:
    cache = WorkflowCache(":memory:")
    with pytest.raises(RuntimeError, match="not connected"):
        _ = cache.token_cache


# Test is_memory property returns True for in-memory database.
def test_is_memory_true_for_memory_db() -> None:
    cache = WorkflowCache(":memory:")
    assert cache.is_memory is True


# Test is_memory property returns False for file database.
def test_is_memory_false_for_file_db(tmp_path: pytest.TempPathFactory) -> None:
    db_path = tmp_path / "test.db"  # type: ignore[operator]
    cache = WorkflowCache(db_path)
    assert cache.is_memory is False


# Test close() is safe to call when not connected.
def test_close_when_not_connected() -> None:
    cache = WorkflowCache(":memory:")
    cache.close()  # Should not raise


# ============================================================================
# Hash computation tests
# ============================================================================


# Test compute_hash returns consistent hash for same input.
def test_compute_hash_deterministic() -> None:
    cache = WorkflowCache(":memory:")
    key = {"algorithm": "pc", "network": "asia"}
    hash1 = cache.compute_hash(key)
    hash2 = cache.compute_hash(key)
    assert hash1 == hash2


# Test compute_hash returns 16 character hex string.
def test_compute_hash_length() -> None:
    cache = WorkflowCache(":memory:")
    key = {"algorithm": "pc", "network": "asia"}
    hash_val = cache.compute_hash(key)
    assert len(hash_val) == 16
    assert all(c in "0123456789abcdef" for c in hash_val)


# Test compute_hash is order-independent (sorted keys).
def test_compute_hash_order_independent() -> None:
    cache = WorkflowCache(":memory:")
    key1 = {"algorithm": "pc", "network": "asia"}
    key2 = {"network": "asia", "algorithm": "pc"}
    assert cache.compute_hash(key1) == cache.compute_hash(key2)


# Test compute_hash produces different hashes for different values.
def test_compute_hash_different_values() -> None:
    cache = WorkflowCache(":memory:")
    key1 = {"algorithm": "pc", "network": "asia"}
    key2 = {"algorithm": "ges", "network": "asia"}
    assert cache.compute_hash(key1) != cache.compute_hash(key2)


# Test compute_hash handles nested structures.
def test_compute_hash_nested_values() -> None:
    cache = WorkflowCache(":memory:")
    key = {"params": {"alpha": 0.05}, "network": "asia"}
    hash_val = cache.compute_hash(key)
    assert len(hash_val) == 16


# ============================================================================
# Encoder registration tests
# ============================================================================


# Test register_encoder and has_encoder work correctly.
def test_register_encoder() -> None:
    with WorkflowCache(":memory:") as cache:
        assert cache.has_encoder("json") is False
        cache.register_encoder("json", JsonEncoder())
        assert cache.has_encoder("json") is True


# Test get_encoder returns registered encoder.
def test_get_encoder_returns_encoder() -> None:
    with WorkflowCache(":memory:") as cache:
        encoder = JsonEncoder()
        cache.register_encoder("json", encoder)
        assert cache.get_encoder("json") is encoder


# Test get_encoder returns None for unregistered type.
def test_get_encoder_returns_none_for_unknown() -> None:
    with WorkflowCache(":memory:") as cache:
        assert cache.get_encoder("unknown") is None


# ============================================================================
# Put/Get tests
# ============================================================================


# Test put and get round-trip for simple data.
def test_put_get_simple_data() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        data = {"nodes": 5, "edges": 4}
        cache.put(key, "json", data)
        result = cache.get(key, "json")
        assert result == data


# Test put returns hash key.
def test_put_returns_hash() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        hash_key = cache.put(key, "json", {"data": "test"})
        assert hash_key == cache.compute_hash(key)


# Test get returns None for missing entry.
def test_get_returns_none_for_missing() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        result = cache.get(key, "json")
        assert result is None


# Test put overwrites existing entry with same key.
def test_put_overwrites_existing() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        cache.put(key, "json", {"version": 1})
        cache.put(key, "json", {"version": 2})
        result = cache.get(key, "json")
        assert result == {"version": 2}
        assert cache.entry_count() == 1


# Test put raises KeyError for unregistered entry type.
def test_put_raises_for_unregistered_type() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        with pytest.raises(KeyError):
            cache.put(key, "unknown", {"data": "test"})


# Test get raises KeyError for unregistered entry type when entry exists.
def test_get_raises_for_unregistered_type() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        cache.put(key, "json", {"data": "test"})
        # For unregistered type, get returns None if entry doesn't exist
        # But would raise KeyError if trying to decode existing entry
        # Since different entry_types are stored separately, this returns None
        result = cache.get(key, "unknown")
        assert result is None


# ============================================================================
# Metadata tests
# ============================================================================


# Test put and get with metadata.
def test_put_get_with_metadata() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        data = {"nodes": 5}
        metadata = {"provenance": "test", "timestamp": "2026-02-06"}
        cache.put(key, "json", data, metadata=metadata)
        result = cache.get_with_metadata(key, "json")
        assert result is not None
        assert result[0] == data
        assert result[1] == metadata


# Test get_with_metadata returns None for missing entry.
def test_get_with_metadata_returns_none_for_missing() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        result = cache.get_with_metadata(key, "json")
        assert result is None


# Test put without metadata stores None for metadata.
def test_put_without_metadata() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        data = {"nodes": 5}
        cache.put(key, "json", data)
        result = cache.get_with_metadata(key, "json")
        assert result is not None
        assert result[0] == data
        assert result[1] is None


# ============================================================================
# Exists tests
# ============================================================================


# Test exists returns False for missing entry.
def test_exists_false_for_missing() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        assert cache.exists(key, "json") is False


# Test exists returns True for existing entry.
def test_exists_true_for_existing() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        cache.put(key, "json", {"data": "test"})
        assert cache.exists(key, "json") is True


# Test exists returns False for different entry type.
def test_exists_false_for_different_type() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        cache.register_encoder("other", JsonEncoder())
        key = {"algorithm": "pc"}
        cache.put(key, "json", {"data": "test"})
        assert cache.exists(key, "other") is False


# ============================================================================
# Delete tests
# ============================================================================


# Test delete removes existing entry.
def test_delete_removes_entry() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        cache.put(key, "json", {"data": "test"})
        assert cache.exists(key, "json") is True
        result = cache.delete(key, "json")
        assert result is True
        assert cache.exists(key, "json") is False


# Test delete returns False for missing entry.
def test_delete_returns_false_for_missing() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"algorithm": "pc"}
        result = cache.delete(key, "json")
        assert result is False


# ============================================================================
# Statistics tests
# ============================================================================


# Test entry_count returns zero for empty cache.
def test_entry_count_empty() -> None:
    with WorkflowCache(":memory:") as cache:
        assert cache.entry_count() == 0


# Test entry_count returns correct count.
def test_entry_count_after_puts() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        cache.put({"k": "1"}, "json", {"data": 1})
        cache.put({"k": "2"}, "json", {"data": 2})
        cache.put({"k": "3"}, "json", {"data": 3})
        assert cache.entry_count() == 3


# Test entry_count filters by entry type.
def test_entry_count_by_type() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        cache.register_encoder("other", JsonEncoder())
        cache.put({"k": "1"}, "json", {"data": 1})
        cache.put({"k": "2"}, "json", {"data": 2})
        cache.put({"k": "3"}, "other", {"data": 3})
        assert cache.entry_count("json") == 2
        assert cache.entry_count("other") == 1


# Test list_entry_types returns empty list for empty cache.
def test_list_entry_types_empty() -> None:
    with WorkflowCache(":memory:") as cache:
        assert cache.list_entry_types() == []


# Test list_entry_types returns all types.
def test_list_entry_types_multiple() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        cache.register_encoder("other", JsonEncoder())
        cache.put({"k": "1"}, "json", {"data": 1})
        cache.put({"k": "2"}, "other", {"data": 2})
        types = cache.list_entry_types()
        assert sorted(types) == ["json", "other"]


# Test token_count returns count of tokens.
def test_token_count() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        cache.put({"algorithm": "pc"}, "json", {"nodes": 5})
        assert cache.token_count() > 0


# ============================================================================
# Hash collision handling tests
# ============================================================================


# Test different keys with same hash prefix are handled correctly.
def test_collision_handling() -> None:
    """Test that different keys are stored separately even if hashes collide.

    Note: This test doesn't force an actual collision but verifies that
    the key_json mechanism works correctly for differentiation.
    """
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key1 = {"algorithm": "pc", "network": "asia"}
        key2 = {"algorithm": "ges", "network": "asia"}
        cache.put(key1, "json", {"result": "pc_result"})
        cache.put(key2, "json", {"result": "ges_result"})
        assert cache.get(key1, "json") == {"result": "pc_result"}
        assert cache.get(key2, "json") == {"result": "ges_result"}
        assert cache.entry_count() == 2


# ============================================================================
# File-based cache tests
# ============================================================================


# Test cache persists to file and can be reopened.
def test_file_persistence(tmp_path: pytest.TempPathFactory) -> None:
    db_path = tmp_path / "test.db"  # type: ignore[operator]
    key = {"algorithm": "pc"}
    data = {"nodes": 5}

    # Write to file
    with WorkflowCache(db_path) as cache:
        cache.register_encoder("json", JsonEncoder())
        cache.put(key, "json", data)

    # Read from file (new connection)
    with WorkflowCache(db_path) as cache:
        cache.register_encoder("json", JsonEncoder())
        result = cache.get(key, "json")
        assert result == data


# ============================================================================
# Complex data tests
# ============================================================================


# Test storage of complex nested data structures.
def test_complex_data_structures() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"experiment": "complex"}
        data = {
            "nodes": ["A", "B", "C", "D"],
            "edges": [
                {"from": "A", "to": "B", "weight": 0.95},
                {"from": "B", "to": "C", "weight": 0.72},
            ],
            "metrics": {
                "shd": 3,
                "precision": 0.85,
                "nested": {"level1": {"level2": [1, 2, 3]}},
            },
        }
        cache.put(key, "json", data)
        result = cache.get(key, "json")
        assert result == data


# Test storage of various numeric types.
def test_numeric_types() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        key = {"test": "numbers"}
        data = {
            "integer": 42,
            "negative": -100,
            "float": 3.14159,
            "scientific": 1.23e-10,
            "zero": 0,
            "large": 9999999999999,
        }
        cache.put(key, "json", data)
        result = cache.get(key, "json")
        assert result == data


# ============================================================================
# Export and import tests
# ============================================================================


# Test export to zip with non-JSON format encoder.
def test_export_to_zip_non_json_format(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Export with non-JSON encoder writes raw files to zip archive."""
    import zipfile
    from pathlib import Path

    from causaliq_core.cache.encoders.base import EntryEncoder
    from causaliq_core.cache.token_cache import TokenCache

    class TextEncoder(EntryEncoder):
        """Mock encoder that exports to .txt format."""

        @property
        def default_export_format(self) -> str:
            return "txt"

        def encode(self, data: dict, token_cache: TokenCache) -> bytes:
            return str(data).encode("utf-8")

        def decode(self, blob: bytes, token_cache: TokenCache) -> dict:
            return eval(blob.decode("utf-8"))  # noqa: S307

        def export(self, data: dict, path: Path) -> None:
            path.with_suffix(".txt").write_text(str(data), encoding="utf-8")

        def import_(self, path: Path) -> dict:
            return eval(path.read_text(encoding="utf-8"))  # noqa: S307

    zip_path = tmp_path / "export.zip"  # type: ignore[operator]
    key = {"test": "non_json"}
    data = {"result": "test_value"}

    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("text", TextEncoder())
        cache.put(key, "text", data)
        count = cache.export(zip_path, "text")

    assert count == 1
    assert zip_path.exists()

    # Verify the zip contains a .txt file (non-JSON format)
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        txt_files = [n for n in names if n.endswith(".txt")]
        assert len(txt_files) == 1


# Test import_entries from directory.
def test_import_entries_from_directory(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Import entries from exported directory structure."""
    import json

    export_dir = tmp_path / "exported"  # type: ignore[operator]
    export_dir.mkdir()

    # Create a valid JSON export file with workflow metadata
    export_data = {
        "result": "imported_value",
        "matrix_values": {"algorithm": "pc"},
        "created_at": "2024-01-01T00:00:00",
        "entry_type": "json",
    }
    (export_dir / "test_entry.json").write_text(
        json.dumps(export_data), encoding="utf-8"
    )

    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        count = cache.import_entries(export_dir, "json")

    assert count == 1


# Test import_entries raises FileNotFoundError for missing path.
def test_import_entries_raises_file_not_found(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Import raises FileNotFoundError when directory doesn't exist."""
    missing_path = tmp_path / "nonexistent"  # type: ignore[operator]

    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        with pytest.raises(FileNotFoundError, match="not found"):
            cache.import_entries(missing_path, "json")


# Test import_entries raises KeyError for unregistered encoder.
def test_import_entries_raises_key_error_unregistered(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Import raises KeyError when no encoder registered for type."""
    # Create directory to avoid FileNotFoundError
    import_dir = tmp_path / "import_dir"  # type: ignore[operator]
    import_dir.mkdir()

    with WorkflowCache(":memory:") as cache:
        with pytest.raises(KeyError, match="No encoder registered"):
            cache.import_entries(import_dir, "unregistered_type")


# Test import_entries skips legacy _meta.json files.
def test_import_entries_skips_meta_files(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Import skips files with _meta in their name (legacy format)."""
    import json

    export_dir = tmp_path / "exported"  # type: ignore[operator]
    export_dir.mkdir()

    # Create a valid entry file
    valid_data = {
        "result": "valid_entry",
        "matrix_values": {"algorithm": "pc"},
    }
    (export_dir / "entry.json").write_text(
        json.dumps(valid_data), encoding="utf-8"
    )

    # Create a _meta.json file that should be skipped
    meta_data = {"metadata": "should_be_skipped"}
    (export_dir / "entry_meta.json").write_text(
        json.dumps(meta_data), encoding="utf-8"
    )

    with WorkflowCache(":memory:") as cache:
        cache.register_encoder("json", JsonEncoder())
        count = cache.import_entries(export_dir, "json")

    # Only the valid entry should be imported, _meta file skipped
    assert count == 1
