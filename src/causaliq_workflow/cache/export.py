"""Cache export functionality for workflow results.

This module handles exporting cache entries to the filesystem using
the CacheEntry's objects to determine output format.

Each named object is exported as a file with extension based on type:
- json → .json
- graphml → .graphml
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from causaliq_core.metadata import SCHEMA_VERSION, normalise_metadata

from causaliq_workflow.cache.entry import CacheEntry

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.cache.workflow_cache import WorkflowCache

# Map serialisation format to file extension
FORMAT_EXTENSIONS: dict[str, str] = {
    "graphml": ".graphml",
    "json": ".json",
}

# Legacy alias for backward compatibility with import_.py
TYPE_EXTENSIONS: dict[str, str] = FORMAT_EXTENSIONS

WINDOWS_RESERVED_NAMES: set[str] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

WINDOWS_INVALID_PATH_CHARS: set[str] = set('<>:"/\\|?*')


def sanitise_path_segment(value: str) -> str:
    """Create a filesystem-safe path segment for export.

    This targets cross-platform safety and specifically handles Windows
    filename restrictions while keeping output readable.

    Args:
        value: Raw matrix value string.

    Returns:
        Sanitised segment safe to use as a directory name.
    """
    cleaned_chars = []
    for char in value:
        is_control_char = ord(char) < 32
        if is_control_char or char in WINDOWS_INVALID_PATH_CHARS:
            cleaned_chars.append("_")
        else:
            cleaned_chars.append(char)

    cleaned = "".join(cleaned_chars).rstrip(" .")

    if not cleaned:
        return "_"

    if cleaned.upper() in WINDOWS_RESERVED_NAMES:
        return f"_{cleaned}_"

    return cleaned


def get_extension_for_format(obj_format: str) -> str:
    """Get file extension for an object format.

    Args:
        obj_format: Serialisation format (e.g., 'graphml', 'json').

    Returns:
        File extension including dot (e.g., '.graphml', '.json').
    """
    return FORMAT_EXTENSIONS.get(obj_format, ".dat")


def get_extension_for_type(obj_type: str) -> str:
    """Get file extension for an object type (legacy).

    Deprecated: Use get_extension_for_format() instead.

    Args:
        obj_type: Object type identifier.

    Returns:
        File extension including dot.
    """
    return FORMAT_EXTENSIONS.get(obj_type, ".dat")


def build_entry_path(
    matrix_values: dict[str, Any],
    matrix_keys: list[str] | None = None,
) -> Path:
    """Build hierarchical path from matrix values.

    Creates a directory structure from matrix variable values.

    Args:
        matrix_values: Dictionary of matrix variable values.
        matrix_keys: Ordered list of keys for path hierarchy.
            If None, uses alphabetical order.

    Returns:
        Relative path like: asia/pc/
    """
    if matrix_keys is None:
        matrix_keys = sorted(matrix_values.keys())

    segments = []
    for key in matrix_keys:
        if key in matrix_values:
            value = str(matrix_values[key])
            safe_value = sanitise_path_segment(value)
            segments.append(safe_value)

    if segments:
        return Path(*segments)
    return Path("default")


def write_entry_to_dir(
    output_dir: Path,
    entry_path: Path,
    entry_info: dict[str, Any],
    objects: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    """Write entry files to directory.

    Creates the directory structure and writes:
    - Each object to its own file (name.ext)
    - A _meta.json file with metadata and matrix_values

    Args:
        output_dir: Root output directory.
        entry_path: Relative path for this entry.
        entry_info: Entry details (matrix_values).
        objects: Dict mapping name to {format, action, content}.
        metadata: Entry metadata dict.
    """
    full_dir = output_dir / entry_path
    full_dir.mkdir(parents=True, exist_ok=True)

    # Write each object
    for name, obj in objects.items():
        obj_format = obj.get("format", "dat")
        content = obj.get("content", "")
        ext = get_extension_for_format(obj_format)
        file_path = full_dir / f"{name}{ext}"
        file_path.write_text(content, encoding="utf-8")

    # Write metadata file
    meta_data = {
        "schema_version": SCHEMA_VERSION,
        "matrix_values": entry_info["matrix_values"],
        "metadata": normalise_metadata(metadata),
    }
    meta_path = full_dir / "_meta.json"
    meta_path.write_text(
        json.dumps(meta_data, indent=2, sort_keys=False),
        encoding="utf-8",
    )


def write_entry_to_zip(
    zf: zipfile.ZipFile,
    entry_path: Path,
    entry_info: dict[str, Any],
    objects: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    """Write entry files to zip archive.

    Args:
        zf: Open ZipFile for writing.
        entry_path: Relative path for this entry.
        entry_info: Entry details (matrix_values).
        objects: Dict mapping name to {format, action, content}.
        metadata: Entry metadata dict.
    """
    # Write each object
    for name, obj in objects.items():
        obj_format = obj.get("format", "dat")
        content = obj.get("content", "")
        ext = get_extension_for_format(obj_format)
        arc_name = str(entry_path / f"{name}{ext}")
        zf.writestr(arc_name, content)

    # Write metadata file
    meta_data = {
        "schema_version": SCHEMA_VERSION,
        "matrix_values": entry_info["matrix_values"],
        "metadata": normalise_metadata(metadata),
    }
    meta_arc = str(entry_path / "_meta.json")
    zf.writestr(meta_arc, json.dumps(meta_data, indent=2, sort_keys=False))


def export_entries(
    cache: "WorkflowCache",
    output_path: Path | str,
    matrix_keys: list[str] | None = None,
) -> int:
    """Export cache entries to filesystem.

    Iterates over cache entries and exports each one. Each entry becomes
    a directory containing its objects as files plus a _meta.json.

    The output format is determined by the path extension:
    - Path ending in .zip: creates a zip archive
    - Otherwise: creates a directory structure

    Args:
        cache: WorkflowCache instance to export from.
        output_path: Path to output directory or .zip file.
        matrix_keys: Ordered list of matrix variable names for directory
            hierarchy. If None, uses alphabetical order.

    Returns:
        Number of entries exported.
    """
    target = Path(output_path)
    entries_info = cache.list_entries()

    if target.suffix.lower() == ".zip":
        return _export_entries_to_zip(cache, entries_info, matrix_keys, target)
    return _export_entries_to_dir(cache, entries_info, matrix_keys, target)


def _export_entries_to_zip(
    cache: "WorkflowCache",
    entries_info: list[dict[str, Any]],
    matrix_keys: list[str] | None,
    output_path: Path,
) -> int:
    """Export entries into a zip archive; return the exported count."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry_info in entries_info:
            count += _export_zip_entry(cache, entry_info, matrix_keys, zf)

    return count


