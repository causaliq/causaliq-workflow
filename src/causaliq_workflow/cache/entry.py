"""Cache entry model for workflow results.

Defines the CacheEntry class representing a single cached workflow result,
containing metadata and typed objects (e.g., dag, pdg, trace).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CacheObject:
    """A typed object within a cache entry.

    Represents a single piece of data with a serialisation format and
    the action that created it. Objects are keyed by semantic type
    (e.g., 'dag', 'pdg') within a CacheEntry.

    Attributes:
        format: Serialisation format (e.g., 'graphml', 'json', 'csv').
        action: Name of the action that created this object.
        content: The object content (string for serialised formats).

    Example:
        >>> obj = CacheObject(
        ...     format="graphml",
        ...     action="migrate_trace",
        ...     content="<graphml>...</graphml>"
        ... )
        >>> obj.format
        'graphml'
        >>> obj.action
        'migrate_trace'
    """

    format: str
    action: str
    content: Any

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialisation.

        Returns:
            Dictionary with 'format', 'action', and 'content' keys.
        """
        return {
            "format": self.format,
            "action": self.action,
            "content": self.content,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CacheObject:
        """Create from dictionary.

        Args:
            data: Dictionary with 'format', 'action', and 'content' keys.

        Returns:
            CacheObject instance.
        """
        return cls(
            format=data["format"],
            action=data.get("action", "unknown"),
            content=data.get("content"),
        )


@dataclass
class CacheEntry:
    """A cached workflow result containing metadata and typed objects.

    Represents a single cache entry identified by matrix variable values.
    Contains workflow metadata and zero or more typed objects. Each object
    has a semantic type (e.g., 'dag', 'pdg') and serialisation format.

    Objects are keyed by their semantic type. Each entry may contain at
    most one object of each type.

    The entry structure maps directly to TokenCache storage:
    - metadata → TokenCache metadata field
    - objects → TokenCache data field

    Attributes:
        metadata: Workflow metadata dictionary.
        objects: Typed objects dictionary (type → CacheObject).

    Example:
        >>> entry = CacheEntry()
        >>> entry.metadata["node_count"] = 5
        >>> entry.add_object("pdg", "graphml", "<graphml>...</graphml>")
        >>> entry.add_object("trace", "json", '{"iterations": [...]}')
    """

    metadata: Dict[str, Any] = field(default_factory=dict)
    objects: Dict[str, CacheObject] = field(default_factory=dict)

    def add_object(
        self,
        obj_type: str,
        obj_format: str,
        content: Any,
        action: str = "unknown",
    ) -> None:
        """Add or replace a typed object.

        Args:
            obj_type: Semantic object type (e.g., 'dag', 'pdg', 'trace').
            obj_format: Serialisation format (e.g., 'graphml', 'json').
            content: Object content.
            action: Name of the action creating this object.

        Example:
            >>> entry = CacheEntry()
            >>> entry.add_object("pdg", "graphml", "<g/>", "merge")
        """
        self.objects[obj_type] = CacheObject(
            format=obj_format,
            action=action,
            content=content,
        )

    def get_object(self, obj_type: str) -> CacheObject | None:
        """Get an object by type.

        Args:
            obj_type: Object type to retrieve (e.g., 'dag', 'pdg').

        Returns:
            CacheObject if found, None otherwise.
        """
        return self.objects.get(obj_type)

    def remove_object(self, obj_type: str) -> bool:
        """Remove an object by type.

        Args:
            obj_type: Object type to remove.

        Returns:
            True if object was removed, False if not found.
        """
        if obj_type in self.objects:
            del self.objects[obj_type]
            return True
        return False

    def has_object(self, obj_type: str) -> bool:
        """Check if an object type exists.

        Args:
            obj_type: Object type to check.

        Returns:
            True if object exists.
        """
        return obj_type in self.objects

    def object_types(self) -> list[str]:
        """Get list of object types in this entry.

        Returns:
            List of object types.
        """
        return list(self.objects.keys())

    def to_storage(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Convert to storage format for TokenCache.

        Returns:
            Tuple of (data, metadata) for TokenCache.put_data().
            - data: Objects dict serialised to dicts
            - metadata: Entry metadata dict
        """
        data = {
            obj_type: obj.to_dict() for obj_type, obj in self.objects.items()
        }
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
            for obj_type, obj_dict in data.items():
                obj = CacheObject.from_dict(obj_dict)
                entry.objects[obj_type] = obj

        return entry

    @classmethod
    def from_action_result(
        cls,
        metadata: Dict[str, Any],
        objects: list[Dict[str, Any]],
    ) -> CacheEntry:
        """Create from action result format.

        Converts the action return format (metadata dict and objects list)
        to a CacheEntry. Objects are keyed by their 'type' field.

        Args:
            metadata: Action metadata dictionary.
            objects: List of object dicts with 'type', 'format', 'action',
                'content'.

        Returns:
            CacheEntry instance.

        Example:
            >>> entry = CacheEntry.from_action_result(
            ...     {"node_count": 5},
            ...     [{"type": "pdg", "format": "graphml",
            ...       "action": "merge_graphs", "content": "..."}]
            ... )
        """
        entry = cls(metadata=metadata.copy())

        for obj in objects:
            obj_type = obj["type"]
            entry.objects[obj_type] = CacheObject(
                format=obj["format"],
                action=obj.get("action", "unknown"),
                content=obj.get("content"),
            )

        return entry

    def to_action_result(self) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
        """Convert to action result format.

        Returns:
            Tuple of (metadata, objects_list) matching action return format.
        """
        objects_list = [
            {
                "type": obj_type,
                "format": obj.format,
                "action": obj.action,
                "content": obj.content,
            }
            for obj_type, obj in self.objects.items()
        ]
        return self.metadata.copy(), objects_list
