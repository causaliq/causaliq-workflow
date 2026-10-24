"""Workflow-call syntax and call-stack frames.

A step calls another workflow when its ``uses`` value is a relative path
(``./`` or ``../``). The leading dot segment keeps workflow calls
disjoint from action provider names, mirroring the GitHub Actions
convention for local reusable workflows.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple, Union

WORKFLOW_SUFFIXES = (".yml", ".yaml")


@dataclass(frozen=True)
class WorkflowFrame:
    """A workflow on the call stack.

    Attributes:
        path: Canonical absolute path of the workflow file.
        source_dir: Directory used to resolve relative workflow calls.
    """

    path: Path
    source_dir: Path


def _normalise_uses(uses: Any) -> str:
    """Return a ``uses`` value with Windows separators normalised."""
    if not isinstance(uses, str):
        return ""
    return uses.replace("\\", "/").strip()


def is_workflow_path(uses: str) -> bool:
    """Return True when a ``uses`` value names a workflow file.

    Args:
        uses: Value of a step's ``uses`` property.

    Returns:
        True when the value starts with ``./`` or ``../``.
    """
    normalised = _normalise_uses(uses)
    return normalised.startswith("./") or normalised.startswith("../")


def is_workflow_call_step(step: Any) -> bool:
    """Return True when a step invokes another workflow.

    Args:
        step: Step configuration dictionary.

    Returns:
        True when the step's ``uses`` value is a workflow path.
    """
    if not isinstance(step, dict):
        return False
    return is_workflow_path(step.get("uses", ""))


def looks_like_workflow_file(uses: Any) -> bool:
    """Return True when a value names a YAML workflow file.

    Used to explain a missing ``./`` prefix instead of reporting the
    value as an unknown action provider.

    Args:
        uses: Value of a step's ``uses`` property.

    Returns:
        True when the value ends in ``.yml`` or ``.yaml``.
    """
    return _normalise_uses(uses).lower().endswith(WORKFLOW_SUFFIXES)


def has_workflow_suffix(target: Union[str, Path]) -> bool:
    """Return True when a target path names a YAML workflow file.

    Args:
        target: Path to check.

    Returns:
        True when the path ends in ``.yml`` or ``.yaml``.
    """
    return Path(str(target)).suffix.lower() in WORKFLOW_SUFFIXES


def workflow_frame(path: Union[str, Path]) -> WorkflowFrame:
    """Return the call-stack frame for a workflow file.

    Args:
        path: Path to a workflow file.

    Returns:
        Frame carrying the canonical path and its parent directory.
    """
    resolved = Path(path).resolve()
    return WorkflowFrame(path=resolved, source_dir=resolved.parent)


def root_frames(
    source_path: Optional[Union[str, Path]],
) -> Tuple[WorkflowFrame, ...]:
    """Return the initial call stack for a top-level workflow.

    Args:
        source_path: Path of the workflow being executed, if known.

    Returns:
        A single-frame stack, or an empty stack when the path is unknown.
    """
    if source_path is None:
        return ()
    return (workflow_frame(source_path),)


def call_base_dir(frames: Tuple[WorkflowFrame, ...]) -> Path:
    """Return the directory relative workflow calls resolve against.

    Args:
        frames: Current call stack.

    Returns:
        The calling workflow's directory, or the current directory when
        the stack is empty.
    """
    return frames[-1].source_dir if frames else Path.cwd()


def resolve_call_target(uses: str, frames: Tuple[WorkflowFrame, ...]) -> Path:
    """Resolve a workflow call target against the current call stack.

    Args:
        uses: Relative workflow path from a step's ``uses`` property.
        frames: Current call stack.

    Returns:
        Canonical absolute path of the called workflow.
    """
    relative = Path(_normalise_uses(uses))
    return (call_base_dir(frames) / relative).resolve()


def canonical_key(path: Path) -> str:
    """Return a comparison key for a workflow path.

    Args:
        path: Path to canonicalise.

    Returns:
        Case-normalised string suitable for equality checks.
    """
    return os.path.normcase(str(path))


def find_recursive_frame(
    target: Path, frames: Tuple[WorkflowFrame, ...]
) -> Optional[WorkflowFrame]:
    """Return the frame that already holds a target workflow.

    Args:
        target: Candidate called workflow.
        frames: Current call stack.

    Returns:
        The matching frame, or None when the call is not recursive.
    """
    key = canonical_key(target)
    for frame in frames:
        if canonical_key(frame.path) == key:
            return frame
    return None


def format_call_chain(frames: Tuple[WorkflowFrame, ...], target: Path) -> str:
    """Format the call chain leading to a recursive target.

    Args:
        frames: Current call stack.
        target: Workflow that would be called again.

    Returns:
        Chain such as ``a.yml -> b.yml -> a.yml``.
    """
    names = [frame.path.name for frame in frames]
    return " -> ".join([*names, target.name])
