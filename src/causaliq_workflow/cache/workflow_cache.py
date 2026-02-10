"""
WorkflowCache: High-level cache for workflow step results.

Wraps TokenCache from causaliq-core with workflow-specific functionality:
- Matrix key hashing for cache lookups
- Entry type dispatch via registered encoders
- Metadata storage alongside data
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from causaliq_core.cache import TokenCache

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_core.cache.encoders.base import EntryEncoder


class WorkflowCache:
    """High-level cache for workflow step results.

    Provides a simplified interface for storing and retrieving workflow
    results. Uses matrix variable values as cache keys, with SHA-256
    hashing for compact storage.

    Supports multiple entry types (e.g., 'graph', 'trace') via registered
    encoders. Each encoder handles encoding/decoding for its type.

    Attributes:
        db_path: Path to SQLite database file, or ":memory:" for in-memory.

    Example:
        >>> from causaliq_core.cache.encoders import JsonEncoder
        >>> with WorkflowCache(":memory:") as cache:
        ...     cache.register_encoder("json", JsonEncoder())
        ...     key = {"algorithm": "pc", "network": "asia"}
        ...     cache.put(key, "json", {"nodes": 5, "edges": 4})
        ...     result = cache.get(key, "json")
        ...     print(result)
        {'nodes': 5, 'edges': 4}
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
    # Encoder registration
    # ========================================================================

    def register_encoder(self, entry_type: str, encoder: EntryEncoder) -> None:
        """Register an encoder for a specific entry type.

        Once registered, `put()` and `get()` will automatically
        encode/decode entries of this type using the registered encoder.

        Args:
            entry_type: Type identifier (e.g., 'graph', 'json', 'trace').
            encoder: EntryEncoder instance for this type.

        Example:
            >>> from causaliq_core.cache.encoders import JsonEncoder
            >>> with WorkflowCache(":memory:") as cache:
            ...     cache.register_encoder("json", JsonEncoder())
        """
        self.token_cache.register_encoder(entry_type, encoder)

    def get_encoder(self, entry_type: str) -> EntryEncoder | None:
        """Get the registered encoder for an entry type.

        Args:
            entry_type: Type identifier to look up.

        Returns:
            The registered encoder, or None if not registered.
        """
        return self.token_cache.get_encoder(entry_type)

    def has_encoder(self, entry_type: str) -> bool:
        """Check if an encoder is registered for an entry type.

        Args:
            entry_type: Type identifier to check.

        Returns:
            True if encoder is registered, False otherwise.
        """
        return self.token_cache.has_encoder(entry_type)

    # ========================================================================
    # Cache operations
    # ========================================================================

    def put(
        self,
        key_data: dict[str, Any],
        entry_type: str,
        data: Any,
        metadata: Any | None = None,
    ) -> str:
        """Store a workflow result in the cache.

        Uses the registered encoder for `entry_type` to encode the data.
        If an entry with the same key already exists, it is replaced.

        Args:
            key_data: Dictionary of matrix variable values (cache key).
            entry_type: Type of entry (must have registered encoder).
            data: Data to encode and store.
            metadata: Optional metadata to encode and store alongside data.

        Returns:
            The hash key used for storage.

        Raises:
            KeyError: If no encoder is registered for entry_type.

        Example:
            >>> with WorkflowCache(":memory:") as cache:
            ...     cache.register_encoder("json", JsonEncoder())
            ...     key = {"algorithm": "pc"}
            ...     hash_key = cache.put(key, "json", {"result": "ok"})
        """
        hash_key = self.compute_hash(key_data)
        key_json = self._key_json(key_data)
        self.token_cache.put_data(
            hash=hash_key,
            entry_type=entry_type,
            data=data,
            metadata=metadata,
            key_json=key_json,
        )
        return hash_key

    def get(
        self,
        key_data: dict[str, Any],
        entry_type: str,
    ) -> Any | None:
        """Retrieve a workflow result from the cache.

        Uses the registered encoder for `entry_type` to decode the data.

        Args:
            key_data: Dictionary of matrix variable values (cache key).
            entry_type: Type of entry (must have registered encoder).

        Returns:
            Decoded data if found, None otherwise.

        Raises:
            KeyError: If no encoder is registered for entry_type.

        Example:
            >>> with WorkflowCache(":memory:") as cache:
            ...     cache.register_encoder("json", JsonEncoder())
            ...     key = {"algorithm": "pc"}
            ...     cache.put(key, "json", {"result": "ok"})
            ...     result = cache.get(key, "json")
        """
        hash_key = self.compute_hash(key_data)
        key_json = self._key_json(key_data)
        return self.token_cache.get_data(
            hash=hash_key,
            entry_type=entry_type,
            key_json=key_json,
        )

    def get_with_metadata(
        self,
        key_data: dict[str, Any],
        entry_type: str,
    ) -> tuple[Any, Any | None] | None:
        """Retrieve a workflow result with its metadata.

        Args:
            key_data: Dictionary of matrix variable values (cache key).
            entry_type: Type of entry (must have registered encoder).

        Returns:
            Tuple of (data, metadata) if found, None otherwise.
            metadata may be None if not stored.

        Raises:
            KeyError: If no encoder is registered for entry_type.
        """
        hash_key = self.compute_hash(key_data)
        key_json = self._key_json(key_data)
        return self.token_cache.get_data_with_metadata(
            hash=hash_key,
            entry_type=entry_type,
            key_json=key_json,
        )

    def exists(
        self,
        key_data: dict[str, Any],
        entry_type: str,
    ) -> bool:
        """Check if a cache entry exists.

        Args:
            key_data: Dictionary of matrix variable values (cache key).
            entry_type: Type of entry to check.

        Returns:
            True if entry exists, False otherwise.

        Example:
            >>> with WorkflowCache(":memory:") as cache:
            ...     cache.register_encoder("json", JsonEncoder())
            ...     key = {"algorithm": "pc"}
            ...     cache.exists(key, "json")  # False
            ...     cache.put(key, "json", {"result": "ok"})
            ...     cache.exists(key, "json")  # True
        """
        hash_key = self.compute_hash(key_data)
        key_json = self._key_json(key_data)
        return self.token_cache.exists(
            hash=hash_key,
            entry_type=entry_type,
            key_json=key_json,
        )

    def delete(
        self,
        key_data: dict[str, Any],
        entry_type: str,
    ) -> bool:
        """Delete a cache entry.

        Args:
            key_data: Dictionary of matrix variable values (cache key).
            entry_type: Type of entry to delete.

        Returns:
            True if entry was deleted, False if it didn't exist.
        """
        hash_key = self.compute_hash(key_data)
        key_json = self._key_json(key_data)
        return self.token_cache.delete(
            hash=hash_key,
            entry_type=entry_type,
            key_json=key_json,
        )

    # ========================================================================
    # Statistics and listing
    # ========================================================================

    def entry_count(self, entry_type: str | None = None) -> int:
        """Count cache entries, optionally filtered by type.

        Args:
            entry_type: If provided, count only entries of this type.

        Returns:
            Number of matching entries.
        """
        return self.token_cache.entry_count(entry_type)

    def list_entries(
        self,
        entry_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all cache entries with details.

        Returns entry details including matrix_values (parsed from key_json),
        created_at timestamp, and metadata.

        Args:
            entry_type: If provided, list only entries of this type.

        Returns:
            List of entry dictionaries with keys: hash, entry_type,
            matrix_values (dict), created_at (str), metadata (raw bytes).
        """
        raw_entries = self.token_cache.list_entries(entry_type)
        entries = []
        for entry in raw_entries:
            # Parse key_json back to matrix_values dict
            key_json = entry["key_json"]
            matrix_values = json.loads(key_json) if key_json else {}
            entries.append(
                {
                    "hash": entry["hash"],
                    "entry_type": entry["entry_type"],
                    "matrix_values": matrix_values,
                    "created_at": entry["created_at"],
                    "metadata": entry["metadata"],
                }
            )
        return entries

    def list_entry_types(self) -> list[str]:
        """List all distinct entry types in the cache.

        Returns:
            List of entry type names found in the cache.
        """
        return self.token_cache.list_entry_types()

    def token_count(self) -> int:
        """Count tokens in the shared dictionary.

        Returns:
            Number of tokens.
        """
        return self.token_cache.token_count()

    # ========================================================================
    # Export operations
    # ========================================================================

    def export(
        self,
        output_path: str | Path,
        entry_type: str,
        matrix_keys: list[str] | None = None,
    ) -> int:
        """Export cache entries to directory or zip file.

        Creates a hierarchical directory structure based on matrix variable
        values in the order specified by matrix_keys. Each entry is exported
        as a pair of files: <timestamp>.graphml and <timestamp>.json.

        The output format is determined by the path extension:
        - Path ending in .zip: creates a zip archive
        - Otherwise: creates a directory structure

        Args:
            output_path: Path to output directory or .zip file.
            entry_type: Type of entries to export (e.g., 'graph').
            matrix_keys: Ordered list of matrix variable names for directory
                hierarchy. If None, uses alphabetical order.

        Returns:
            Number of entries exported.

        Raises:
            KeyError: If no encoder is registered for entry_type.
            ValueError: If entry has matrix values not in matrix_keys.

        Example:
            >>> with WorkflowCache("cache.db") as cache:
            ...     # Export to dir: asia/pc/2026-02-06T14-30-00.graphml
            ...     cache.export("./out", "graph", ["dataset", "algorithm"])
            ...     # Export to zip file
            ...     cache.export("./out.zip", "graph", ["dataset"])
        """
        output_path = Path(output_path)
        is_zip = output_path.suffix.lower() == ".zip"

        if is_zip:
            return self._export_to_zip(output_path, entry_type, matrix_keys)
        else:
            return self._export_to_dir(output_path, entry_type, matrix_keys)

    def _build_entry_path(
        self,
        matrix_values: dict[str, Any],
        created_at: str,
        matrix_keys: list[str] | None,
    ) -> Path:
        """Build hierarchical path from matrix values.

        Args:
            matrix_values: Dictionary of matrix variable values.
            created_at: ISO timestamp for filename.
            matrix_keys: Ordered list of keys for path hierarchy.

        Returns:
            Relative path like: asia/pc/2026-02-06T14-30-00
        """
        if matrix_keys is None:
            matrix_keys = sorted(matrix_values.keys())

        # Build path segments from matrix values in specified order
        segments = []
        for key in matrix_keys:
            if key in matrix_values:
                # Sanitise value for filesystem (replace problematic chars)
                value = str(matrix_values[key])
                safe_value = value.replace("/", "_").replace("\\", "_")
                segments.append(safe_value)

        # Convert timestamp to filesystem-safe format
        safe_timestamp = created_at.replace(":", "-")

        if segments:
            return Path(*segments) / safe_timestamp
        else:
            return Path(safe_timestamp)

    def _export_to_dir(
        self,
        output_dir: Path,
        entry_type: str,
        matrix_keys: list[str] | None,
    ) -> int:
        """Export entries to a directory structure.

        Args:
            output_dir: Root directory for export.
            entry_type: Type of entries to export.
            matrix_keys: Ordered list of matrix variable names.

        Returns:
            Number of entries exported.
        """
        entries = self.list_entries(entry_type)
        encoder = self.get_encoder(entry_type)
        if encoder is None:
            raise KeyError(
                f"No encoder registered for entry type: {entry_type}"
            )

        count = 0
        for entry in entries:
            # Get data and metadata
            result = self.get_with_metadata(entry["matrix_values"], entry_type)
            if result is None:
                continue

            data, metadata = result

            # Build path
            rel_path = self._build_entry_path(
                entry["matrix_values"],
                entry["created_at"],
                matrix_keys,
            )

            # Create directories
            full_dir = output_dir / rel_path.parent
            full_dir.mkdir(parents=True, exist_ok=True)

            # Export data using encoder's export method
            ext = encoder.default_export_format
            data_path = output_dir / f"{rel_path}.{ext}"
            encoder.export(data, data_path)

            # Merge workflow metadata into the JSON file
            json_path = data_path.with_suffix(".json")
            if json_path.exists():
                exported_data = json.loads(json_path.read_text())
                # Add workflow metadata at top level
                exported_data["matrix_values"] = entry["matrix_values"]
                exported_data["created_at"] = entry["created_at"]
                exported_data["entry_type"] = entry_type
                if metadata is not None:
                    exported_data["workflow_metadata"] = metadata
                json_path.write_text(
                    json.dumps(exported_data, indent=2, sort_keys=False),
                    encoding="utf-8",
                )

            count += 1

        return count

    def _export_to_zip(
        self,
        zip_path: Path,
        entry_type: str,
        matrix_keys: list[str] | None,
    ) -> int:
        """Export entries to a zip archive.

        Args:
            zip_path: Path to output zip file.
            entry_type: Type of entries to export.
            matrix_keys: Ordered list of matrix variable names.

        Returns:
            Number of entries exported.
        """
        import tempfile
        import zipfile

        entries = self.list_entries(entry_type)
        encoder = self.get_encoder(entry_type)
        if encoder is None:
            raise KeyError(
                f"No encoder registered for entry type: {entry_type}"
            )

        # Ensure parent directory exists
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for entry in entries:
                # Get data and metadata
                result = self.get_with_metadata(
                    entry["matrix_values"], entry_type
                )
                if result is None:
                    continue

                data, metadata = result

                # Build path
                rel_path = self._build_entry_path(
                    entry["matrix_values"],
                    entry["created_at"],
                    matrix_keys,
                )

                # Export data to temporary directory then to zip
                ext = encoder.default_export_format

                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_path = Path(tmp_dir) / f"export.{ext}"
                    encoder.export(data, tmp_path)

                    # Add all files encoder created (may include .graphml)
                    for tmp_file in Path(tmp_dir).glob("export.*"):
                        arc_name = f"{rel_path}{tmp_file.suffix}"

                        # For JSON files, merge in workflow metadata
                        if tmp_file.suffix == ".json":
                            exported_data = json.loads(tmp_file.read_text())
                            exported_data["matrix_values"] = entry[
                                "matrix_values"
                            ]
                            exported_data["created_at"] = entry["created_at"]
                            exported_data["entry_type"] = entry_type
                            if metadata is not None:
                                exported_data["workflow_metadata"] = metadata
                            zf.writestr(
                                arc_name,
                                json.dumps(
                                    exported_data, indent=2, sort_keys=False
                                ),
                            )
                        else:
                            zf.write(tmp_file, arc_name)

                count += 1

        return count

    # ========================================================================
    # Import operations
    # ========================================================================

    def import_entries(
        self,
        input_path: str | Path,
        entry_type: str,
    ) -> int:
        """Import cache entries from directory or zip file.

        Reads entries exported by `export()` and stores them back into
        the cache. The input format is determined by the path:
        - Path ending in .zip: reads from a zip archive
        - Otherwise: reads from a directory structure

        Uses metadata files to reconstruct matrix_values and entry metadata.
        Data files are imported using the registered encoder's import_ method.

        Args:
            input_path: Path to input directory or .zip file.
            entry_type: Type of entries to import (e.g., 'graph').

        Returns:
            Number of entries imported.

        Raises:
            KeyError: If no encoder is registered for entry_type.
            FileNotFoundError: If input_path does not exist.

        Example:
            >>> with WorkflowCache("cache.db") as cache:
            ...     # Import from directory
            ...     cache.import_entries("./exported", "graph")
            ...     # Import from zip file
            ...     cache.import_entries("./exported.zip", "graph")
        """
        input_path = Path(input_path)
        is_zip = input_path.suffix.lower() == ".zip"

        if is_zip:
            return self._import_from_zip(input_path, entry_type)
        else:
            return self._import_from_dir(input_path, entry_type)

    def _import_from_dir(
        self,
        input_dir: Path,
        entry_type: str,
    ) -> int:
        """Import entries from a directory structure.

        Args:
            input_dir: Root directory containing exported entries.
            entry_type: Type of entries to import.

        Returns:
            Number of entries imported.

        Raises:
            KeyError: If no encoder is registered for entry_type.
            FileNotFoundError: If input_dir does not exist.
        """
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        encoder = self.get_encoder(entry_type)
        if encoder is None:
            raise KeyError(
                f"No encoder registered for entry type: {entry_type}"
            )

        ext = encoder.default_export_format
        count = 0

        # Find all data files recursively (excluding _meta.json files)
        for data_path in input_dir.rglob(f"*.{ext}"):
            # Skip _meta.json files (legacy format)
            if "_meta" in data_path.stem:
                continue

            # Read the JSON file to extract workflow metadata
            json_content = json.loads(data_path.read_text(encoding="utf-8"))

            # Extract workflow metadata (added during export)
            matrix_values = json_content.pop("matrix_values", {})
            json_content.pop("created_at", None)  # Remove, will be regenerated
            json_content.pop("entry_type", None)
            workflow_metadata = json_content.pop("workflow_metadata", None)

            # Use the cleaned json_content as data (without workflow metadata)
            data = json_content

            # Store in cache
            self.put(matrix_values, entry_type, data, workflow_metadata)
            count += 1

        return count

    def _import_from_zip(
        self,
        zip_path: Path,
        entry_type: str,
    ) -> int:
        """Import entries from a zip archive.

        Args:
            zip_path: Path to input zip file.
            entry_type: Type of entries to import.

        Returns:
            Number of entries imported.

        Raises:
            KeyError: If no encoder is registered for entry_type.
            FileNotFoundError: If zip_path does not exist.
        """
        import zipfile

        if not zip_path.exists():
            raise FileNotFoundError(f"Zip file not found: {zip_path}")

        encoder = self.get_encoder(entry_type)
        if encoder is None:
            raise KeyError(
                f"No encoder registered for entry type: {entry_type}"
            )

        ext = encoder.default_export_format
        count = 0

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Find all data files (JSON files, excluding _meta.json)
            data_names = [
                n
                for n in zf.namelist()
                if n.endswith(f".{ext}") and "_meta" not in n
            ]

            for data_name in data_names:
                # Read JSON content to extract workflow metadata
                json_content = json.loads(zf.read(data_name).decode("utf-8"))

                # Extract workflow metadata (added during export)
                matrix_values = json_content.pop("matrix_values", {})
                json_content.pop("created_at", None)
                json_content.pop("entry_type", None)
                workflow_metadata = json_content.pop("workflow_metadata", None)

                # Use the cleaned json_content as data (without workflow meta)
                data = json_content

                # Store in cache
                self.put(matrix_values, entry_type, data, workflow_metadata)
                count += 1

        return count