def _export_zip_entry(
    cache: "WorkflowCache",
    entry_info: dict[str, Any],
    matrix_keys: list[str] | None,
    zf: zipfile.ZipFile,
) -> int:
    """Export one entry into an open zip; return 1 when written, else 0."""
    written = _export_single_entry(
        cache,
        entry_info,
        matrix_keys,
        lambda path, info, objs, meta: write_entry_to_zip(
            zf, path, info, objs, meta
        ),
    )
    return 1 if written else 0


def _export_entries_to_dir(
    cache: "WorkflowCache",
    entries_info: list[dict[str, Any]],
    matrix_keys: list[str] | None,
    output_path: Path,
) -> int:
    """Export entries into a directory tree; return the exported count."""
    output_path.mkdir(parents=True, exist_ok=True)
    count = 0

    for entry_info in entries_info:
        if _export_single_entry(
            cache,
            entry_info,
            matrix_keys,
            lambda path, info, objs, meta: write_entry_to_dir(
                output_path, path, info, objs, meta
            ),
        ):
            count += 1

    return count


def _export_single_entry(
    cache: "WorkflowCache",
    entry_info: dict[str, Any],
    matrix_keys: list[str] | None,
    write_fn: Callable[
        [Path, dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]],
        None,
    ],
) -> bool:
    """Export a single cache entry.

    Args:
        cache: WorkflowCache instance.
        entry_info: Entry dict from list_entries().
        matrix_keys: Ordered list of matrix variable names.
        write_fn: Function to write files, called with
            (entry_path, entry_info, objects_dict, metadata).

    Returns:
        True if entry was exported, False if skipped.
    """
    # Get the full entry
    entry = cache.get(entry_info["matrix_values"])
    if entry is None:
        return False  # pragma: no cover

    # Skip only when there is nothing to record (no objects and no
    # metadata).  Metadata-only entries (e.g. recorded failures) are
    # exported so their _meta.json is still produced.
    if not entry.objects and not entry.metadata:
        return False

    # Build objects dict for export
    objects_dict = {name: obj.to_dict() for name, obj in entry.objects.items()}

    # Build entry path
    entry_path = build_entry_path(
        entry_info["matrix_values"],
        matrix_keys,
    )

    # Write files
    write_fn(entry_path, entry_info, objects_dict, entry.metadata)
    return True


