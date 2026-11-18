"""Describe the entries, objects and matrix coverage of a workflow cache.

The description is a read-only scan used by the ``cqflow describe-cache``
command and by any caller that needs to inspect a partitioned cache
without exporting it. "Possible" counts are the Cartesian product of the
matrix values observed in the cache: the cache stores no declared matrix,
so a value that was never attempted is not counted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.cache.entry import CacheEntry
    from causaliq_workflow.cache.workflow_cache import WorkflowCache

__all__ = ["describe_cache", "format_description"]

Record = dict[str, Any]
Description = dict[str, Any]


def describe_cache(cache: "WorkflowCache") -> Description:
    """Describe the entries, objects and matrix coverage of a cache.

    Args:
        cache: Open workflow cache to scan.

    Returns:
        Description mapping with keys ``cache_type``, ``entry_count``,
        ``possible_count``, ``object_count``, ``variables`` and
        ``example``. ``variables`` holds one mapping per matrix name
        with its type, totals and per-value counts; ``example`` is the
        first entry holding an object, or None when the cache is empty.
    """
    records, example = _scan_cache(cache)
    variables = _variables(cache, records)
    return {
        "cache_type": _cache_type(cache, records),
        "entry_count": len(records),
        "possible_count": _possible_total(
            [len(variable["values"]) for variable in variables],
            len(records),
        ),
        "object_count": sum(1 for record in records if record["has_object"]),
        "variables": variables,
        "example": example,
    }


def format_description(
    description: Description,
    cache_file: Path,
    size_bytes: int,
) -> list[str]:
    """Format a cache description as terminal report lines.

    Args:
        description: Mapping returned by :func:`describe_cache`.
        cache_file: Path shown as the cache's full path name.
        size_bytes: Size of the cache file in bytes.

    Returns:
        Report lines, without trailing newlines.
    """
    lines = [
        "Cache description",
        "",
        f"  File        : {cache_file}",
        f"  Size        : {_format_size(size_bytes)}",
        f"  Object type : {description['cache_type']}",
        f"  Entries     : {_entry_counts(description)}",
        "",
        "Key schema (possible / entry / object):",
        "",
    ]
    lines.extend(_variable_lines(description["variables"]))
    lines.extend(_example_lines(description["example"]))
    return lines


def _scan_cache(
    cache: "WorkflowCache",
) -> tuple[list[Record], Record | None]:
    """Return one light record per entry plus the example entry.

    Args:
        cache: Open workflow cache to scan.

    Returns:
        Tuple of (entry records, example entry mapping).
    """
    records: list[Record] = []
    example: Record | None = None
    for info in cache.list_entries():
        entry = cache.get(info["matrix_values"])
        if entry is None:  # pragma: no cover
            continue
        record = _entry_record(info["matrix_values"], entry)
        records.append(record)
        example = _pick_example(example, record, entry)
    return records, example


def _entry_record(
    matrix_values: dict[str, Any],
    entry: "CacheEntry",
) -> Record:
    """Return the description record for one cache entry."""
    objects = _object_summaries(entry)
    return {
        "matrix_values": matrix_values,
        "has_object": bool(objects),
        "objects": objects,
    }


def _object_summaries(entry: "CacheEntry") -> list[Record]:
    """Return a summary of each non-empty object held by an entry."""
    summaries: list[Record] = []
    for obj_type, obj in entry.objects.items():
        if obj.is_empty:
            continue
        summaries.append(
            {
                "type": obj_type,
                "format": obj.format,
                "action": obj.action,
                "size": _content_size(obj.content),
            }
        )
    return summaries


def _content_size(content: Any) -> int:
    """Return the size in bytes of an object's stored content."""
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    if isinstance(content, (bytes, bytearray)):
        return len(content)
    return len(json.dumps(content, default=str))


def _pick_example(
    example: Record | None,
    record: Record,
    entry: "CacheEntry",
) -> Record:
    """Return the example candidate, preferring an entry with an object."""
    if example is None:
        return {**record, "metadata": entry.metadata}
    if example["has_object"] or not record["has_object"]:
        return example
    return {**record, "metadata": entry.metadata}


def _cache_type(cache: "WorkflowCache", records: list[Record]) -> str:
    """Return the pinned cache type, falling back to observed objects."""
    pinned = cache.get_cache_type()
    if pinned is not None:
        return pinned
    return _observed_type(records)


def _observed_type(records: list[Record]) -> str:
    """Return the object types observed in entries, or 'unknown'."""
    types = {obj["type"] for record in records for obj in record["objects"]}
    if not types:
        return "unknown"
    return "|".join(sorted(types))


def _variables(
    cache: "WorkflowCache",
    records: list[Record],
) -> list[Record]:
    """Return the per-variable description in declaration order."""
    names = _variable_names(cache)
    counts = {name: _value_counts(records, name) for name in names}
    sizes = {name: len(counts[name]) for name in names}
    return [_variable(name, counts[name], sizes) for name in names]


def _variable_names(cache: "WorkflowCache") -> list[str]:
    """Return matrix variable names, declared order first."""
    schema = cache.get_matrix_schema()
    if schema is None:
        return []
    order = cache.get_matrix_key_order() or []
    ordered = [name for name in order if name in schema]
    return ordered + sorted(schema.difference(ordered))


