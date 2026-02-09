"""
Action framework for CausalIQ workflow components.

This module provides the base classes and interfaces for implementing
reusable workflow actions that follow GitHub Actions patterns.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from causaliq_workflow.logger import WorkflowLogger
    from causaliq_workflow.registry import WorkflowContext


@dataclass
class ActionInput:
    """Define action input specification."""

    name: str
    description: str
    required: bool = False
    default: Any = None
    type_hint: str = "Any"


@dataclass
class ActionOutput:
    """Define action output specification."""

    name: str
    description: str
    value: Any


class CausalIQAction(ABC):
    """Base class for all workflow actions.

    Actions can capture execution metadata during run() which can be
    retrieved via get_action_metadata() after execution completes.
    This supports workflow caching and auditing use cases.

    Attributes:
        name: Action identifier for workflow 'uses' field.
        version: Action version string.
        description: Human-readable description.
        author: Action author/maintainer.
        inputs: Input parameter specifications.
        outputs: Output name to description mapping.
        _execution_metadata: Internal storage for execution metadata.
    """

    # Action metadata
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = "CausalIQ"

    # Input/output specifications
    inputs: Dict[str, ActionInput] = {}
    outputs: Dict[str, str] = {}  # name -> description mapping

    def __init__(self) -> None:
        """Initialise action with empty execution metadata."""
        self._execution_metadata: Dict[str, Any] = {}

    @abstractmethod
    def run(
        self,
        inputs: Dict[str, Any],
        mode: str = "dry-run",
        context: Optional["WorkflowContext"] = None,
        logger: Optional["WorkflowLogger"] = None,
    ) -> Dict[str, Any]:
        """Execute action with validated inputs, return outputs.

        Implementations should populate self._execution_metadata with
        relevant metadata during execution for later retrieval via
        get_action_metadata().

        Args:
            inputs: Dictionary of input values keyed by input name
            mode: Execution mode ('dry-run', 'run', 'compare')
            context: Workflow context for optimisation and intelligence
            logger: Optional logger for task execution reporting

        Returns:
            Dictionary of output values keyed by output name

        Raises:
            ActionExecutionError: If action execution fails
        """
        pass

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate input values against input specifications.

        Args:
            inputs: Dictionary of input values to validate

        Returns:
            True if all inputs are valid

        Raises:
            ActionValidationError: If validation fails
        """
        return True  # Default: accept all inputs

    def get_action_metadata(self) -> Dict[str, Any]:
        """Return metadata about the action execution.

        Called after run() completes to retrieve execution metadata
        for workflow caching and auditing purposes. Subclasses should
        populate self._execution_metadata during run() execution.

        The base implementation returns _execution_metadata with
        standard fields (action_name, action_version) added.

        Returns:
            Dictionary of metadata relevant to this action type.
            Always includes 'action_name' and 'action_version'.
        """
        base_metadata = {
            "action_name": self.name,
            "action_version": self.version,
        }
        return {**base_metadata, **self._execution_metadata}


class ActionExecutionError(Exception):
    """Raised when action execution fails."""

    pass


class ActionValidationError(Exception):
    """Raised when action input validation fails."""

    pass
