"""Functional tests for workflow cache integration.

Tests cache integration with workflow execution using tracked test data
files for reading and temporary directories for writing.
"""

import tempfile
from pathlib import Path

import pytest

from causaliq_workflow.cache import WorkflowCache
from causaliq_workflow.workflow import WorkflowExecutor
from tests.functional.fixtures.test_action import CausalIQAction

# Test data directory
TEST_DATA_DIR = (
    Path(__file__).parent.parent / "data" / "functional" / "workflow"
)


class CacheCapturingAction(CausalIQAction):
    """Test action that captures cache from context."""

    name = "cache-capturing-action"
    version = "1.0.0"
    description = "Test action that captures cache context"

    def run(self, inputs: dict, **kwargs) -> dict:
        context = kwargs.get("context")
        result = {
            "status": "success",
            "inputs": inputs,
            "has_cache": context.cache is not None if context else False,
            "cache_is_open": False,
        }
        if context and context.cache:
            result["cache_is_open"] = context.cache.is_open
        return result


@pytest.fixture
def executor() -> WorkflowExecutor:
    """Pytest fixture for executor setup."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["cache_capturing_action"] = (
        CacheCapturingAction
    )
    return executor


# Test workflow execution with file-based cache.
def test_workflow_with_file_cache(executor: WorkflowExecutor) -> None:
    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.db"
        with WorkflowCache(cache_path) as cache:
            results = executor.execute_workflow(
                workflow, mode="run", cache=cache
            )
            assert len(results) == 1
            step_result = results[0]["steps"]["Cache Capture Step"]
            assert step_result["has_cache"] is True
            assert step_result["cache_is_open"] is True
        assert cache_path.exists()


# Test workflow execution with in-memory cache.
def test_workflow_with_memory_cache(executor: WorkflowExecutor) -> None:
    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with WorkflowCache(":memory:") as cache:
        results = executor.execute_workflow(workflow, mode="run", cache=cache)
        assert len(results) == 1
        step_result = results[0]["steps"]["Cache Capture Step"]
        assert step_result["has_cache"] is True
        assert step_result["cache_is_open"] is True
        assert cache.is_memory


# Test cache persists across multiple workflow executions.
def test_cache_persists_across_executions(executor: WorkflowExecutor) -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "persistent_cache.db"

        # First execution - write to cache
        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"dataset": "asia"}, "json", {"value": 42})
            executor.execute_workflow(workflow, mode="run", cache=cache)

        # Second execution - verify cache persisted
        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            assert cache.exists({"dataset": "asia"}, "json")
            data = cache.get({"dataset": "asia"}, "json")
            assert data == {"value": 42}


# Test matrix execution with shared cache.
def test_matrix_execution_with_shared_cache(
    executor: WorkflowExecutor,
) -> None:
    workflow_path = TEST_DATA_DIR / "cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "matrix_cache.db"
        with WorkflowCache(cache_path) as cache:
            results = executor.execute_workflow(
                workflow, mode="run", cache=cache
            )
            assert len(results) == 4
            for result in results:
                step_result = result["steps"]["Cache Capture Step"]
                assert step_result["has_cache"] is True
                assert step_result["cache_is_open"] is True


# Test dry-run mode with cache.
def test_dry_run_with_cache(executor: WorkflowExecutor) -> None:
    workflow_path = TEST_DATA_DIR / "single_cache_workflow.yml"
    workflow = executor.parse_workflow(str(workflow_path))

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "dryrun_cache.db"
        with WorkflowCache(cache_path) as cache:
            results = executor.execute_workflow(
                workflow, mode="dry-run", cache=cache
            )
            assert len(results) == 1
            step_result = results[0]["steps"]["Cache Capture Step"]
            assert step_result["has_cache"] is True


# Test cache export to directory.
def test_cache_export_to_directory() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "export_test.db"
        output_dir = Path(tmpdir) / "exported"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"dataset": "asia", "method": "pc"}, "json", {"v": 1})
            cache.put({"dataset": "asia", "method": "ges"}, "json", {"v": 2})
            cache.put({"dataset": "sachs", "method": "pc"}, "json", {"v": 3})

            count = cache.export(
                output_dir,
                "json",
                matrix_keys=["dataset", "method"],
            )

        assert count == 3
        assert output_dir.exists()

        # Check directory structure
        asia_dir = output_dir / "asia"
        assert asia_dir.exists()
        pc_dir = asia_dir / "pc"
        ges_dir = asia_dir / "ges"
        assert pc_dir.exists()
        assert ges_dir.exists()

        # Check files exist
        pc_files = list(pc_dir.glob("*.json"))
        assert len(pc_files) >= 1  # At least data file and metadata


# Test cache export to zip.
def test_cache_export_to_zip() -> None:
    import zipfile

    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "export_test.db"
        zip_path = Path(tmpdir) / "exported.zip"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"dataset": "asia", "method": "pc"}, "json", {"v": 1})
            cache.put({"dataset": "sachs", "method": "ges"}, "json", {"v": 2})

            count = cache.export(
                zip_path,
                "json",
                matrix_keys=["dataset", "method"],
            )

        assert count == 2
        assert zip_path.exists()

        # Verify zip contents - single JSON file per entry (merged metadata)
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert len(names) == 2  # 1 JSON file per entry
            assert any("asia/pc/" in n for n in names)
            assert any("sachs/ges/" in n for n in names)


# Test cache export with empty cache.
def test_cache_export_empty_cache() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "empty_cache.db"
        output_dir = Path(tmpdir) / "exported"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            count = cache.export(output_dir, "json")

        assert count == 0


# Test cache list_entries returns correct data.
def test_cache_list_entries() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "list_test.db"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"a": "1", "b": "2"}, "json", {"data": "test1"})
            cache.put({"a": "3", "b": "4"}, "json", {"data": "test2"})

            entries = cache.list_entries("json")
            assert len(entries) == 2

            # Check entry structure
            for entry in entries:
                assert "matrix_values" in entry
                assert "created_at" in entry
                assert entry["entry_type"] == "json"


# Test cache export with empty matrix_values (covers line 499).
def test_cache_export_empty_matrix_values() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "empty_matrix.db"
        output_dir = Path(tmpdir) / "exported"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            # Put entry with empty matrix values
            cache.put({}, "json", {"value": 42})

            count = cache.export(output_dir, "json")

        assert count == 1
        # Files should be at root level (no nested directories)
        json_files = list(output_dir.glob("*.json"))
        assert len(json_files) >= 1


# Test cache export with no encoder raises KeyError (covers lines 520, 588).
def test_cache_export_no_encoder_raises_error() -> None:
    import pytest
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "no_encoder.db"
        output_dir = Path(tmpdir) / "exported"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"a": "1"}, "json", {"value": 1})

            # Try to export with unregistered entry type
            with pytest.raises(KeyError, match="No encoder registered"):
                cache.export(output_dir, "unknown_type")


# Test cache export to zip with no encoder raises KeyError.
def test_cache_export_zip_no_encoder_raises_error() -> None:
    import pytest
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "no_encoder_zip.db"
        zip_path = Path(tmpdir) / "exported.zip"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"a": "1"}, "json", {"value": 1})

            # Try to export with unregistered entry type
            with pytest.raises(KeyError, match="No encoder registered"):
                cache.export(zip_path, "unknown_type")


# Test cache export with metadata (covers lines 557, 637).
def test_cache_export_with_metadata() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "with_metadata.db"
        output_dir = Path(tmpdir) / "exported"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            # Put entry with metadata
            cache.put(
                {"dataset": "test"},
                "json",
                {"value": 42},
                metadata={"source": "test", "version": "1.0"},
            )

            count = cache.export(output_dir, "json")

        assert count == 1

        # Check JSON file contains merged metadata
        import json

        json_files = list(output_dir.glob("**/*.json"))
        assert len(json_files) == 1

        json_content = json.loads(json_files[0].read_text())
        assert "workflow_metadata" in json_content
        assert json_content["workflow_metadata"]["source"] == "test"
        assert json_content["matrix_values"]["dataset"] == "test"


# Test cache export to zip with metadata.
def test_cache_export_zip_with_metadata() -> None:
    import json
    import zipfile

    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "with_metadata_zip.db"
        zip_path = Path(tmpdir) / "exported.zip"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put(
                {"dataset": "test"},
                "json",
                {"value": 42},
                metadata={"source": "test", "version": "1.0"},
            )

            count = cache.export(zip_path, "json")

        assert count == 1

        # Check JSON in zip contains merged metadata
        with zipfile.ZipFile(zip_path, "r") as zf:
            json_files = [n for n in zf.namelist() if n.endswith(".json")]
            assert len(json_files) == 1

            json_content = json.loads(zf.read(json_files[0]))
            assert "workflow_metadata" in json_content
            assert json_content["workflow_metadata"]["source"] == "test"


# Test export skips entries where get_with_metadata returns None (line 529).
def test_cache_export_skips_missing_entries(monkeypatch) -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "skip_test.db"
        output_dir = Path(tmpdir) / "exported"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"a": "1"}, "json", {"value": 1})
            cache.put({"a": "2"}, "json", {"value": 2})

            # Mock get_with_metadata to return None for one entry
            original_get = cache.get_with_metadata
            call_count = [0]

            def mock_get(matrix_values, entry_type):
                call_count[0] += 1
                if matrix_values.get("a") == "1":
                    return None  # Simulate missing entry
                return original_get(matrix_values, entry_type)

            monkeypatch.setattr(cache, "get_with_metadata", mock_get)

            count = cache.export(output_dir, "json")

        # Only one entry should be exported
        assert count == 1


# Test zip export skips entries where get_with_metadata returns None.
def test_cache_export_zip_skips_missing_entries(monkeypatch) -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "skip_test_zip.db"
        zip_path = Path(tmpdir) / "exported.zip"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"a": "1"}, "json", {"value": 1})
            cache.put({"a": "2"}, "json", {"value": 2})

            # Mock get_with_metadata to return None for one entry
            original_get = cache.get_with_metadata
            call_count = [0]

            def mock_get(matrix_values, entry_type):
                call_count[0] += 1
                if matrix_values.get("a") == "1":
                    return None  # Simulate missing entry
                return original_get(matrix_values, entry_type)

            monkeypatch.setattr(cache, "get_with_metadata", mock_get)

            count = cache.export(zip_path, "json")

        # Only one entry should be exported
        assert count == 1


# ============================================================================
# Import tests
# ============================================================================


# Test cache import from directory.
def test_cache_import_from_directory() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        source_cache = Path(tmpdir) / "source.db"
        export_dir = Path(tmpdir) / "exported"
        dest_cache = Path(tmpdir) / "dest.db"

        # Create and export source cache
        with WorkflowCache(source_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"dataset": "asia", "method": "pc"}, "json", {"v": 1})
            cache.put({"dataset": "asia", "method": "ges"}, "json", {"v": 2})
            cache.put({"dataset": "sachs", "method": "pc"}, "json", {"v": 3})
            cache.export(export_dir, "json")

        # Import into new cache
        with WorkflowCache(dest_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            count = cache.import_entries(export_dir, "json")
            assert count == 3

            # Verify imported entries
            assert cache.exists({"dataset": "asia", "method": "pc"}, "json")
            assert cache.exists({"dataset": "asia", "method": "ges"}, "json")
            assert cache.exists({"dataset": "sachs", "method": "pc"}, "json")

            # Check data integrity
            data = cache.get({"dataset": "asia", "method": "pc"}, "json")
            assert data == {"v": 1}


# Test cache import from zip file.
def test_cache_import_from_zip() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        source_cache = Path(tmpdir) / "source.db"
        zip_path = Path(tmpdir) / "exported.zip"
        dest_cache = Path(tmpdir) / "dest.db"

        # Create and export source cache
        with WorkflowCache(source_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"dataset": "asia"}, "json", {"v": 1})
            cache.put({"dataset": "sachs"}, "json", {"v": 2})
            cache.export(zip_path, "json")

        # Import into new cache
        with WorkflowCache(dest_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            count = cache.import_entries(zip_path, "json")
            assert count == 2

            # Verify imported entries
            assert cache.exists({"dataset": "asia"}, "json")
            assert cache.exists({"dataset": "sachs"}, "json")

            # Check data integrity
            data = cache.get({"dataset": "sachs"}, "json")
            assert data == {"v": 2}


# Test round-trip export then import preserves data.
def test_cache_round_trip() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        original_cache = Path(tmpdir) / "original.db"
        export_dir = Path(tmpdir) / "exported"
        imported_cache = Path(tmpdir) / "imported.db"

        original_data = [
            ({"a": "1", "b": "2"}, {"data": "test1"}),
            ({"a": "3", "b": "4"}, {"data": "test2"}),
            ({"a": "5", "b": "6"}, {"data": "test3"}),
        ]

        # Create original cache
        with WorkflowCache(original_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            for key, data in original_data:
                cache.put(key, "json", data)
            cache.export(export_dir, "json")

        # Import into new cache
        with WorkflowCache(imported_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.import_entries(export_dir, "json")

            # Verify all data preserved
            for key, expected_data in original_data:
                assert cache.exists(key, "json")
                actual_data = cache.get(key, "json")
                assert actual_data == expected_data


# Test round-trip with zip file.
def test_cache_round_trip_zip() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        original_cache = Path(tmpdir) / "original.db"
        zip_path = Path(tmpdir) / "exported.zip"
        imported_cache = Path(tmpdir) / "imported.db"

        original_data = [
            ({"x": "a"}, {"value": 100}),
            ({"x": "b"}, {"value": 200}),
        ]

        # Create original cache
        with WorkflowCache(original_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            for key, data in original_data:
                cache.put(key, "json", data)
            cache.export(zip_path, "json")

        # Import into new cache
        with WorkflowCache(imported_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.import_entries(zip_path, "json")

            for key, expected_data in original_data:
                assert cache.exists(key, "json")
                assert cache.get(key, "json") == expected_data


# Test import with metadata preserves metadata.
def test_cache_import_with_metadata() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        source_cache = Path(tmpdir) / "source.db"
        export_dir = Path(tmpdir) / "exported"
        dest_cache = Path(tmpdir) / "dest.db"

        # Create cache with metadata
        with WorkflowCache(source_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put(
                {"key": "test"},
                "json",
                {"data": "value"},
                metadata={"source": "test", "version": "1.0"},
            )
            cache.export(export_dir, "json")

        # Import and check metadata
        with WorkflowCache(dest_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.import_entries(export_dir, "json")

            result = cache.get_with_metadata({"key": "test"}, "json")
            assert result is not None
            data, metadata = result
            # Data now includes merged workflow metadata fields
            assert "data" in data
            assert data["data"] == "value"
            assert metadata == {"source": "test", "version": "1.0"}


# Test import from nonexistent directory raises FileNotFoundError.
def test_cache_import_nonexistent_dir_raises_error() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.db"
        missing_dir = Path(tmpdir) / "missing"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            with pytest.raises(FileNotFoundError, match="Input directory"):
                cache.import_entries(missing_dir, "json")


# Test import from nonexistent zip raises FileNotFoundError.
def test_cache_import_nonexistent_zip_raises_error() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "cache.db"
        missing_zip = Path(tmpdir) / "missing.zip"

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            with pytest.raises(FileNotFoundError, match="Zip file"):
                cache.import_entries(missing_zip, "json")


# Test import with no encoder raises KeyError.
def test_cache_import_no_encoder_raises_error() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        source_cache = Path(tmpdir) / "source.db"
        export_dir = Path(tmpdir) / "exported"
        dest_cache = Path(tmpdir) / "dest.db"

        # Create and export
        with WorkflowCache(source_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"a": "1"}, "json", {"v": 1})
            cache.export(export_dir, "json")

        # Try import without registering encoder
        with WorkflowCache(dest_cache) as cache:
            with pytest.raises(KeyError, match="No encoder registered"):
                cache.import_entries(export_dir, "json")


# Test import from zip with no encoder raises KeyError.
def test_cache_import_zip_no_encoder_raises_error() -> None:
    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        source_cache = Path(tmpdir) / "source.db"
        zip_path = Path(tmpdir) / "exported.zip"
        dest_cache = Path(tmpdir) / "dest.db"

        # Create and export
        with WorkflowCache(source_cache) as cache:
            cache.register_encoder("json", JsonEncoder())
            cache.put({"a": "1"}, "json", {"v": 1})
            cache.export(zip_path, "json")

        # Try import without registering encoder
        with WorkflowCache(dest_cache) as cache:
            with pytest.raises(KeyError, match="No encoder registered"):
                cache.import_entries(zip_path, "json")


# Test import skips entries without matching data file.
def test_cache_import_skips_missing_data_file() -> None:
    import json

    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        export_dir = Path(tmpdir) / "partial"
        export_dir.mkdir()
        cache_path = Path(tmpdir) / "cache.db"

        # Create JSON file with proper merged format
        data_content = {
            "data": "complete",
            "matrix_values": {"key": "complete"},
            "created_at": "2026-02-06T12:01:00",
            "entry_type": "json",
        }
        data_path = export_dir / "2026-02-06T12-01-00.json"
        data_path.write_text(json.dumps(data_content))

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            count = cache.import_entries(export_dir, "json")

        # Entry should be imported
        assert count == 1


# Test import from zip skips entries without matching data file.
def test_cache_import_zip_skips_missing_data_file() -> None:
    import json
    import zipfile

    from causaliq_core.cache.encoders import JsonEncoder

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "partial.zip"
        cache_path = Path(tmpdir) / "cache.db"

        # Create zip with JSON file in merged format
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Complete entry with merged metadata
            complete_content = {
                "data": "complete",
                "matrix_values": {"key": "complete"},
                "created_at": "2026-02-06T12:01:00",
                "entry_type": "json",
            }
            zf.writestr("complete.json", json.dumps(complete_content))

        with WorkflowCache(cache_path) as cache:
            cache.register_encoder("json", JsonEncoder())
            count = cache.import_entries(zip_path, "json")

        # Entry should be imported
        assert count == 1
