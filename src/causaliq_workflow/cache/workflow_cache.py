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
    # Statistics
    # ========================================================================

    def entry_count(self, entry_type: str | None = None) -> int:
        """Count cache entries, optionally filtered by type.

        Args:
            entry_type: If provided, count only entries of this type.

        Returns:
            Number of matching entries.
        """
        return self.token_cache.entry_count(entry_type)

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
