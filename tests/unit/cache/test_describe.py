"""Unit tests for cache description and report formatting."""

from pathlib import Path

import pytest
from causaliq_core.metadata import build_metadata

from causaliq_workflow.cache import EMPTY_FORMAT, CacheEntry, WorkflowCache
from causaliq_workflow.cache.describe import (
    describe_cache,
    format_description,
)


def _metadata() -> dict:
    """Return a version 2 metadata envelope for a test entry."""
    return build_metadata(
        "causaliq-analysis",
        "evaluate_graph",
        {},
        {"status": "ok"},
    )


def _put_object(
    cache: WorkflowCache,
    matrix: dict,
    obj_type: str = "metrics",
) -> None:
    """Store a typed entry holding one small object."""
    entry = CacheEntry(metadata=_metadata())
    entry.add_object(obj_type, "json", "{}", "evaluate_graph")
    cache.put_typed(matrix, entry)


def _empty_description() -> dict:
    """Return the description of an empty cache."""
    return {
        "cache_type": "unknown",
        "entry_count": 0,
        "possible_count": 0,
        "object_count": 0,
        "variables": [],
        "example": None,
    }


# Test an empty cache describes as zero throughout.
def test_describe_cache_empty_cache() -> None:
    with WorkflowCache(":memory:") as cache:
        description = describe_cache(cache)

    assert description["cache_type"] == "unknown"
    assert description["entry_count"] == 0
    assert description["possible_count"] == 0
    assert description["object_count"] == 0
    assert description["variables"] == []
    assert description["example"] is None


# Test a partitioned cache reports the missing matrix combination.
def test_describe_cache_reports_possible_and_object_counts() -> None:
    with WorkflowCache(":memory:") as cache:
        _put_object(cache, {"network": "asia", "algorithm": "pc"})
        _put_object(cache, {"network": "asia", "algorithm": "ges"})
        cache.put_failure(
            {"network": "cancer", "algorithm": "pc"}, _metadata()
        )
        description = describe_cache(cache)

    assert description["cache_type"] == "metrics"
    assert description["entry_count"] == 3
    assert description["possible_count"] == 4
    assert description["object_count"] == 2


# Test each variable reports its values with possible/entry/object counts.
def test_describe_cache_reports_variable_values() -> None:
    with WorkflowCache(":memory:") as cache:
        _put_object(cache, {"network": "asia", "algorithm": "pc"})
        _put_object(cache, {"network": "asia", "algorithm": "ges"})
        cache.put_failure(
            {"network": "cancer", "algorithm": "pc"}, _metadata()
        )
        description = describe_cache(cache)

    variables = {item["name"]: item for item in description["variables"]}
    assert sorted(variables) == ["algorithm", "network"]
    assert variables["network"]["type"] == "str"
    assert variables["network"]["possible"] == 4
    values = {item["value"]: item for item in variables["network"]["values"]}
    assert values["asia"] == {
        "value": "asia",
        "possible": 2,
        "entries": 2,
        "objects": 2,
    }
    assert values["cancer"]["objects"] == 0


# Test the example prefers an entry that holds an object.
def test_describe_cache_example_prefers_object() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put_failure({"network": "asia"}, _metadata())
        _put_object(cache, {"network": "cancer"})
        description = describe_cache(cache)

    example = description["example"]
    assert example is not None
    assert example["matrix_values"] == {"network": "cancer"}
    assert example["objects"][0]["type"] == "metrics"
    assert example["metadata"]["result"]["status"] == "ok"


# Test a failure-only cache has no cache type and no object.
def test_describe_cache_failure_only_cache() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put_failure({"network": "asia"}, _metadata())
        description = describe_cache(cache)

    assert description["cache_type"] == "unknown"
    assert description["object_count"] == 0
    assert description["possible_count"] == 1
    assert description["example"]["objects"] == []


# Test an unpinned cache falls back to the object types it holds.
def test_describe_cache_observed_types() -> None:
    with WorkflowCache(":memory:") as cache:
        first = CacheEntry(metadata=_metadata())
        first.add_object("dag", "graphml", "<graphml/>", "learn_graph")
        cache.put({"network": "asia"}, first)
        second = CacheEntry(metadata=_metadata())
        second.add_object("pdg", "graphml", "<graphml/>", "merge_graphs")
        cache.put({"network": "cancer"}, second)
        description = describe_cache(cache)

    assert description["cache_type"] == "dag|pdg"


# Test mixed value types are reported together.
def test_describe_cache_mixed_value_types() -> None:
    with WorkflowCache(":memory:") as cache:
        _put_object(cache, {"seed": 1})
        _put_object(cache, {"seed": "1"})
        _put_object(cache, {"seed": None})
        description = describe_cache(cache)

    assert description["variables"][0]["type"] == "int|null|str"


# Test content sizes are measured for strings, bytes and other values.
@pytest.mark.parametrize(
    ("content", "expected"),
    [("{}", 2), (b"abc", 3), ({"a": 1}, 8)],
)
def test_content_size(content, expected) -> None:
    from causaliq_workflow.cache.describe import _content_size

    assert _content_size(content) == expected