def _value_counts(
    records: list[Record],
    name: str,
) -> dict[str, Record]:
    """Return per-value entry and object counts for one variable."""
    counts: dict[str, Record] = {}
    for record in records:
        matrix_values = record["matrix_values"]
        if name not in matrix_values:
            continue
        counts = _count_value(
            counts, matrix_values[name], record["has_object"]
        )
    return counts


def _count_value(
    counts: dict[str, Record],
    value: Any,
    has_object: bool,
) -> dict[str, Record]:
    """Add one entry to a value's counts and return the counts."""
    current = counts.setdefault(
        repr(value), {"value": value, "entries": 0, "objects": 0}
    )
    current["entries"] += 1
    current["objects"] += int(has_object)
    return counts


def _variable(
    name: str,
    value_counts: dict[str, Record],
    sizes: dict[str, int],
) -> Record:
    """Return the description of one matrix variable."""
    others = _product(size for other, size in sizes.items() if other != name)
    values = [
        {
            "value": item["value"],
            "possible": others,
            "entries": item["entries"],
            "objects": item["objects"],
        }
        for item in value_counts.values()
    ]
    values.sort(key=lambda item: str(item["value"]))
    return {
        "name": name,
        "type": _type_name([item["value"] for item in values]),
        "possible": others * len(values),
        "entries": sum(item["entries"] for item in values),
        "objects": sum(item["objects"] for item in values),
        "values": values,
    }


def _product(values: Iterable[int]) -> int:
    """Return the product of an iterable of counts."""
    total = 1
    for value in values:
        total *= value
    return total


def _possible_total(counts: list[int], entry_count: int) -> int:
    """Return the number of possible combinations."""
    if not counts:
        return 1 if entry_count else 0
    return _product(counts)


def _value_type(value: Any) -> str:
    """Return the display name of a value's type."""
    if value is None:
        return "null"
    return type(value).__name__


def _type_name(values: list[Any]) -> str:
    """Return the sorted type names of a variable's values."""
    names = sorted({_value_type(value) for value in values})
    return "|".join(names) if names else "unknown"


def _format_value(value: Any) -> str:
    """Return a matrix value as terminal text."""
    if isinstance(value, str):
        return value
    return repr(value)


def _entry_counts(description: Description) -> str:
    """Return the cache-level possible/entry/object counts."""
    return (
        f"{description['possible_count']} possible / "
        f"{description['entry_count']} with an entry / "
        f"{description['object_count']} with an object"
    )


def _variable_lines(variables: list[Record]) -> list[str]:
    """Return the key-schema report lines."""
    if not variables:
        return ["  (none)", ""]
    lines: list[str] = []
    for variable in variables:
        lines.extend(_one_variable_lines(variable))
    return lines + [""]


def _one_variable_lines(variable: Record) -> list[str]:
    """Return the heading and value lines for one variable."""
    heading = f"  {variable['name']} ({variable['type']})"
    texts = [_format_value(item["value"]) for item in variable["values"]]
    width = _value_width(heading, texts)
    lines = [f"{heading.ljust(width)}  {_counts_text(variable)}"]
    for text, item in zip(texts, variable["values"]):
        lines.append(f"{('    ' + text).ljust(width)}  {_counts_text(item)}")
    return lines


def _value_width(heading: str, texts: list[str]) -> int:
    """Return the alignment width for a variable's value lines."""
    longest = max((len(text) for text in texts), default=0)
    return max(len(heading), longest + 4)


def _counts_text(item: Record) -> str:
    """Return the possible/entry/object counts of a variable or value."""
    return f"{item['possible']} / {item['entries']} / {item['objects']}"


def _example_lines(example: Record | None) -> list[str]:
    """Return the example-entry report lines."""
    if example is None:
        return ["Example entry:", "", "  (none)", ""]
    key = json.dumps(example["matrix_values"], sort_keys=True, default=str)
    lines = [
        "Example entry:",
        "",
        f"  key      : {key}",
        f"  object   : {_format_objects(example['objects'])}",
        "  metadata :",
    ]
    lines.extend(_metadata_lines(example["metadata"]))
    return lines + [""]


def _metadata_lines(metadata: dict[str, Any]) -> list[str]:
    """Return an example entry's metadata as indented JSON lines."""
    text = json.dumps(metadata, indent=2, sort_keys=True, default=str)
    return [f"    {line}" for line in text.splitlines()]


def _format_objects(objects: list[Record]) -> str:
    """Return a one-line summary of an entry's objects."""
    if not objects:
        return "none"
    return "; ".join(
        f"type={obj['type']}, format={obj['format']}, "
        f"action={obj['action']}, {_format_size(obj['size'])}"
        for obj in objects
    )


def _format_size(size: int) -> str:
    """Return a human-readable size with the exact byte count."""
    if size < 1024:
        return f"{size} Bytes"
    return f"{_scaled_size(size)} ({size:,} Bytes)"


def _scaled_size(size: int) -> str:
    """Return a size scaled to KByte, MByte, GByte or TByte."""
    value = float(size)
    for unit in ("KByte", "MByte", "GByte", "TByte"):
        value = value / 1024
        if value < 1024:
            return f"{value:.1f} {unit}"
    return f"{value / 1024:.1f} PByte"