# Legacy function for backward compatibility
def store_action_result(
    cache: "WorkflowCache | None",
    context: Any,
    entry_type: str,
    metadata: dict[str, Any],
    objects: list[dict[str, Any]],
    matrix_key_order: list[str] | None = None,
) -> str | None:
    """Store action result to workflow cache (framework interface).

    Args:
        cache: WorkflowCache instance to store into, or None.
        context: WorkflowContext with matrix_values for cache key.
        entry_type: Unused (kept for compatibility).
        metadata: Version 2 metadata envelope built by the executor.
        objects: List of object dicts with type, name, content.
        matrix_key_order: Optional ordered list of matrix variable names
            for export directory structure. If provided and not already
            set in cache, stores this order.

    Returns:
        Hash key used for storage, or None if no cache available.
    """
    _ = entry_type  # No longer used
    if cache is None:
        return None

    # Store matrix key order if provided and not already set
    if matrix_key_order is not None and cache.get_matrix_key_order() is None:
        cache.set_matrix_key_order(matrix_key_order)

    return cache.put_from_action(
        key_data=context.matrix_values,
        metadata=metadata,
        objects=objects,
    )


def store_failure_result(
    cache: "WorkflowCache | None",
    context: Any,
    metadata: dict[str, Any],
    matrix_key_order: list[str] | None = None,
) -> str | None:
    """Record a failed step as provenance only.

    A failed run writes provenance (status and failure reason) and no
    object: an object would be indistinguishable from the result of a
    successful run and could be scored. The entry replaces any prior entry
    for the key, so the latest run wins.

    Args:
        cache: WorkflowCache instance to store into, or None.
        context: WorkflowContext with matrix_values for the cache key.
        metadata: Version 2 metadata envelope recording the failure.
        matrix_key_order: Optional ordered list of matrix variable names
            for export directory structure.

    Returns:
        Hash key used for storage, or None if no cache is available.
    """
    if cache is None:
        return None

    if matrix_key_order is not None and cache.get_matrix_key_order() is None:
        cache.set_matrix_key_order(matrix_key_order)

    return cache.put(
        context.matrix_values,
        CacheEntry(metadata=normalise_metadata(metadata)),
    )


def serialise_objects(
    data: Any,
    objects_spec: list[dict[str, Any]],
) -> dict[str, str]:
    """Extract content from objects array for export (legacy).

    Args:
        data: Unused.
        objects_spec: List of object specifications.

    Returns:
        Dictionary mapping filename to content string.
    """
    _ = data
    result: dict[str, str] = {}

    for obj in objects_spec:
        obj_type = obj.get("type")
        name = obj.get("name", obj_type)
        content = obj.get("content")

        if not obj_type or not content:
            continue

        ext = get_extension_for_type(obj_type)
        result[f"{name}{ext}"] = content

    return result
