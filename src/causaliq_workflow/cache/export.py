"""Cache export functionality for workflow results.

This module handles exporting cache entries to the filesystem using
the objects array in entry metadata to determine output format.

Each object in the array should contain:
- type: Data type identifier (e.g., 'graphml', 'json')
- name: Base filename for the exported file
- content: Serialised string content to export
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.cache.workflow_cache import WorkflowCache
    from causaliq_workflow.registry import WorkflowContext

# Map object type to file extension
TYPE_EXTENSIONS: dict[str, str] = {
    "graphml": ".graphml",
    "json": ".json",
}


def store_action_result(
    cache: "WorkflowCache | None",
    context: "WorkflowContext",
    entry_type: str,
    metadata: Dict[str, Any],
    objects: List[Dict[str, Any]],
) -> str | None:
    """Store action result to workflow cache.

    Stores the action result as a single cache entry with the objects
    array embedded in the metadata. This enables export to reconstruct
    the original files.

    Args:
        cache: WorkflowCache instance to store into, or None.
        context: WorkflowContext with matrix_values for cache key.
        entry_type: Type of entry (e.g., 'graph').
        metadata: Action result metadata dictionary.
        objects: List of object dicts with type, name, content.

    Returns:
        Hash key used for storage, or None if no cache available.

    Example:
        >>> store_action_result(
        ...     cache, context, "graph",
        ...     {"edge_count": 5},
        ...     [{"type": "graphml", "name": "graph", "content": "..."}]
        ... )
    """
    if cache is None:
        return None

    # Build metadata with objects array
    full_metadata = {**metadata, "objects": objects}

    # Use matrix_values as key, store empty dict as data
    # (all content is in objects array within metadata)
    return cache.put(
        key_data=context.matrix_values,
        entry_type=entry_type,
        data={},
        metadata=full_metadata,
    )


def get_extension_for_type(obj_type: str) -> str:
    """Get file extension for an object type.

    Args:
        obj_type: Object type identifier (e.g., 'graph', 'json').

    Returns:
        File extension including dot (e.g., '.graphml', '.json').
    """
    return TYPE_EXTENSIONS.get(obj_type, ".dat")


def serialise_objects(
    data: Any,
    objects_spec: list[dict[str, Any]],
) -> dict[str, str]:
    """Extract content from objects array for export.

    Each object specification should contain a 'content' field with
    the serialised string representation (e.g., GraphML, JSON string).

    Args:
        data: Unused (kept for API compatibility).
        objects_spec: List of object specifications, each with:
            - type: Data type for serialisation ('graphml', 'json')
            - name: Base filename (without extension)
            - content: Serialised string content

    Returns:
        Dictionary mapping filename (with extension) to content string.

    Example:
        >>> spec = [{"type": "graphml", "name": "graph",
        ...          "content": "<graphml>...</graphml>"}]
        >>> result = serialise_objects(None, spec)
        >>> # Returns {"graph.graphml": "<graphml>...</graphml>"}
    """
    _ = data  # Unused - content comes from objects_spec
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


def build_entry_path(
    matrix_values: dict[str, Any],
    created_at: str,
    matrix_keys: list[str] | None = None,
) -> Path:
    """Build hierarchical path from matrix values.

    Creates a directory structure from matrix variable values,
    with timestamp as the leaf filename.

    Args:
        matrix_values: Dictionary of matrix variable values.
        created_at: ISO timestamp for filename.
        matrix_keys: Ordered list of keys for path hierarchy.
            If None, uses alphabetical order.

    Returns:
        Relative path like: asia/pc/2026-02-06T14-30-00
    """
    if matrix_keys is None:
        matrix_keys = sorted(matrix_values.keys())

    segments = []
    for key in matrix_keys:
        if key in matrix_values:
            value = str(matrix_values[key])
            safe_value = value.replace("/", "_").replace("\\", "_")
            segments.append(safe_value)

    safe_timestamp = created_at.replace(":", "-")

    if segments:
        return Path(*segments) / safe_timestamp
    return Path(safe_timestamp)


def write_entry_to_dir(
    output_dir: Path,
    entry_path: Path,
    entry_info: dict[str, Any],
    metadata: dict[str, Any] | None,
    serialised_objects: dict[str, str],
) -> None:
    """Write entry files to directory.

    Creates the directory structure and writes:
    - Each serialised object to its own file
    - Adds workflow metadata to JSON files

    Args:
        output_dir: Root output directory.
        entry_path: Relative path for this entry.
        entry_info: Entry details (matrix_values, created_at, entry_type).
        metadata: Entry metadata dict.
        serialised_objects: Dict mapping filename to content.
    """
    full_dir = output_dir / entry_path.parent
    full_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in serialised_objects.items():
        file_path = output_dir / entry_path.parent / filename

        # For JSON files, merge in workflow metadata
        if filename.endswith(".json"):
            try:
                data = json.loads(content)
                data["matrix_values"] = entry_info["matrix_values"]
                data["created_at"] = entry_info["created_at"]
                data["entry_type"] = entry_info["entry_type"]
                if metadata is not None:
                    data["workflow_metadata"] = metadata
                content = json.dumps(data, indent=2, sort_keys=False)
            except json.JSONDecodeError:
                pass  # Write content as-is if not valid JSON

        file_path.write_text(content, encoding="utf-8")


def write_entry_to_zip(
    zf: zipfile.ZipFile,
    entry_path: Path,
    entry_info: dict[str, Any],
    metadata: dict[str, Any] | None,
    serialised_objects: dict[str, str],
) -> None:
    """Write entry files to zip archive.

    Args:
        zf: Open ZipFile for writing.
        entry_path: Relative path for this entry.
        entry_info: Entry details (matrix_values, created_at, entry_type).
        metadata: Entry metadata dict.
        serialised_objects: Dict mapping filename to content.
    """
    for filename, content in serialised_objects.items():
        arc_name = str(entry_path.parent / filename)

        # For JSON files, merge in workflow metadata
        if filename.endswith(".json"):
            try:
                data = json.loads(content)
                data["matrix_values"] = entry_info["matrix_values"]
                data["created_at"] = entry_info["created_at"]
                data["entry_type"] = entry_info["entry_type"]
                if metadata is not None:
                    data["workflow_metadata"] = metadata
                content = json.dumps(data, indent=2, sort_keys=False)
            except json.JSONDecodeError:
                pass

        zf.writestr(arc_name, content)


def export_entries(
    cache: "WorkflowCache",
    output_path: Path | str,
    entry_type: str | None = None,
    matrix_keys: list[str] | None = None,
) -> int:
    """Export cache entries to filesystem using provider serialisation.

    Iterates over cache entries and exports each one using the objects
    array in its metadata to determine serialisation format.

    The output format is determined by the path extension:
    - Path ending in .zip: creates a zip archive
    - Otherwise: creates a directory structure

    Args:
        cache: WorkflowCache instance to export from.
        output_path: Path to output directory or .zip file.
        entry_type: If provided, export only entries of this type.
        matrix_keys: Ordered list of matrix variable names for directory
            hierarchy. If None, uses alphabetical order.

    Returns:
        Number of entries exported.

    Raises:
        ValueError: If entry has no objects array in metadata.
    """
    output_path = Path(output_path)
    is_zip = output_path.suffix.lower() == ".zip"

    entries = cache.list_entries(entry_type)
    count = 0

    if is_zip:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for entry in entries:
                exported = _export_single_entry(
                    cache,
                    entry,
                    matrix_keys,
                    lambda path, info, meta, objs: write_entry_to_zip(
                        zf, path, info, meta, objs
                    ),
                )
                if exported:
                    count += 1
    else:
        output_path.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            exported = _export_single_entry(
                cache,
                entry,
                matrix_keys,
                lambda path, info, meta, objs: write_entry_to_dir(
                    output_path, path, info, meta, objs
                ),
            )
            if exported:
                count += 1

    return count


def _export_single_entry(
    cache: "WorkflowCache",
    entry: dict[str, Any],
    matrix_keys: list[str] | None,
    write_fn: Any,
) -> bool:
    """Export a single cache entry.

    Args:
        cache: WorkflowCache instance.
        entry: Entry dict from list_entries().
        matrix_keys: Ordered list of matrix variable names.
        write_fn: Function to write files, called with
            (entry_path, entry_info, metadata, serialised_objects).

    Returns:
        True if entry was exported, False if skipped.
    """
    # Get data and metadata
    result = cache.get_with_metadata(
        entry["matrix_values"],
        entry["entry_type"],
    )
    if result is None:
        return False

    data, metadata = result

    # Get objects array from metadata
    if metadata is None or "objects" not in metadata:
        return False

    objects_spec = metadata.get("objects", [])
    if not objects_spec:
        return False

    # Serialise objects
    serialised = serialise_objects(data, objects_spec)
    if not serialised:
        return False

    # Build entry path
    entry_path = build_entry_path(
        entry["matrix_values"],
        entry["created_at"],
        matrix_keys,
    )

    # Build entry info for metadata embedding
    entry_info = {
        "matrix_values": entry["matrix_values"],
        "created_at": entry["created_at"],
        "entry_type": entry["entry_type"],
    }

    # Write files
    write_fn(entry_path, entry_info, metadata, serialised)
    return True
