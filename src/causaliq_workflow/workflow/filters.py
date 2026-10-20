"""Metadata flattening for filter expressions."""

from typing import Any, Dict

from causaliq_workflow.cache.reporting import build_entry_view
from causaliq_workflow.workflow._base import WorkflowExecutorBase


class FilterMixin(WorkflowExecutorBase):
    """Filter and metadata methods for WorkflowExecutor."""

    def _flatten_metadata(
        self,
        matrix_values: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Flatten metadata for filter expression evaluation.

        Combines matrix values with the version 2 metadata blocks into the
        shared reporting view: bare names for matrix and object values,
        and producer-qualified names for metadata.

        Args:
            matrix_values: Entry's matrix variable values
            metadata: Entry's metadata in version 2 or legacy form

        Returns:
            Flat dictionary of names to values
        """
        return build_entry_view(matrix_values, metadata)
