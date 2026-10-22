"""Provenance collection for workflow cache entries.

The executor records who ran an action, when, for how long, and in what
environment. These helpers keep that collection in one place so the
execution mixin stays within the size limits.
"""

from __future__ import annotations

import importlib.metadata
from datetime import datetime
from time import perf_counter
from typing import Any, Dict, Optional, Tuple

from causaliq_core.metadata import build_metadata
from causaliq_core.utils import environment as _environment

from causaliq_workflow.workflow.errors import WorkflowExecutionError

__all__ = [
    "build_result_metadata",
    "build_step_metadata",
    "collect_environment",
    "collect_step_provenance",
    "execute_with_provenance",
    "local_now",
    "resolve_action_name",
    "resolve_provider_version",
    "split_action_metadata",
    "workflow_version",
]


def local_now() -> str:
    """Return the current local time as a timezone-aware ISO 8601 string.

    Fractions of a second are not recorded, keeping timestamps compact and
    stable across platforms.

    Returns:
        Local timestamp such as ``2026-10-22T06:06:16+01:00``.
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def collect_environment() -> Optional[Dict[str, Any]]:
    """Collect runtime environment information without failing the run.

    Returns:
        Environment information, or None when it cannot be collected.
    """
    try:
        env = _environment()
    except Exception:
        return None
    return dict(env) if isinstance(env, dict) else None


def resolve_provider_version(
    action_class: Any,
    provider_name: str,
) -> Optional[str]:
    """Return the provider version, falling back to package metadata.

    Args:
        action_class: Provider class declaring the action.
        provider_name: Provider name used for the metadata fallback.

    Returns:
        Version string, or None when it cannot be determined.
    """
    version = getattr(action_class, "version", "")
    if isinstance(version, str) and version.strip():
        return version
    try:
        return importlib.metadata.version(provider_name)
    except (importlib.metadata.PackageNotFoundError, ValueError):
        return None


def workflow_version() -> Optional[str]:
    """Return the causaliq-workflow package version.

    Returns:
        Version string, or None when it cannot be determined.
    """
    try:
        from causaliq_workflow import __version__
    except Exception:  # pragma: no cover - import cycles during setup
        return None
    return __version__ or None


def resolve_action_name(
    resolved_inputs: Dict[str, Any],
    action_class: Any,
) -> str:
    """Return the action name, deriving it for single-action providers.

    Args:
        resolved_inputs: Resolved step parameters.
        action_class: Provider class declaring the action.

    Returns:
        Action name, or an empty string when it cannot be resolved.
    """
    name = resolved_inputs.get("action")
    if isinstance(name, str) and name.strip():
        return name
    supported = sorted(getattr(action_class, "supported_actions", set()) or [])
    return supported[0] if len(supported) == 1 else ""


def split_action_metadata(
    raw_metadata: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Split action metadata into effective parameters and results.

    CausalIQ actions return ``{"parameters": {...}, "result": {...}}``. A
    legacy flat mapping is treated as the result so third-party providers
    keep working during the transition.

    Args:
        raw_metadata: Metadata returned by an action.

    Returns:
        Tuple of (parameters, result) dictionaries.
    """
    if not isinstance(raw_metadata, dict):
        return {}, {}
    parameters = raw_metadata.get("parameters")
    result = raw_metadata.get("result")
    if isinstance(parameters, dict) and isinstance(result, dict):
        return dict(parameters), dict(result)
    return {}, dict(raw_metadata)


def execute_with_provenance(
    registry: Any,
    action_name: str,
    resolved_inputs: Dict[str, Any],
    context: Any,
    environment: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Execute an action and collect its provenance.

    Args:
        registry: Action registry used to execute the action.
        action_name: Provider name from the workflow step.
        resolved_inputs: Resolved step parameters.
        context: Workflow context for the action.
        environment: Runtime environment information, if available.

    Returns:
        Tuple of (step result, provenance mapping).

    Raises:
        WorkflowExecutionError: If the action name cannot be resolved.
    """
    started = local_now()
    start = perf_counter()
    step_result = registry.execute_action(
        action_name, resolved_inputs, context
    )
    elapsed = round(perf_counter() - start, 6)
    action_class = registry.get_action_class(action_name)
    provider_name = getattr(action_class, "name", action_name)
    provenance = collect_step_provenance(
        action_class,
        provider_name,
        resolved_inputs,
        started,
        elapsed,
        environment,
    )
    if not provenance["action"]:
        raise WorkflowExecutionError(
            f"Cannot determine the action name for provider '{provider_name}'"
        )
    return step_result, provenance


def build_result_metadata(
    provenance: Dict[str, Any],
    step_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the metadata envelope for a completed step.

    Args:
        provenance: Provenance collected for the step.
        step_result: Result dictionary returned by the registry.

    Returns:
        Metadata envelope ready for storage.
    """
    parameters, result = split_action_metadata(
        step_result.get("_action_metadata", {})
    )
    return build_step_metadata(provenance, parameters, result)


def collect_step_provenance(
    action_class: Any,
    provider_name: str,
    resolved_inputs: Dict[str, Any],
    started: str,
    elapsed: float,
    environment: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Collect provenance for one executed action.

    Args:
        action_class: Provider class declaring the action.
        provider_name: Provider name that owns the action.
        resolved_inputs: Resolved step parameters.
        started: Local ISO 8601 time at which the action started.
        elapsed: Monotonic wall-clock duration of the action in seconds.
        environment: Runtime environment information, if available.

    Returns:
        Provenance mapping ready for :func:`build_step_metadata`.
    """
    return {
        "provider": provider_name,
        "action": resolve_action_name(resolved_inputs, action_class),
        "provider_version": resolve_provider_version(
            action_class, provider_name
        ),
        "workflow_version": workflow_version(),
        "started": started,
        "elapsed": elapsed,
        "environment": environment,
    }


def build_step_metadata(
    provenance: Dict[str, Any],
    parameters: Dict[str, Any],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a version 2 envelope from collected step provenance.

    Args:
        provenance: Provenance collected by the executor.
        parameters: Effective parameters reported by the action.
        result: Values reported by the action.

    Returns:
        Metadata envelope ready for storage.
    """
    return build_metadata(
        provider=provenance["provider"],
        action=provenance["action"],
        parameters=parameters,
        result=result,
        provider_version=provenance.get("provider_version"),
        workflow_version=provenance.get("workflow_version"),
        started=provenance.get("started"),
        elapsed=provenance.get("elapsed"),
        environment=provenance.get("environment"),
    )
