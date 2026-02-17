"""Unit tests for WorkflowCache class with CacheEntry API."""

import pytest

from causaliq_workflow.cache import (
    CacheEntry,
    MatrixSchemaError,
    WorkflowCache,
)

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
# Put/Get tests
# ============================================================================


# Test put and get round-trip for simple entry.
def test_put_get_simple_entry() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        entry = CacheEntry()
        entry.metadata["nodes"] = 5
        entry.add_object("result", "json", '{"status": "ok"}')

        cache.put(key, entry)
        result = cache.get(key)

        assert result is not None
        assert result.metadata["nodes"] == 5
        assert result.has_object("result")


# Test put returns hash key.
def test_put_returns_hash() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        entry = CacheEntry(metadata={"data": "test"})
        hash_key = cache.put(key, entry)
        assert hash_key == cache.compute_hash(key)


# Test get returns None for missing entry.
def test_get_returns_none_for_missing() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        result = cache.get(key)
        assert result is None


# Test put overwrites existing entry with same key.
def test_put_overwrites_existing() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        cache.put(key, CacheEntry(metadata={"version": 1}))
        cache.put(key, CacheEntry(metadata={"version": 2}))
        result = cache.get(key)
        assert result is not None
        assert result.metadata == {"version": 2}
        assert cache.entry_count() == 1


# Test get_or_create returns new entry for missing key.
def test_get_or_create_returns_new_for_missing() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        entry = cache.get_or_create(key)
        assert entry.metadata == {}
        assert entry.objects == {}


# Test get_or_create returns existing entry.
def test_get_or_create_returns_existing() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        original = CacheEntry(metadata={"original": True})
        cache.put(key, original)
        entry = cache.get_or_create(key)
        assert entry.metadata == {"original": True}


# ============================================================================
# CacheEntry object tests
# ============================================================================


# Test entry with multiple objects.
def test_entry_with_multiple_objects() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        entry = CacheEntry()
        entry.metadata["step"] = "discovery"
        entry.add_object("graph", "graphml", "<graphml>...</graphml>")
        entry.add_object("confidences", "json", '{"A->B": 0.95}')
        entry.add_object("trace", "json", '{"iterations": 100}')

        cache.put(key, entry)
        result = cache.get(key)

        assert result is not None
        assert result.metadata["step"] == "discovery"
        assert len(result.objects) == 3
        assert result.get_object("graph") is not None
        assert result.get_object("graph").type == "graphml"
        assert result.get_object("confidences").content == '{"A->B": 0.95}'


# Test entry object_names method.
def test_entry_object_names() -> None:
    entry = CacheEntry()
    entry.add_object("alpha", "json", "{}")
    entry.add_object("beta", "graphml", "<g/>")
    names = entry.object_names()
    assert sorted(names) == ["alpha", "beta"]


# Test entry remove_object.
def test_entry_remove_object() -> None:
    entry = CacheEntry()
    entry.add_object("temp", "json", "{}")
    assert entry.has_object("temp") is True
    result = entry.remove_object("temp")
    assert result is True
    assert entry.has_object("temp") is False


# Test entry remove_object returns false for missing.
def test_entry_remove_object_missing() -> None:
    entry = CacheEntry()
    result = entry.remove_object("nonexistent")
    assert result is False


# Test CacheEntry.from_action_result factory.
def test_cache_entry_from_action_result() -> None:
    metadata = {"node_count": 5, "edge_count": 4}
    objects = [
        {
            "type": "graphml",
            "name": "graph",
            "content": "<graphml>...</graphml>",
        },
        {"type": "json", "name": "data", "content": '{"key": "value"}'},
    ]
    entry = CacheEntry.from_action_result(metadata, objects)

    assert entry.metadata["node_count"] == 5
    assert entry.has_object("graph")
    assert entry.get_object("graph").type == "graphml"
    assert entry.has_object("data")


# Test CacheEntry.to_action_result round-trip.
def test_cache_entry_to_action_result() -> None:
    entry = CacheEntry(metadata={"test": True})
    entry.add_object("output", "json", '{"result": 1}')

    metadata, objects_list = entry.to_action_result()

    assert metadata == {"test": True}
    assert len(objects_list) == 1
    assert objects_list[0]["name"] == "output"
    assert objects_list[0]["type"] == "json"


# ============================================================================
# Exists tests
# ============================================================================


# Test exists returns False for missing entry.
def test_exists_false_for_missing() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        assert cache.exists(key) is False


# Test exists returns True for existing entry.
def test_exists_true_for_existing() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        cache.put(key, CacheEntry(metadata={"data": "test"}))
        assert cache.exists(key) is True


# ============================================================================
# Delete tests
# ============================================================================


# Test delete removes existing entry.
def test_delete_removes_entry() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        cache.put(key, CacheEntry(metadata={"data": "test"}))
        assert cache.exists(key) is True
        result = cache.delete(key)
        assert result is True
        assert cache.exists(key) is False


