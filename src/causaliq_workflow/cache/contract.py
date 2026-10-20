"""Cache type and one-object contract for workflow caches.

Implements the simplified cache model in which a cache holds a single
object type and every entry holds provenance metadata plus exactly one
typed object. These helpers are the enforcement points used by the typed
write API (``WorkflowCache.put_typed`` and ``WorkflowCache.put_failure``);
the legacy ``put`` path remains permissive during the transition.

See ``docs/architecture/cache_type_model.md`` for the full design.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from causaliq_core.metadata import normalise_metadata

from causaliq_workflow.cache.entry import CacheEntry

__all__ = [
    "CacheTypeError",
    "TypedCache",
    "build_failure_entry",
    "pin_cache_type",
    "resolve_cache_type",
    "single_object_type",
    "store_failure_entry",
    "store_typed_entry",
]


class CacheTypeError(Exception):
    """Raised when a cache type or object-count rule is violated.

    The simplified model requires one object type per cache and exactly
    one object per entry, so a conflicting write is reported rather than
    silently producing a mixed entry.
    """

    pass


def pin_cache_type(existing: str | None, new_type: str) -> str:
    """Return the pinned cache type, raising on a conflicting type.

    Args:
        existing: Type already pinned to the cache, or None if unpinned.
        new_type: Type being written.

    Returns:
        The pinned type.

    Raises:
        CacheTypeError: If the cache is already pinned to another type.
    """
    if existing is not None and existing != new_type:
        raise CacheTypeError(
            f"Cache holds '{existing}' objects but '{new_type}' was written"
        )
    return new_type


def single_object_type(entry: CacheEntry) -> str:
    """Return the single object type held by an entry.

    Args:
        entry: Cache entry to inspect.

    Returns:
        The entry's single object type.

    Raises:
        CacheTypeError: If the entry does not hold exactly one object.
    """
    count = len(entry.objects)
    if count != 1:
        raise CacheTypeError(
            f"Cache entry must hold exactly one object, found {count}"
        )
    return next(iter(entry.objects))


def build_failure_entry(metadata: Dict[str, Any]) -> CacheEntry:
    """Build a failure entry: version 2 metadata and no object.

    A failure entry records provenance only. An object would be
    indistinguishable from the result of a successful run and could be
    scored, so none is written.

    Args:
        metadata: Version 2 metadata envelope recording the failure.

    Returns:
        Cache entry holding the provenance and no object.
    """
    return CacheEntry(metadata=normalise_metadata(metadata))


class TypedCache(Protocol):
    """Minimal cache surface used by the typed write helpers."""

    def validate_matrix_keys(self, key_data: Dict[str, Any]) -> None:
        """Validate key names against the cache's matrix schema."""
        ...  # pragma: no cover - protocol declaration

    def get_cache_type(self) -> Optional[str]:
        """Return the pinned object type, or None when unpinned."""
        ...  # pragma: no cover - protocol declaration

    def set_cache_type(self, cache_type: str) -> str:
        """Pin the object type, raising on a conflict."""
        ...  # pragma: no cover - protocol declaration

    def put(self, key_data: Dict[str, Any], entry: CacheEntry) -> str:
        """Store an entry, returning its hash key."""
        ...  # pragma: no cover - protocol declaration


def resolve_cache_type(
    existing: Optional[str],
    explicit: Optional[str],
) -> str:
    """Resolve the cache type to use, preferring an explicit value.

    Args:
        existing: Type already pinned to the cache, or None if unpinned.
        explicit: Type supplied by the caller, or None.

    Returns:
        The resolved type.

    Raises:
        CacheTypeError: If neither an existing nor explicit type is known.
    """
    resolved = explicit or existing
    if resolved is None:
        raise CacheTypeError(
            "Cannot record a failure before the cache type is known"
        )
    return resolved


def store_typed_entry(
    cache: TypedCache,
    key_data: Dict[str, Any],
    entry: CacheEntry,
) -> str:
    """Store an entry, enforcing one object of the cache's type.

    Args:
        cache: Cache receiving the entry.
        key_data: Dictionary of matrix variable values (cache key).
        entry: Cache entry holding exactly one typed object.

    Returns:
        The hash key used for storage.

    Raises:
        CacheTypeError: If the entry does not hold exactly one object, or
            its type conflicts with the cache's pinned type.
    """
    cache.validate_matrix_keys(key_data)
    cache.set_cache_type(single_object_type(entry))
    return cache.put(key_data, entry)


def store_failure_entry(
    cache: TypedCache,
    key_data: Dict[str, Any],
    metadata: Dict[str, Any],
    cache_type: Optional[str] = None,
) -> str:
    """Store a failure: version 2 metadata and no object.

    Args:
        cache: Cache receiving the failure entry.
        key_data: Dictionary of matrix variable values (cache key).
        metadata: Version 2 metadata envelope recording the failure.
        cache_type: Object type to pin when the cache is unpinned.

    Returns:
        The hash key used for storage.

    Raises:
        CacheTypeError: If the cache type is unknown.
    """
    resolved = resolve_cache_type(cache.get_cache_type(), cache_type)
    cache.set_cache_type(resolved)
    entry = build_failure_entry(metadata)
    return cache.put(key_data, entry)
