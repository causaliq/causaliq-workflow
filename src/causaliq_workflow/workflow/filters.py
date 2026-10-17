"""Metadata flattening for filter expressions."""

from typing import Any, Dict

from causaliq_workflow.workflow._base import WorkflowExecutorBase


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