# Test delete returns False for missing entry.
def test_delete_returns_false_for_missing() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        result = cache.delete(key)
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
        cache.put({"k": "1"}, CacheEntry(metadata={"v": 1}))
        cache.put({"k": "2"}, CacheEntry(metadata={"v": 2}))
        cache.put({"k": "3"}, CacheEntry(metadata={"v": 3}))
        assert cache.entry_count() == 3


# Test list_entries returns entry details.
def test_list_entries() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put(
            {"algo": "pc", "data": "asia"}, CacheEntry(metadata={"v": 1})
        )
        cache.put(
            {"algo": "ges", "data": "asia"}, CacheEntry(metadata={"v": 2})
        )

        entries = cache.list_entries()
        assert len(entries) == 2
        # Entries have matrix_values, hash, created_at
        assert all("matrix_values" in e for e in entries)
        assert all("hash" in e for e in entries)
        assert all("created_at" in e for e in entries)


# Test token_count returns count of tokens.
def test_token_count() -> None:
    with WorkflowCache(":memory:") as cache:
        entry = CacheEntry(metadata={"algorithm": "pc", "nodes": 5})
        cache.put({"algorithm": "pc"}, entry)
        assert cache.token_count() > 0


# ============================================================================
# Hash collision handling tests
# ============================================================================


# Test different keys are stored separately.
def test_different_keys_stored_separately() -> None:
    with WorkflowCache(":memory:") as cache:
        key1 = {"algorithm": "pc", "network": "asia"}
        key2 = {"algorithm": "ges", "network": "asia"}
        cache.put(key1, CacheEntry(metadata={"result": "pc_result"}))
        cache.put(key2, CacheEntry(metadata={"result": "ges_result"}))

        result1 = cache.get(key1)
        result2 = cache.get(key2)

        assert result1 is not None
        assert result2 is not None
        assert result1.metadata["result"] == "pc_result"
        assert result2.metadata["result"] == "ges_result"
        assert cache.entry_count() == 2


# ============================================================================
# File-based cache tests
# ============================================================================


# Test cache persists to file and can be reopened.
def test_file_persistence(tmp_path: pytest.TempPathFactory) -> None:
    db_path = tmp_path / "test.db"  # type: ignore[operator]
    key = {"algorithm": "pc"}

    # Write to file
    with WorkflowCache(db_path) as cache:
        entry = CacheEntry(metadata={"nodes": 5})
        entry.add_object("graph", "graphml", "<graphml/>")
        cache.put(key, entry)

    # Read from file (new connection)
    with WorkflowCache(db_path) as cache:
        result = cache.get(key)
        assert result is not None
        assert result.metadata["nodes"] == 5
        assert result.has_object("graph")


# ============================================================================
# Complex data tests
# ============================================================================


# Test storage of complex nested metadata.
def test_complex_metadata() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"experiment": "complex"}
        entry = CacheEntry(
            metadata={
                "nodes": ["A", "B", "C", "D"],
                "metrics": {
                    "shd": 3,
                    "precision": 0.85,
                    "nested": {"level1": {"level2": [1, 2, 3]}},
                },
            }
        )
        cache.put(key, entry)
        result = cache.get(key)
        assert result is not None
        assert result.metadata["metrics"]["nested"]["level1"]["level2"] == [
            1,
            2,
            3,
        ]


# Test storage of various numeric types in metadata.
def test_numeric_types_in_metadata() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"test": "numbers"}
        entry = CacheEntry(
            metadata={
                "integer": 42,
                "negative": -100,
                "float": 3.14159,
                "scientific": 1.23e-10,
                "zero": 0,
                "large": 9999999999999,
            }
        )
        cache.put(key, entry)
        result = cache.get(key)
        assert result is not None
        assert result.metadata["integer"] == 42
        assert result.metadata["float"] == 3.14159


# ============================================================================
# Matrix schema validation tests
# ============================================================================


# Test get_matrix_schema returns None for empty cache.
def test_get_matrix_schema_empty_cache() -> None:
    with WorkflowCache(":memory:") as cache:
        schema = cache.get_matrix_schema()
        assert schema is None


# Test get_matrix_schema returns correct keys from entries.
def test_get_matrix_schema_returns_keys() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put(
            {"algorithm": "pc", "dataset": "asia"},
            CacheEntry(),
        )
        schema = cache.get_matrix_schema()
        assert schema == {"algorithm", "dataset"}


# Test get_matrix_schema returns consistent schema with multiple entries.
def test_get_matrix_schema_multiple_entries() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put(
            {"algo": "pc", "data": "asia"}, CacheEntry(metadata={"v": 1})
        )
        cache.put(
            {"algo": "ges", "data": "asia"}, CacheEntry(metadata={"v": 2})
        )
        cache.put(
            {"algo": "pc", "data": "cancer"}, CacheEntry(metadata={"v": 3})
        )
        schema = cache.get_matrix_schema()
        assert schema == {"algo", "data"}


