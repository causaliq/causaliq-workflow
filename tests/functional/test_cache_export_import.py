"""Functional tests for cache export and import.

Tests cache export/import with real filesystem operations using
temporary directories.
"""

import json
import zipfile
from pathlib import Path

import pytest

from causaliq_workflow.cache import CacheEntry, WorkflowCache
from causaliq_workflow.cache.entry import CacheObject
from causaliq_workflow.cache.export import (
    export_entries,
    write_entry_to_dir,
    write_entry_to_zip,
)
from causaliq_workflow.cache.import_ import (
    import_entries,
)

# =============================================================================
# write_entry_to_dir tests
# =============================================================================


# Test write_entry_to_dir creates directory structure.
def test_write_entry_to_dir_creates_directory(tmp_path: Path) -> None:
    """Test that write_entry_to_dir creates the directory structure."""
    entry_path = Path("asia/pc")
    entry_info = {
        "matrix_values": {"dataset": "asia", "method": "pc"},
        "created_at": "2026-01-01T00:00:00Z",
    }
    objects = {
        "graph": {"type": "graphml", "content": "<graphml/>"},
    }
    metadata = {"node_count": 5}

    write_entry_to_dir(tmp_path, entry_path, entry_info, objects, metadata)

    assert (tmp_path / "asia" / "pc").exists()
    assert (tmp_path / "asia" / "pc").is_dir()


# Test write_entry_to_dir writes object files correctly.
def test_write_entry_to_dir_writes_objects(tmp_path: Path) -> None:
    """Test write_entry_to_dir writes object files with correct content."""
    entry_path = Path("test")
    entry_info = {
        "matrix_values": {"x": "1"},
        "created_at": "2026-01-01T00:00:00Z",
    }
    objects = {
        "graph": {"type": "graphml", "content": "<graphml>test</graphml>"},
        "data": {"type": "json", "content": '{"key": "value"}'},
    }
    metadata = {}

    write_entry_to_dir(tmp_path, entry_path, entry_info, objects, metadata)

    graph_path = tmp_path / "test" / "graph.graphml"
    assert graph_path.exists()
    assert graph_path.read_text() == "<graphml>test</graphml>"

    data_path = tmp_path / "test" / "data.json"
    assert data_path.exists()
    assert data_path.read_text() == '{"key": "value"}'


# Test write_entry_to_dir writes _meta.json correctly.
def test_write_entry_to_dir_writes_metadata(tmp_path: Path) -> None:
    """Test that write_entry_to_dir writes _meta.json with correct content."""
    entry_path = Path("entry")
    entry_info = {
        "matrix_values": {"dataset": "asia"},
        "created_at": "2026-02-17T10:00:00Z",
    }
    objects = {"result": {"type": "json", "content": "{}"}}
    metadata = {"status": "success", "elapsed": 1.5}

    write_entry_to_dir(tmp_path, entry_path, entry_info, objects, metadata)

    meta_path = tmp_path / "entry" / "_meta.json"
    assert meta_path.exists()

    meta_content = json.loads(meta_path.read_text())
    assert meta_content["matrix_values"] == {"dataset": "asia"}
    assert meta_content["created_at"] == "2026-02-17T10:00:00Z"
    assert meta_content["metadata"] == {"status": "success", "elapsed": 1.5}


# =============================================================================
# write_entry_to_zip tests
# =============================================================================


# Test write_entry_to_zip writes files to archive.
def test_write_entry_to_zip_writes_files(tmp_path: Path) -> None:
    """Test that write_entry_to_zip writes files to zip archive."""
    zip_path = tmp_path / "test.zip"
    entry_path = Path("asia/pc")
    entry_info = {
        "matrix_values": {"dataset": "asia", "method": "pc"},
        "created_at": "2026-01-01T00:00:00Z",
    }
    objects = {
        "graph": {"type": "graphml", "content": "<graphml>content</graphml>"},
    }
    metadata = {"count": 10}

    with zipfile.ZipFile(zip_path, "w") as zf:
        write_entry_to_zip(zf, entry_path, entry_info, objects, metadata)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert "asia/pc/graph.graphml" in names
        assert "asia/pc/_meta.json" in names

        content = zf.read("asia/pc/graph.graphml").decode("utf-8")
        assert content == "<graphml>content</graphml>"


