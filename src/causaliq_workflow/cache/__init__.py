"""
Workflow caching infrastructure.

This module provides caching for workflow step results, enabling
conservative execution (skipping work if results exist) and
reproducibility of research over many years.

Built on causaliq-core's TokenCache with workflow-specific features:
- Matrix key generation for cache lookups
- Matrix schema validation for consistency
- CacheEntry model with named objects (graph, confidences, etc.)
- Import/export to open formats (GraphML, JSON)
"""

from causaliq_workflow.cache.entry import CacheEntry, CacheObject
from causaliq_workflow.cache.export import (
    export_entries,
    get_extension_for_type,
    serialise_objects,
    store_action_result,
)
from causaliq_workflow.cache.import_ import import_entries
from causaliq_workflow.cache.workflow_cache import (
    MatrixSchemaError,
    WorkflowCache,
)

__all__ = [
    "CacheEntry",
    "CacheObject",
    "MatrixSchemaError",
    "WorkflowCache",
    "export_entries",
    "get_extension_for_type",
    "import_entries",
    "serialise_objects",
    "store_action_result",
]