# Test validate_matrix_keys passes for empty cache.
def test_validate_matrix_keys_empty_cache() -> None:
    with WorkflowCache(":memory:") as cache:
        # Should not raise - any keys valid for empty cache
        cache.validate_matrix_keys({"algorithm": "pc", "dataset": "asia"})


# Test validate_matrix_keys passes for matching keys.
def test_validate_matrix_keys_matching() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put({"algorithm": "pc", "dataset": "asia"}, CacheEntry())
        # Should not raise - keys match
        cache.validate_matrix_keys({"algorithm": "ges", "dataset": "cancer"})


# Test validate_matrix_keys raises for mismatched keys.
def test_validate_matrix_keys_mismatch() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put({"algorithm": "pc", "dataset": "asia"}, CacheEntry())
        with pytest.raises(MatrixSchemaError, match="Matrix keys mismatch"):
            cache.validate_matrix_keys({"method": "pc", "network": "asia"})


# Test validate_matrix_keys raises for subset of keys.
def test_validate_matrix_keys_subset() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put({"algorithm": "pc", "dataset": "asia"}, CacheEntry())
        with pytest.raises(MatrixSchemaError, match="Matrix keys mismatch"):
            cache.validate_matrix_keys({"algorithm": "pc"})


# Test validate_matrix_keys raises for superset of keys.
def test_validate_matrix_keys_superset() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put({"algorithm": "pc"}, CacheEntry())
        with pytest.raises(MatrixSchemaError, match="Matrix keys mismatch"):
            cache.validate_matrix_keys({"algorithm": "pc", "extra": "key"})


# Test put enforces matrix schema validation.
def test_put_enforces_schema_validation() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put(
            {"algorithm": "pc", "dataset": "asia"},
            CacheEntry(metadata={"v": 1}),
        )
        with pytest.raises(MatrixSchemaError, match="Matrix keys mismatch"):
            cache.put({"method": "ges"}, CacheEntry(metadata={"v": 2}))


# Test MatrixSchemaError can be imported from cache module.
def test_matrix_schema_error_importable() -> None:
    error = MatrixSchemaError("Test error message")
    assert str(error) == "Test error message"
    assert isinstance(error, Exception)


# ============================================================================
# Legacy compatibility tests
# ============================================================================


# Test put_from_action stores action result format.
def test_put_from_action() -> None:
    with WorkflowCache(":memory:") as cache:
        key = {"algorithm": "pc"}
        metadata = {"node_count": 5}
        objects = [
            {"type": "graphml", "name": "graph", "content": "<graphml/>"},
            {"type": "json", "name": "data", "content": '{"key": "val"}'},
        ]
        hash_key = cache.put_from_action(key, metadata, objects)
        assert hash_key == cache.compute_hash(key)

        result = cache.get(key)
        assert result is not None
        assert result.metadata["node_count"] == 5
        assert result.has_object("graph")
        assert result.has_object("data")


# ============================================================================
# Compressor tests
# ============================================================================


# Test set_compressor sets compressor on token cache.
def test_set_compressor() -> None:
    from causaliq_core.cache.compressors import JsonCompressor

    with WorkflowCache(":memory:") as cache:
        # Default compressor is set on open()
        assert cache.token_cache.has_compressor()

        # Set a new compressor
        new_compressor = JsonCompressor()
        cache.set_compressor(new_compressor)
        assert cache.token_cache.get_compressor() is new_compressor


# ============================================================================
# Matrix schema inconsistency tests
# ============================================================================


# Test get_matrix_schema raises for inconsistent schemas.
def test_get_matrix_schema_inconsistent_raises() -> None:
    with WorkflowCache(":memory:") as cache:
        # Add first entry with schema {"algorithm", "dataset"}
        entry1 = CacheEntry(metadata={"v": 1})
        cache.put({"algorithm": "pc", "dataset": "asia"}, entry1)

        # Manually insert entry with different schema {"method", "network"}
        # must bypass validation by inserting directly into token_cache
        key2 = {"method": "fci", "network": "alarm"}
        hash_val = cache.compute_hash(key2)
        key_json = cache._key_json(key2)
        # Simply insert raw bytes with the different key_json
        cache.token_cache.put_data(hash_val, b"{}", key_json=key_json)

        with pytest.raises(MatrixSchemaError, match="Inconsistent"):
            cache.get_matrix_schema()


# ============================================================================
# Import entries tests
# ============================================================================


# Test import_entries delegates to import module.
def test_import_entries_delegates(tmp_path) -> None:
    import json

    # Create directory structure manually
    entry_dir = tmp_path / "entry"
    entry_dir.mkdir()
    (entry_dir / "data.json").write_text('{"key": "value"}')
    (entry_dir / "_meta.json").write_text(
        json.dumps(
            {
                "matrix_values": {"test": "import"},
                "created_at": "2026-01-01T00:00:00Z",
                "metadata": {"imported": True},
            }
        )
    )

    with WorkflowCache(":memory:") as cache:
        count = cache.import_entries(tmp_path)
        assert count == 1

        entry = cache.get({"test": "import"})
        assert entry is not None
        assert entry.metadata.get("imported") is True