# Test an object's size is reported for string content.
def test_describe_cache_reports_object_size() -> None:
    with WorkflowCache(":memory:") as cache:
        entry = CacheEntry(metadata=_metadata())
        entry.add_object("metrics", "json", "{}", "evaluate_graph")
        cache.put_typed({"network": "asia"}, entry)
        description = describe_cache(cache)

    assert description["example"]["objects"][0]["size"] == 2


# Test an empty placeholder object is not counted as an object.
def test_describe_cache_ignores_empty_object() -> None:
    with WorkflowCache(":memory:") as cache:
        entry = CacheEntry(metadata=_metadata())
        entry.add_object("metrics", EMPTY_FORMAT, "", "evaluate_graph")
        cache.put({"network": "asia"}, entry)
        description = describe_cache(cache)

    assert description["object_count"] == 0
    assert description["cache_type"] == "unknown"
    assert description["example"]["objects"] == []


# Test declared matrix order is preserved.
def test_describe_cache_uses_declared_variable_order() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.set_matrix_key_order(["network", "algorithm"])
        _put_object(cache, {"algorithm": "pc", "network": "asia"})
        description = describe_cache(cache)

    names = [item["name"] for item in description["variables"]]
    assert names == ["network", "algorithm"]


# Test the report formats an empty description.
def test_format_description_empty_description() -> None:
    lines = format_description(_empty_description(), Path("cache.db"), 0)

    assert lines[0] == "Cache description"
    assert "  File        : cache.db" in lines
    assert "  Size        : 0 Bytes" in lines
    assert "  Object type : unknown" in lines
    assert (
        "  Entries     : 0 possible / 0 with an entry / "
        "0 with an object" in lines
    )
    assert lines.count("  (none)") == 2


# Test file sizes are scaled to the matching unit.
@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 Bytes"),
        (1023, "1023 Bytes"),
        (1024, "1.0 KByte (1,024 Bytes)"),
        (1024**2, "1.0 MByte (1,048,576 Bytes)"),
        (1024**3, "1.0 GByte (1,073,741,824 Bytes)"),
        (1024**4, "1.0 TByte (1,099,511,627,776 Bytes)"),
        (1024**5, "1.0 PByte (1,125,899,906,842,624 Bytes)"),
    ],
)
def test_format_description_scales_size(size: int, expected: str) -> None:
    lines = format_description(_empty_description(), Path("cache.db"), size)
    assert f"  Size        : {expected}" in lines


# Test variables, their values and the example are formatted.
def test_format_description_variables_and_example() -> None:
    description = {
        "cache_type": "metrics",
        "entry_count": 3,
        "possible_count": 4,
        "object_count": 2,
        "variables": [
            {
                "name": "network",
                "type": "str",
                "possible": 4,
                "entries": 3,
                "objects": 2,
                "values": [
                    {
                        "value": "asia",
                        "possible": 2,
                        "entries": 2,
                        "objects": 2,
                    },
                    {
                        "value": "cancer",
                        "possible": 2,
                        "entries": 1,
                        "objects": 0,
                    },
                ],
            }
        ],
        "example": {
            "matrix_values": {"network": "asia"},
            "objects": [
                {
                    "type": "metrics",
                    "format": "json",
                    "action": "evaluate_graph",
                    "size": 2048,
                }
            ],
            "metadata": {"schema_version": 2},
        },
    }
    lines = format_description(description, Path("cache.db"), 4096)
    text = "\n".join(lines)

    assert "  network (str)" in text
    assert "2 / 2 / 2" in text
    assert "2 / 1 / 0" in text
    assert any(line.startswith("    asia ") for line in lines)
    assert 'key      : {"network": "asia"}' in text
    assert (
        "type=metrics, format=json, action=evaluate_graph, 2.0 KByte" in text
    )
    assert '"schema_version": 2' in text


# Test non-string matrix values render with their Python literal form.
def test_format_description_renders_non_string_values() -> None:
    description = {
        "cache_type": "metrics",
        "entry_count": 1,
        "possible_count": 1,
        "object_count": 1,
        "variables": [
            {
                "name": "weights",
                "type": "list",
                "possible": 1,
                "entries": 1,
                "objects": 1,
                "values": [
                    {
                        "value": [0.5, 0.5],
                        "possible": 1,
                        "entries": 1,
                        "objects": 1,
                    }
                ],
            }
        ],
        "example": {
            "matrix_values": {"weights": [0.5, 0.5]},
            "objects": [],
            "metadata": {},
        },
    }
    text = "\n".join(format_description(description, Path("cache.db"), 2048))

    assert "  weights (list)" in text
    assert "[0.5, 0.5]" in text
    assert "object   : none" in text


# Test records without a variable are skipped when counting its values.
def test_value_counts_skips_records_without_the_variable() -> None:
    from causaliq_workflow.cache.describe import _value_counts

    records = [
        {"matrix_values": {"network": "asia"}, "has_object": True},
        {"matrix_values": {}, "has_object": False},
    ]
    counts = _value_counts(records, "network")

    assert len(counts) == 1
    assert counts[repr("asia")]["entries"] == 1
    assert counts[repr("asia")]["objects"] == 1
