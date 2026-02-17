"""Cache entry model for workflow results.

Defines the CacheEntry class representing a single cached workflow result,
containing metadata and named objects (e.g., graph, confidences).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CacheObject:
    """A named object within a cache entry.

    Represents a single piece of data with a type identifier used for
    serialisation and export (e.g., graphml, json).

    Attributes:
        type: Object type identifier (e.g., 'graphml', 'json').
        content: The object content (string for serialised formats).

    Example:
        >>> obj = CacheObject(type="graphml", content="<graphml>...</graphml>")
        >>> obj.type
        'graphml'
    """

    type: str
    content: Any

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialisation.

        Returns:
            Dictionary with 'type' and 'content' keys.
        """
        return {"type": self.type, "content": self.content}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CacheObject:
        """Create from dictionary.

        Args:
            data: Dictionary with 'type' and 'content' keys.

        Returns:
            CacheObject instance.
        """
        return cls(type=data["type"], content=data["content"])


@dataclass
class CacheEntry:
    """A cached workflow result containing metadata and named objects.

    Represents a single cache entry identified by matrix variable values.
    Contains workflow metadata and zero or more named objects, each with
    a type and content.

    The entry structure maps directly to TokenCache storage:
    - metadata → TokenCache metadata field
    - objects → TokenCache data field

    Attributes:
        metadata: Workflow metadata dictionary.
        objects: Named objects dictionary (name → CacheObject).

    Example:
        >>> entry = CacheEntry()
        >>> entry.metadata["node_count"] = 5
        >>> entry.objects["graph"] = CacheObject(
        ...     type="graphml",
        ...     content="<graphml>...</graphml>"
        ... )
        >>> entry.objects["confidences"] = CacheObject(
        ...     type="json",
        ...     content='{"A->B": 0.95}'
        ... )
    """

    metadata: Dict[str, Any] = field(default_factory=dict)
    objects: Dict[str, CacheObject] = field(default_factory=dict)

    def add_object(
        self,
        name: str,
        obj_type: str,
        content: Any,
    ) -> None:
        """Add or replace a named object.

        Args:
            name: Object name (e.g., 'graph', 'confidences').
            obj_type: Object type (e.g., 'graphml', 'json').
            content: Object content.

        Example:
            >>> entry = CacheEntry()
            >>> entry.add_object("graph", "graphml", "<graphml>...")
        """
        self.objects[name] = CacheObject(type=obj_type, content=content)

    def get_object(self, name: str) -> CacheObject | None:
        """Get a named object.

        Args:
            name: Object name to retrieve.

        Returns:
            CacheObject if found, None otherwise.
        """
        return self.objects.get(name)

    def remove_object(self, name: str) -> bool:
        """Remove a named object.

        Args:
            name: Object name to remove.

        Returns:
            True if object was removed, False if not found.
        """
        if name in self.objects:
            del self.objects[name]
            return True
        return False

    def has_object(self, name: str) -> bool:
        """Check if a named object exists.

        Args:
            name: Object name to check.

        Returns:
            True if object exists.
        """
        return name in self.objects

    def object_names(self) -> list[str]:
        """Get list of object names.

        Returns:
            List of object names in the entry.
        """
        return list(self.objects.keys())

    def to_storage(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Convert to storage format for TokenCache.

        Returns:
            Tuple of (data, metadata) for TokenCache.put_data().
            - data: Objects dict serialised to dicts
            - metadata: Entry metadata dict
        """
        data = {name: obj.to_dict() for name, obj in self.objects.items()}
        return data, self.metadata

    @classmethod
    def from_storage(
        cls,
        data: Dict[str, Any] | None,
        metadata: Dict[str, Any] | None,
    ) -> CacheEntry:
        """Create from TokenCache storage format.

        Args:
            data: Objects dict from TokenCache.get_data().
            metadata: Metadata dict from TokenCache.

        Returns:
            CacheEntry instance.
        """
        entry = cls()
        entry.metadata = metadata or {}

        if data:
            for name, obj_dict in data.items():
                entry.objects[name] = CacheObject.from_dict(obj_dict)

        return entry

    @classmethod
    def from_action_result(
        cls,
        metadata: Dict[str, Any],
        objects: list[Dict[str, Any]],
    ) -> CacheEntry:
        """Create from action result format.

        Converts the current action return format (metadata dict and
        objects list) to a CacheEntry.

        Args:
            metadata: Action metadata dictionary.
            objects: List of object dicts with 'type', 'name', 'content'.

        Returns:
            CacheEntry instance.

        Example:
            >>> entry = CacheEntry.from_action_result(
            ...     {"node_count": 5},
            ...     [{"type": "graphml", "name": "graph", "content": "..."}]
            ... )
        """
        entry = cls(metadata=metadata.copy())

        for obj in objects:
            name = obj.get("name", obj.get("type", "unknown"))
            entry.objects[name] = CacheObject(
                type=obj["type"],
                content=obj.get("content"),
            )

        return entry

    def to_action_result(self) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
        """Convert to action result format.

        Returns:
            Tuple of (metadata, objects_list) matching action return format.
        """
        objects_list = [
            {"type": obj.type, "name": name, "content": obj.content}
            for name, obj in self.objects.items()
        ]
        return self.metadata.copy(), objects_list
