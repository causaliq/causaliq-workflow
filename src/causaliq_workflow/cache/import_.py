"""Cache import functionality for workflow results.

This module handles importing cache entries from the filesystem back
into the cache. Reads the _meta.json files to reconstruct matrix_values
and metadata, and reads object files to reconstruct the CacheEntry.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

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
    for meta_path in input_dir.rglob("_meta.json"):
        matrix_values, entry = _dir_cache_entry(meta_path.parent, meta_path)
        if entry.objects or entry.metadata:
            cache.put(matrix_values, entry)
            count += 1

    return count


def _dir_cache_entry(
    entry_dir: Path, meta_path: Path
) -> Tuple[Dict[str, Any], CacheEntry]:
    """Build a CacheEntry and its matrix values from an entry directory."""
    matrix_values, metadata = _read_meta(meta_path.read_text(encoding="utf-8"))
    entry = CacheEntry(metadata=metadata)

    for file_path in entry_dir.iterdir():
        if file_path.name == "_meta.json" or file_path.is_dir():
            continue
        entry.objects[file_path.stem] = CacheObject(
            format=get_type_for_extension(file_path.suffix),
            action="import",
            content=file_path.read_text(encoding="utf-8"),
        )

    return matrix_values, entry


def _read_meta(
    meta_content: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Parse a _meta.json payload into matrix values and metadata."""
    data = json.loads(meta_content)
    return data.get("matrix_values", {}), data.get("metadata", {})


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

    with zipfile.ZipFile(zip_path, "r") as zf:
        return _import_zip_archive(cache, zf)


def _import_zip_archive(cache: "WorkflowCache", zf: zipfile.ZipFile) -> int:
    """Import every entry from an open zip archive; return the count."""
    dirs_files = _group_zip_dir_files(zf)
    processed_dirs: Set[str] = set()
    count = 0

    for name in zf.namelist():
        meta_entry = _zip_meta_entry(zf, name, dirs_files, processed_dirs)
        if meta_entry is None:
            continue
        matrix_values, entry = meta_entry
        if entry.objects or entry.metadata:
            cache.put(matrix_values, entry)
            count += 1

    return count


def _group_zip_dir_files(zf: zipfile.ZipFile) -> Dict[str, List[str]]:
    """Group a zip archive's file names by their parent directory."""
    dirs_files: Dict[str, List[str]] = {}
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        parent = str(PurePosixPath(name).parent)
        dirs_files.setdefault(parent, []).append(name)
    return dirs_files


def _zip_meta_entry(
    zf: zipfile.ZipFile,
    name: str,
    dirs_files: Dict[str, List[str]],
    processed_dirs: Set[str],
) -> Optional[Tuple[Dict[str, Any], CacheEntry]]:
    """Build a (matrix_values, entry) pair from one zip member, or None."""
    if not name.endswith("_meta.json"):
        return None

    entry_dir = str(PurePosixPath(name).parent)
    if entry_dir in processed_dirs:  # pragma: no cover - duplicate guard
        return None
    processed_dirs.add(entry_dir)

    matrix_values, metadata = _read_meta(zf.read(name).decode("utf-8"))
    entry = CacheEntry(metadata=metadata)
    for file_name in dirs_files.get(entry_dir, []):
        _add_zip_object(zf, entry, file_name)
    return matrix_values, entry


def _add_zip_object(
    zf: zipfile.ZipFile,
    entry: CacheEntry,
    file_name: str,
) -> None:
    """Add a single file from a zip archive to an entry's objects."""
    if PurePosixPath(file_name).name == "_meta.json":
        return
    suffix = PurePosixPath(file_name).suffix
    entry.objects[PurePosixPath(file_name).stem] = CacheObject(
        format=get_type_for_extension(suffix),
        action="import",
        content=zf.read(file_name).decode("utf-8"),
    )
