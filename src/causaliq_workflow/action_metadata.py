"""Splitting the metadata an action returns into parameters and result.

CausalIQ actions return an ``ActionMetadata`` mapping of ``parameters`` and
``result``. A legacy flat mapping is treated as the result block so
third-party providers keep working during the transition. This module is
the single implementation of that rule; the action registry and the
workflow provenance layer both use it.
"""

from typing import Any, Dict, Tuple

__all__ = ["split_action_metadata"]


def split_action_metadata(
    raw_metadata: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Split action metadata into effective parameters and results.

    Args:
        raw_metadata: Metadata returned by an action, in version 2 or flat
            (legacy) form.

    Returns:
        Tuple of (parameters, result) dictionaries, both empty when the
        value is not a mapping.
    """
    if not isinstance(raw_metadata, dict):
        return {}, {}
    parameters = raw_metadata.get("parameters")
    result = raw_metadata.get("result")
    if isinstance(parameters, dict) and isinstance(result, dict):
        return dict(parameters), dict(result)
    return {}, dict(raw_metadata)
