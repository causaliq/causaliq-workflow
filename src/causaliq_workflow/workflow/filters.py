"""Metadata flattening for filter expressions."""

from typing import Any, Dict, Iterable, Set

from causaliq_core.utils import FilterSyntaxError, relax_filter_literals

from causaliq_workflow.cache.reporting import build_entry_view
from causaliq_workflow.schema import _RESERVED_KEYS
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


def _reserved_filter_names(
    workflow: Dict[str, Any], supplied_names: Iterable[str]
) -> Set[str]:
    """Return names that must stay field references in filters.

    Declared parameters, matrix variables and supplied parameters are
    references. Any other bare word on the right of a comparison is
    treated as a literal value.
    """
    reserved = set(supplied_names)
    reserved.update(key for key in workflow if key not in _RESERVED_KEYS)
    matrix = workflow.get("matrix", {})
    if isinstance(matrix, dict):
        reserved.update(matrix)
    return reserved


def _relax_filter(filter_expr: str, reserved: Set[str]) -> str:
    """Return a relaxed filter expression, leaving invalid syntax alone."""
    try:
        return relax_filter_literals(filter_expr, reserved)
    except FilterSyntaxError:
        return filter_expr


def relax_step_filter_literals(
    workflow: Dict[str, Any], supplied_names: Iterable[str] = ()
) -> Dict[str, Any]:
    """Rewrite bare filter values as string literals in place.

    Rewriting happens once, before validation, so every consumer sees
    the same expression. Invalid filter syntax is left unchanged so the
    normal validation pass can report it.

    Args:
        workflow: Parsed workflow dictionary, modified in place.
        supplied_names: Parameter names supplied by a caller or CLI.

    Returns:
        The same workflow dictionary, for call chaining.
    """
    steps = workflow.get("steps", [])
    if not isinstance(steps, list):
        return workflow
    reserved = _reserved_filter_names(workflow, supplied_names)
    for step in steps:
        values = step.get("with") if isinstance(step, dict) else None
        if not isinstance(values, dict):
            continue
        filter_expr = values.get("filter")
        if not isinstance(filter_expr, str) or not filter_expr.strip():
            continue
        values["filter"] = _relax_filter(filter_expr, reserved)
    return workflow