# Test write_entry_to_zip writes correct metadata.
def test_write_entry_to_zip_writes_metadata(tmp_path: Path) -> None:
    """Test that write_entry_to_zip writes _meta.json correctly."""
    zip_path = tmp_path / "test.zip"
    entry_path = Path("test")
    entry_info = {
        "matrix_values": {"x": "1"},
        "created_at": "2026-02-17T12:00:00Z",
    }
    objects = {"data": {"type": "json", "content": "{}"}}
    metadata = {"key": "value"}

    with zipfile.ZipFile(zip_path, "w") as zf:
        write_entry_to_zip(zf, entry_path, entry_info, objects, metadata)

    with zipfile.ZipFile(zip_path, "r") as zf:
        meta_content = json.loads(zf.read("test/_meta.json").decode("utf-8"))
        assert meta_content["matrix_values"] == {"x": "1"}
        assert meta_content["metadata"] == {"key": "value"}


# =============================================================================
# export_entries tests
# =============================================================================


# Test export_entries exports to directory structure.
def test_export_entries_to_directory(tmp_path: Path) -> None:
    """Test export_entries creates directory structure with files."""
    with WorkflowCache(":memory:") as cache:
        # Add an entry
        entry = CacheEntry(metadata={"status": "success"})
        entry.objects["graph"] = CacheObject(
            type="graphml", content="<graphml>test</graphml>"
        )
        cache.put({"dataset": "asia", "method": "pc"}, entry)

        # Export
        output_dir = tmp_path / "export"
        count = export_entries(cache, output_dir, matrix_keys=["dataset"])

        assert count == 1
        assert (output_dir / "asia" / "graph.graphml").exists()
        assert (output_dir / "asia" / "_meta.json").exists()


# Test export_entries exports to zip file.
def test_export_entries_to_zip(tmp_path: Path) -> None:
    """Test export_entries creates zip archive with files."""
    with WorkflowCache(":memory:") as cache:
        # Add an entry
        entry = CacheEntry(metadata={"count": 5})
        entry.objects["result"] = CacheObject(
            type="json", content='{"data": true}'
        )
        cache.put({"algorithm": "fci"}, entry)

        # Export to zip
        zip_path = tmp_path / "export.zip"
        count = export_entries(cache, zip_path)

        assert count == 1
        assert zip_path.exists()

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert any("result.json" in n for n in names)
            assert any("_meta.json" in n for n in names)


# Test export_entries returns zero for empty cache.
def test_export_entries_empty_cache(tmp_path: Path) -> None:
    """Test export_entries returns 0 when cache is empty."""
    with WorkflowCache(":memory:") as cache:
        output_dir = tmp_path / "empty_export"
        count = export_entries(cache, output_dir)

        assert count == 0


# Test export_entries skips entries without objects.
def test_export_entries_skips_empty_entries(tmp_path: Path) -> None:
    """Test export_entries skips entries with no objects."""
    with WorkflowCache(":memory:") as cache:
        # Add entry without objects
        entry = CacheEntry(metadata={"empty": True})
        cache.put({"test": "empty"}, entry)

        output_dir = tmp_path / "export"
        count = export_entries(cache, output_dir)

        assert count == 0


# Test export_entries with multiple entries.
def test_export_entries_multiple_entries(tmp_path: Path) -> None:
    """Test export_entries handles multiple entries."""
    with WorkflowCache(":memory:") as cache:
        # Add multiple entries
        for i in range(3):
            entry = CacheEntry(metadata={"index": i})
            entry.objects["data"] = CacheObject(
                type="json", content=f'{{"value": {i}}}'
            )
            cache.put({"id": str(i)}, entry)

        output_dir = tmp_path / "multi_export"
        count = export_entries(cache, output_dir)

        assert count == 3


# =============================================================================
# import_entries tests
# =============================================================================


