"""Metadata flattening and filter resolution."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from causaliq_workflow.workflow._base import WorkflowExecutorBase

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.cache import WorkflowCache


def _flatten_provider(
    flat: Dict[str, Any],
    provider_name: str,
    provider_data: Any,
) -> None:
    """Flatten one provider's metadata section into a flat dictionary."""
    if not isinstance(provider_data, dict):
        flat[provider_name] = provider_data
        return

    for action_name, action_data in provider_data.items():
        _flatten_action(flat, provider_name, action_name, action_data)


def _flatten_action(
    flat: Dict[str, Any],
    provider_name: str,
    action_name: str,
    action_data: Any,
) -> None:
    """Flatten one action's metadata section into a flat dictionary."""
    qual_key = f"{provider_name}.{action_name}"
    if not isinstance(action_data, dict):
        flat[qual_key] = action_data
        return

    for key, value in action_data.items():
        # Use simple key if no conflict
        if key not in flat:
            flat[key] = value
        # Use fully qualified key as fallback
        flat[f"{qual_key}.{key}"] = value


class FilterMixin(WorkflowExecutorBase):
    """Filter and metadata methods for WorkflowExecutor."""

    def _flatten_metadata(
        self,
        matrix_values: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Flatten metadata for filter expression evaluation.

        Combines matrix values with nested metadata structure into a flat
        dictionary suitable for filter expression evaluation.

        Args:
            matrix_values: Entry's matrix variable values
            metadata: Entry's nested metadata dictionary

        Returns:
            Flat dictionary with all metadata fields
        """
        flat: Dict[str, Any] = dict(matrix_values)

        # Flatten nested metadata (provider -> action -> fields)
        for provider_name, provider_data in metadata.items():
            _flatten_provider(flat, provider_name, provider_data)

        return flat

    def _resolve_filter(
        self,
        filter_expr: Optional[str],
        cache: "WorkflowCache",
        entries: List[Dict[str, Any]],
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Pre-resolve ``random()`` calls in a filter expression.

        Scans *entries* from *cache* to build the distinct-value
        populations needed by ``random(count, seed)`` patterns,
        then returns a rewritten expression and a dictionary of
        pre-computed frozen sets.

        When *filter_expr* contains no ``random()`` calls the
        original expression is returned unchanged with an empty
        dictionary.

        Args:
            filter_expr: Filter expression string, or ``None``.
            cache: Open cache used to retrieve full entries.
            entries: Entry list from ``cache.list_entries()``.

        Returns:
            Tuple of *(resolved_expression, extra_names)*.
        """
        if not filter_expr or "random(" not in filter_expr:
            return filter_expr, {}

        from causaliq_core.utils import resolve_random_calls

        all_meta: List[Dict[str, Any]] = []
        for entry_info in entries:
            entry_matrix = entry_info.get("matrix_values", {})
            full_entry = cache.get(entry_matrix)
            if full_entry is not None:
                all_meta.append(
                    self._flatten_metadata(entry_matrix, full_entry.metadata)
                )

        return resolve_random_calls(filter_expr, all_meta)
