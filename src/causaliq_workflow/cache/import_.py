"""Cache import functionality for workflow results.

This module handles importing cache entries from the filesystem back
into the cache. Reads the _meta.json files to reconstruct matrix_values
and metadata, and reads object files to reconstruct the CacheEntry.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from causaliq_workflow.cache.entry import CacheEntry, CacheObject
from causaliq_workflow.cache.export import TYPE_EXTENSIONS

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.cache.workflow_cache import WorkflowCache

# Reverse mapping: extension to type
EXTENSION_TYPES: dict[str, str] = {v: k for k, v in TYPE_EXTENSIONS.items()}


def get_type_for_extension(ext: str) -> str:
    """Get object type for a file extension.

    Args:
        ext: File extension including dot (e.g., '.graphml').

    Returns:
        Object type identifier (e.g., 'graphml').
    """
    return EXTENSION_TYPES.get(ext, "dat")


def import_entries(
    cache: "WorkflowCache",
    input_path: str | Path,
) -> int:
    """Import cache entries from filesystem.

    Reads entries exported by `export_entries()` and stores them back
    into the cache.

    The input format is determined by the path:
    - Path ending in .zip: reads from a zip archive
    - Otherwise: reads from a directory structure

    Args:
        cache: WorkflowCache instance to import into.
        input_path: Path to input directory or .zip file.

    Returns:
        Number of entries imported.

    Raises:
        FileNotFoundError: If input_path does not exist.
    """
    input_path = Path(input_path)
    is_zip = input_path.suffix.lower() == ".zip"

    if is_zip:
        return _import_from_zip(cache, input_path)
    else:
        return _import_from_dir(cache, input_path)


def _import_from_dir(
    cache: "WorkflowCache",
    input_dir: Path,
) -> int:
    """Import entries from a directory structure.

    Reads exported entries where each entry directory contains:
    - _meta.json with matrix_values and metadata
    - Object files (name.ext)

    Args:
        input_dir: Root directory containing exported entries.

    Returns:
        Number of entries imported.

    Raises:
        FileNotFoundError: If input_dir does not exist.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    count = 0

    # Find all _meta.json files
    for meta_path in input_dir.rglob("_meta.json"):
        entry_dir = meta_path.parent

        # Read metadata
        meta_content = json.loads(meta_path.read_text(encoding="utf-8"))
        matrix_values = meta_content.get("matrix_values", {})
        metadata = meta_content.get("metadata", {})

        # Build entry from files in directory
        entry = CacheEntry(metadata=metadata)

        for file_path in entry_dir.iterdir():
            if file_path.name == "_meta.json":
                continue
            if file_path.is_dir():
                continue

            name = file_path.stem
            ext = file_path.suffix
            obj_type = get_type_for_extension(ext)
            content = file_path.read_text(encoding="utf-8")

            entry.objects[name] = CacheObject(type=obj_type, content=content)

        # Store in cache
        if entry.objects:
            cache.put(matrix_values, entry)
            count += 1

    return count


def _import_from_zip(
    cache: "WorkflowCache",
    zip_path: Path,
) -> int:
    """Import entries from a zip archive.

    Reads exported entries where each entry directory contains:
    - _meta.json with matrix_values and metadata
    - Object files (name.ext)

    Args:
        zip_path: Path to input zip file.

    Returns:
        Number of entries imported.

    Raises:
        FileNotFoundError: If zip_path does not exist.
    """
    if not zip_path.exists():
        raise FileNotFoundError(f"Zip file not found: {zip_path}")

    count = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Group files by directory
        dirs_files: dict[str, list[str]] = {}
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            parent = str(PurePosixPath(name).parent)
            if parent not in dirs_files:
                dirs_files[parent] = []
            dirs_files[parent].append(name)

        # Find directories with _meta.json
        processed_dirs: set[str] = set()

        for name in zf.namelist():
            if not name.endswith("_meta.json"):
                continue

            entry_dir = str(PurePosixPath(name).parent)
            if entry_dir in processed_dirs:
                continue  # pragma: no cover
            processed_dirs.add(entry_dir)

            # Read metadata
            meta_content = json.loads(zf.read(name).decode("utf-8"))
            matrix_values = meta_content.get("matrix_values", {})
            metadata = meta_content.get("metadata", {})

            # Build entry from files in directory
            entry = CacheEntry(metadata=metadata)
            dir_files = dirs_files.get(entry_dir, [])

            for file_name in dir_files:
                fname = PurePosixPath(file_name).name
                if fname == "_meta.json":
                    continue

                stem = PurePosixPath(file_name).stem
                ext = PurePosixPath(file_name).suffix
                obj_type = get_type_for_extension(ext)
                content = zf.read(file_name).decode("utf-8")

                entry.objects[stem] = CacheObject(
                    type=obj_type, content=content
                )

            # Store in cache
            if entry.objects:
                cache.put(matrix_values, entry)
                count += 1

    return count