# Test import_entries imports from directory.
def test_import_entries_from_directory(tmp_path: Path) -> None:
    """Test import_entries reads entries from directory structure."""
    # Create directory structure manually
    entry_dir = tmp_path / "source" / "test_entry"
    entry_dir.mkdir(parents=True)

    (entry_dir / "graph.graphml").write_text("<graphml>imported</graphml>")
    (entry_dir / "_meta.json").write_text(
        json.dumps(
            {
                "matrix_values": {"key": "value"},
                "created_at": "2026-01-01T00:00:00Z",
                "metadata": {"imported": True},
            }
        )
    )

    # Import into cache
    with WorkflowCache(":memory:") as cache:
        count = import_entries(cache, tmp_path / "source")

        assert count == 1

        # Verify entry was imported
        entry = cache.get({"key": "value"})
        assert entry is not None
        assert "graph" in entry.objects
        assert entry.objects["graph"].content == "<graphml>imported</graphml>"
        assert entry.metadata.get("imported") is True


# Test import_entries imports from zip file.
def test_import_entries_from_zip(tmp_path: Path) -> None:
    """Test import_entries reads entries from zip archive."""
    # Create zip file manually
    zip_path = tmp_path / "import.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("entry/data.json", '{"imported": true}')
        zf.writestr(
            "entry/_meta.json",
            json.dumps(
                {
                    "matrix_values": {"source": "zip"},
                    "created_at": "2026-02-17T00:00:00Z",
                    "metadata": {"from_zip": True},
                }
            ),
        )

    # Import into cache
    with WorkflowCache(":memory:") as cache:
        count = import_entries(cache, zip_path)

        assert count == 1

        entry = cache.get({"source": "zip"})
        assert entry is not None
        assert "data" in entry.objects
        assert entry.objects["data"].type == "json"


# Test import_entries raises FileNotFoundError for missing directory.
def test_import_entries_missing_directory(tmp_path: Path) -> None:
    """Test import_entries raises FileNotFoundError for missing path."""
    with WorkflowCache(":memory:") as cache:
        with pytest.raises(FileNotFoundError):
            import_entries(cache, tmp_path / "nonexistent")


# Test import_entries raises FileNotFoundError for missing zip.
def test_import_entries_missing_zip(tmp_path: Path) -> None:
    """Test import_entries raises FileNotFoundError for missing zip."""
    with WorkflowCache(":memory:") as cache:
        with pytest.raises(FileNotFoundError):
            import_entries(cache, tmp_path / "nonexistent.zip")


