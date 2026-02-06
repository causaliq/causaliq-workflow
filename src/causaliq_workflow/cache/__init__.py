"""
Workflow caching infrastructure.

This module provides caching for workflow step results, enabling
conservative execution (skipping work if results exist) and
reproducibility of research over many years.

Built on causaliq-core's TokenCache with workflow-specific features:
- Matrix key generation for cache lookups
- Entry type dispatch via registered encoders
- Import/export to open formats (GraphML, JSON)
"""

from causaliq_workflow.cache.workflow_cache import WorkflowCache

__all__ = [
    "WorkflowCache",
]
