"""
WorkflowCache: High-level cache for workflow step results.

Wraps TokenCache from causaliq-core with workflow-specific functionality:
- Matrix key hashing for cache lookups
- CacheEntry storage with metadata and named objects
- Matrix schema validation for consistency
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from causaliq_core.cache import TokenCache
from causaliq_core.cache.compressors import Compressor, JsonCompressor

from causaliq_workflow.cache.entry import CacheEntry


class MatrixSchemaError(Exception):
    """Raised when matrix variable keys don't match existing cache entries.

    Once a cache contains entries, all subsequent entries must use the
    same matrix variable names. This ensures cache consistency and
    prevents accidental data corruption from mismatched workflows.

    Example:
        >>> # Cache has entries with keys {"algorithm", "dataset"}
        >>> # Trying to add entry with {"algorithm", "network"} raises
        >>> raise MatrixSchemaError(
        ...     "Matrix keys mismatch: got {'algorithm', 'network'}, "
        ...     "expected {'algorithm', 'dataset'}"
        ... )
    """

    pass


class WorkflowCache:
    """High-level cache for workflow step results.

    Provides a simplified interface for storing and retrieving workflow
    results as CacheEntry objects. Uses matrix variable values as cache
    keys, with SHA-256 hashing for compact storage.

    Each entry contains metadata and named objects (e.g., 'graph',
    'confidences'), allowing a single workflow step to produce multiple
    outputs that are stored together.

    Attributes:
        db_path: Path to SQLite database file, or ":memory:" for in-memory.

    Example:
        >>> from causaliq_workflow.cache import WorkflowCache, CacheEntry
        >>> with WorkflowCache(":memory:") as cache:
        ...     entry = CacheEntry()
        ...     entry.metadata["node_count"] = 5
        ...     entry.add_object("graph", "graphml", "<graphml>...</graphml>")
        ...     key = {"algorithm": "pc", "network": "asia"}
        ...     cache.put(key, entry)
        ...     result = cache.get(key)
        ...     print(result.metadata)
        {'node_count': 5}
    """

    # Length of truncated SHA-256 hash (16 hex chars = 64 bits)
    HASH_LENGTH = 16

    def __init__(self, db_path: str | Path) -> None:
        """Initialise WorkflowCache.

        Args:
            db_path: Path to SQLite database file. Use ":memory:" for
                in-memory database (fast, non-persistent).
        """
        self.db_path = str(db_path)
        self._token_cache: TokenCache | None = None

    @property
    def token_cache(self) -> TokenCache:
        """Get the underlying TokenCache, raising if not connected."""
        if self._token_cache is None:
            raise RuntimeError(
                "WorkflowCache not connected. "
                "Use 'with cache:' or call open()."
            )
        return self._token_cache

    @property
    def is_open(self) -> bool:
        """Check if the cache connection is open."""
        return self._token_cache is not None and self._token_cache.is_open

    @property
    def is_memory(self) -> bool:
        """Check if this is an in-memory database."""
        return self.db_path == ":memory:"

    def open(self) -> WorkflowCache:
        """Open the database connection and initialise schema.

        Returns:
            self for method chaining.

        Raises:
            RuntimeError: If already connected.
        """
        if self._token_cache is not None:
            raise RuntimeError("WorkflowCache already connected.")

        self._token_cache = TokenCache(self.db_path)
        self._token_cache.open()
        # Set default compressor for JSON-based storage
        self._token_cache.set_compressor(JsonCompressor())
        return self

    def close(self) -> None:
        """Close the database connection."""
        if self._token_cache is not None:
            self._token_cache.close()
            self._token_cache = None

    def __enter__(self) -> WorkflowCache:
        """Context manager entry - opens connection."""
        return self.open()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit - closes connection."""
        self.close()

    def set_compressor(self, compressor: Compressor) -> None:
        """Set the compressor for data encoding.

        Args:
            compressor: Compressor instance for encoding/decoding.
        """
        self.token_cache.set_compressor(compressor)

    # ========================================================================
    # Key hashing
    # ========================================================================

    def compute_hash(self, key_data: dict[str, Any]) -> str:
        """Compute truncated SHA-256 hash from key data.

        The hash is derived from JSON-serialised key data with sorted
        keys for deterministic ordering.

        Args:
            key_data: Dictionary of matrix variable values.

        Returns:
            Truncated hex hash string (16 characters).

        Example:
            >>> cache = WorkflowCache(":memory:")
            >>> cache.compute_hash({"algorithm": "pc", "network": "asia"})
            'a3f7b2c1e9d4f8a2'  # Example output
        """
        key_json = json.dumps(key_data, sort_keys=True, separators=(",", ":"))
        full_hash = hashlib.sha256(key_json.encode("utf-8")).hexdigest()
        return full_hash[: self.HASH_LENGTH]

    def _key_json(self, key_data: dict[str, Any]) -> str:
        """Convert key data to canonical JSON string.

        Used for collision detection - stored alongside hash.

        Args:
            key_data: Dictionary of matrix variable values.

        Returns:
            Canonical JSON string with sorted keys.
        """
        return json.dumps(key_data, sort_keys=True, separators=(",", ":"))

    # ========================================================================
    # Cache operations
    # ========================================================================

    def put(
        self,
        key_data: dict[str, Any],
        entry: CacheEntry,
    ) -> str:
        """Store a workflow entry in the cache.

        If an entry with the same key already exists, it is replaced.

        Validates that key_data uses the same matrix variable names as
        existing entries to ensure cache consistency.

        Args:
            key_data: Dictionary of matrix variable values (cache key).
            entry: CacheEntry containing metadata and objects.

        Returns:
            The hash key used for storage.

        Raises:
            MatrixSchemaError: If key_data uses different variable names
                than existing entries.

        Example:
            >>> with WorkflowCache(":memory:") as cache:
            ...     entry = CacheEntry()
            ...     entry.metadata["result"] = "ok"
            ...     key = {"algorithm": "pc"}
            ...     hash_key = cache.put(key, entry)
        """
        # Validate matrix keys match existing schema
        self.validate_matrix_keys(key_data)

        hash_key = self.compute_hash(key_data)
        key_json = self._key_json(key_data)

        # Convert entry to storage format
        data, metadata = entry.to_storage()

        self.token_cache.put_data(
            hash=hash_key,
            data=data,
            metadata=metadata,
            key_json=key_json,
        )
        return hash_key

    def get(
        self,
        key_data: dict[str, Any],
    ) -> CacheEntry | None:
        """Retrieve a workflow entry from the cache.

        Args:
            key_data: Dictionary of matrix variable values (cache key).

        Returns:
            CacheEntry if found, None otherwise.

        Example:
            >>> with WorkflowCache(":memory:") as cache:
            ...     entry = CacheEntry()
            ...     entry.metadata["result"] = "ok"
            ...     cache.put({"algo": "pc"}, entry)
            ...     result = cache.get({"algo": "pc"})
            ...     print(result.metadata)
            {'result': 'ok'}
        """
        hash_key = self.compute_hash(key_data)
        key_json = self._key_json(key_data)

        result = self.token_cache.get_data_with_metadata(
            hash=hash_key,
            key_json=key_json,
        )
        if result is None:
            return None

        data, metadata = result
        return CacheEntry.from_storage(data, metadata)

    def get_or_create(
        self,
        key_data: dict[str, Any],
    ) -> CacheEntry:
        """Get existing entry or create a new empty one.

        Convenience method for actions that modify entries. If the entry
        doesn't exist, returns a new empty CacheEntry.

        Args:
            key_data: Dictionary of matrix variable values (cache key).

        Returns:
            Existing CacheEntry or new empty entry.

        Example:
            >>> with WorkflowCache(":memory:") as cache:
            ...     entry = cache.get_or_create({"algo": "pc"})
            ...     entry.metadata["step"] = 1
            ...     cache.put({"algo": "pc"}, entry)
        """
        entry = self.get(key_data)
        return entry if entry is not None else CacheEntry()

    def exists(
        self,
        key_data: dict[str, Any],
    ) -> bool:
        """Check if a cache entry exists.

        Args:
            key_data: Dictionary of matrix variable values (cache key).

        Returns:
            True if entry exists, False otherwise.

        Example:
            >>> with WorkflowCache(":memory:") as cache:
            ...     cache.exists({"algo": "pc"})  # False
            ...     cache.put({"algo": "pc"}, CacheEntry())
            ...     cache.exists({"algo": "pc"})  # True
        """
        hash_key = self.compute_hash(key_data)
        key_json = self._key_json(key_data)
        return self.token_cache.exists(hash=hash_key, key_json=key_json)

    def delete(
        self,
        key_data: dict[str, Any],
    ) -> bool:
        """Delete a cache entry.

        Args:
            key_data: Dictionary of matrix variable values (cache key).

        Returns:
            True if entry was deleted, False if it didn't exist.
        """
        hash_key = self.compute_hash(key_data)
        key_json = self._key_json(key_data)
        return self.token_cache.delete(hash=hash_key, key_json=key_json)

    # ========================================================================
    # Statistics and listing
    # ========================================================================

    def entry_count(self) -> int:
        """Count cache entries.

        Returns:
            Number of entries in the cache.
        """
        return self.token_cache.entry_count()

    def list_entries(self) -> list[dict[str, Any]]:
        """List all cache entries with details.

        Returns entry details including matrix_values (parsed from key_json)
        and created_at timestamp.

        Returns:
            List of entry dictionaries with keys: hash, matrix_values (dict),
            created_at (str).
        """
        raw_entries = self.token_cache.list_entries()
        entries = []
        for entry in raw_entries:
            # Parse key_json back to matrix_values dict
            key_json = entry["key_json"]
            matrix_values = json.loads(key_json) if key_json else {}
            entries.append(
                {
                    "hash": entry["hash"],
                    "matrix_values": matrix_values,
                    "created_at": entry["created_at"],
                }
            )
        return entries

    def token_count(self) -> int:
        """Count tokens in the shared dictionary.

        Returns:
            Number of tokens.
        """
        return self.token_cache.token_count()

    # ========================================================================
    # Matrix schema validation
    # ========================================================================

    def get_matrix_schema(self) -> set[str] | None:
        """Get the matrix variable names from existing cache entries.

        Examines existing entries to determine the matrix schema (set of
        variable names used as keys). Returns None if the cache is empty.

        Returns:
            Set of matrix variable names, or None if cache is empty.

        Raises:
            MatrixSchemaError: If existing entries have inconsistent schemas.

        Example:
            >>> with WorkflowCache(":memory:") as cache:
            ...     entry = CacheEntry()
            ...     cache.put({"algo": "pc", "data": "asia"}, entry)
            ...     cache.get_matrix_schema()
            {'algo', 'data'}
        """
        entries = self.list_entries()
        if not entries:
            return None

        # Get schema from first entry
        first_schema = frozenset(entries[0]["matrix_values"].keys())

        # Verify all entries have same schema
        for entry in entries[1:]:
            entry_schema = frozenset(entry["matrix_values"].keys())
            if entry_schema != first_schema:
                raise MatrixSchemaError(
                    f"Inconsistent matrix schemas in cache: "
                    f"found {set(entry_schema)} but expected "
                    f"{set(first_schema)}"
                )

        return set(first_schema)

    def validate_matrix_keys(self, key_data: dict[str, Any]) -> None:
        """Validate that key_data matches the existing matrix schema.

        If the cache already contains entries, the keys in key_data must
        exactly match the keys used in existing entries. This ensures
        cache consistency across workflow executions.

        Args:
            key_data: Dictionary of matrix variable values to validate.

        Raises:
            MatrixSchemaError: If keys don't match existing schema.

        Example:
            >>> with WorkflowCache(":memory:") as cache:
            ...     cache.put({"algo": "pc"}, CacheEntry())
            ...     cache.validate_matrix_keys({"algo": "ges"})  # OK
            ...     cache.validate_matrix_keys({"method": "pc"})  # Raises
        """
        existing_schema = self.get_matrix_schema()
        if existing_schema is None:
            # Empty cache - any schema is valid
            return

        new_schema = set(key_data.keys())
        if new_schema != existing_schema:
            raise MatrixSchemaError(
                f"Matrix keys mismatch: got {sorted(new_schema)}, "
                f"expected {sorted(existing_schema)}"
            )

    # ========================================================================
    # Export operations
    # ========================================================================

    def export(
        self,
        output_path: str | Path,
        matrix_keys: list[str] | None = None,
    ) -> int:
        """Export cache entries to directory or zip file.

        Creates a hierarchical directory structure based on matrix variable
        values. Each entry's objects are written as individual files.

        The output format is determined by the path extension:
        - Path ending in .zip: creates a zip archive
        - Otherwise: creates a directory structure

        Args:
            output_path: Path to output directory or .zip file.
            matrix_keys: Ordered list of matrix variable names for directory
                hierarchy. If None, uses alphabetical order.

        Returns:
            Number of entries exported.

        Example:
            >>> with WorkflowCache("cache.db") as cache:
            ...     # Export to dir: asia/pc/graph.graphml
            ...     cache.export("./out", ["dataset", "algorithm"])
            ...     # Export to zip file
            ...     cache.export("./out.zip", ["dataset"])
        """
        from causaliq_workflow.cache.export import export_entries

        return export_entries(self, output_path, matrix_keys)

    # ========================================================================
    # Import operations
    # ========================================================================

    def import_entries(
        self,
        input_path: str | Path,
    ) -> int:
        """Import cache entries from directory or zip file.

        Reads entries exported by `export()` and stores them back into
        the cache. The input format is determined by the path:
        - Path ending in .zip: reads from a zip archive
        - Otherwise: reads from a directory structure

        Args:
            input_path: Path to input directory or .zip file.

        Returns:
            Number of entries imported.

        Raises:
            FileNotFoundError: If input_path does not exist.

        Example:
            >>> with WorkflowCache("cache.db") as cache:
            ...     # Import from directory
            ...     cache.import_entries("./exported")
            ...     # Import from zip file
            ...     cache.import_entries("./exported.zip")
        """
        from causaliq_workflow.cache.import_ import import_entries

        return import_entries(self, input_path)

    # ========================================================================
    # Legacy compatibility
    # ========================================================================

    def put_from_action(
        self,
        key_data: dict[str, Any],
        metadata: dict[str, Any],
        objects: list[dict[str, Any]],
    ) -> str:
        """Store action result in legacy format.

        Convenience method for storing results from actions that still
        return (status, metadata, objects) tuples.

        Args:
            key_data: Dictionary of matrix variable values (cache key).
            metadata: Action metadata dictionary.
            objects: List of object dicts with 'type', 'name', 'content'.

        Returns:
            The hash key used for storage.
        """
        entry = CacheEntry.from_action_result(metadata, objects)
        return self.put(key_data, entry)