# Test import_entries returns zero for empty directory.
def test_import_entries_empty_directory(tmp_path: Path) -> None:
    """Test import_entries returns 0 for directory with no entries."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with WorkflowCache(":memory:") as cache:
        count = import_entries(cache, empty_dir)
        assert count == 0


# Test import_entries skips subdirectories within entry directory.
def test_import_entries_skips_subdirectories(tmp_path: Path) -> None:
    """Test import_entries ignores subdirectories in entry folder."""
    # Create directory structure with a subdirectory
    entry_dir = tmp_path / "source" / "entry"
    entry_dir.mkdir(parents=True)

    # Create valid files
    (entry_dir / "data.json").write_text('{"key": "value"}')
    (entry_dir / "_meta.json").write_text(
        json.dumps(
            {
                "matrix_values": {"test": "subdir"},
                "created_at": "2026-01-01T00:00:00Z",
                "metadata": {},
            }
        )
    )
    # Create a subdirectory that should be skipped
    subdir = entry_dir / "nested"
    subdir.mkdir()
    (subdir / "file.txt").write_text("nested content")

    with WorkflowCache(":memory:") as cache:
        count = import_entries(cache, tmp_path / "source")
        assert count == 1

        entry = cache.get({"test": "subdir"})
        assert entry is not None
        # Only data.json should be imported, not nested/file.txt
        assert "data" in entry.objects
        assert "nested" not in entry.objects
        assert "file" not in entry.objects


# Test import_entries handles zip with directory entries.
def test_import_entries_zip_with_directory_entries(tmp_path: Path) -> None:
    """Test import_entries handles zip files containing directory entries."""
    zip_path = tmp_path / "with_dirs.zip"

    with zipfile.ZipFile(zip_path, "w") as zf:
        # Add a directory entry (trailing slash)
        zf.writestr("entry/", "")
        # Add actual files
        zf.writestr("entry/data.json", '{"from": "zip"}')
        zf.writestr(
            "entry/_meta.json",
            json.dumps(
                {
                    "matrix_values": {"zip": "dirs"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "metadata": {},
                }
            ),
        )

    with WorkflowCache(":memory:") as cache:
        count = import_entries(cache, zip_path)
        assert count == 1

        entry = cache.get({"zip": "dirs"})
        assert entry is not None
        assert "data" in entry.objects


# Test import_entries handles zip with duplicate meta.json paths.
def test_import_entries_zip_deduplicates_entries(tmp_path: Path) -> None:
    """Test import_entries doesn't process same directory twice."""
    zip_path = tmp_path / "test.zip"

    with zipfile.ZipFile(zip_path, "w") as zf:
        # Single entry with multiple files
        zf.writestr("entry/file1.json", '{"f": 1}')
        zf.writestr("entry/file2.json", '{"f": 2}')
        zf.writestr(
            "entry/_meta.json",
            json.dumps(
                {
                    "matrix_values": {"dedup": "test"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "metadata": {},
                }
            ),
        )

    with WorkflowCache(":memory:") as cache:
        count = import_entries(cache, zip_path)
        # Should only import once, not multiple times
        assert count == 1

        entry = cache.get({"dedup": "test"})
        assert entry is not None
        assert "file1" in entry.objects
        assert "file2" in entry.objects


# =============================================================================
# Round-trip export/import tests
# =============================================================================


# Test export/import round-trip preserves data.
def test_round_trip_directory(tmp_path: Path) -> None:
    """Test export then import preserves entry data."""
    export_dir = tmp_path / "export"

    # Create and populate source cache
    with WorkflowCache(":memory:") as source:
        entry = CacheEntry(metadata={"original": True, "count": 42})
        entry.objects["graph"] = CacheObject(
            type="graphml", content="<graphml>original</graphml>"
        )
        entry.objects["stats"] = CacheObject(
            type="json", content='{"mean": 1.5}'
        )
        source.put({"dataset": "asia", "method": "pc"}, entry)

        export_entries(source, export_dir)

    # Import into fresh cache
    with WorkflowCache(":memory:") as dest:
        count = import_entries(dest, export_dir)
        assert count == 1

        imported = dest.get({"dataset": "asia", "method": "pc"})
        assert imported is not None
        assert imported.metadata.get("original") is True
        assert imported.metadata.get("count") == 42
        assert "graph" in imported.objects
        assert "stats" in imported.objects
        assert (
            imported.objects["graph"].content == "<graphml>original</graphml>"
        )


# Test export/import round-trip with zip preserves data.
def test_round_trip_zip(tmp_path: Path) -> None:
    """Test export to zip then import preserves entry data."""
    zip_path = tmp_path / "archive.zip"

    # Create and populate source cache
    with WorkflowCache(":memory:") as source:
        entry = CacheEntry(metadata={"from_zip": True})
        entry.objects["result"] = CacheObject(
            type="json", content='{"success": true}'
        )
        source.put({"test": "zip_roundtrip"}, entry)

        export_entries(source, zip_path)

    # Import into fresh cache
    with WorkflowCache(":memory:") as dest:
        count = import_entries(dest, zip_path)
        assert count == 1

        imported = dest.get({"test": "zip_roundtrip"})
        assert imported is not None
        assert imported.metadata.get("from_zip") is True
        assert imported.objects["result"].content == '{"success": true}'


# Test round-trip with multiple entries.
def test_round_trip_multiple_entries(tmp_path: Path) -> None:
    """Test export/import preserves multiple entries."""
    export_dir = tmp_path / "multi"

    # Create source with multiple entries
    with WorkflowCache(":memory:") as source:
        for i in range(5):
            entry = CacheEntry(metadata={"index": i})
            entry.objects["data"] = CacheObject(
                type="json", content=f'{{"id": {i}}}'
            )
            source.put({"entry_id": str(i)}, entry)

        count = export_entries(source, export_dir)
        assert count == 5

    # Import and verify all entries
    with WorkflowCache(":memory:") as dest:
        count = import_entries(dest, export_dir)
        assert count == 5

        for i in range(5):
            entry = dest.get({"entry_id": str(i)})
            assert entry is not None
            assert entry.metadata.get("index") == i
