"""
Action provider framework for CausalIQ workflow components.

This module provides the base classes and interfaces for implementing
action providers that expose multiple workflow actions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional, Set

if TYPE_CHECKING:
    from causaliq_workflow.logger import WorkflowLogger
    from causaliq_workflow.registry import WorkflowContext


@dataclass
class ActionInput:
    """Define action input specification.

    Note: This class defines parameter specifications for actions.
    The name 'ActionInput' is retained for backward compatibility.
    """

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


class BaseActionProvider(ABC):
    """Base class for action providers that expose multiple workflow actions.

    Action providers group related actions together. Each provider must
    declare which actions it supports via the supported_actions attribute.
    The 'action' input parameter selects which action to execute.

    Providers can capture execution metadata during run() which can be
    retrieved via get_action_metadata() after execution completes.
    This supports workflow caching and auditing use cases.

    Attributes:
        name: Provider identifier for workflow 'uses' field.
        version: Provider version string.
        description: Human-readable description.
        author: Provider author/maintainer.
        supported_actions: Set of action names this provider supports.
        inputs: Input parameter specifications.
        outputs: Output name to description mapping.
        _execution_metadata: Internal storage for execution metadata.
    """

    # Provider metadata
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = "CausalIQ"

    # Actions supported by this provider
    supported_actions: Set[str] = set()

    # Input/output specifications
    inputs: Dict[str, ActionInput] = {}
    outputs: Dict[str, str] = {}  # name -> description mapping

    def __init__(self) -> None:
        """Initialise provider with empty execution metadata."""
        self._execution_metadata: Dict[str, Any] = {}

    @abstractmethod
    def run(
        self,
        action: str,
        parameters: Dict[str, Any],
        mode: str = "dry-run",
        context: Optional["WorkflowContext"] = None,
        logger: Optional["WorkflowLogger"] = None,
    ) -> Dict[str, Any]:
        """Execute the specified action with validated parameters.

        The action parameter specifies which action to execute.
        Implementations should validate that action is in supported_actions.

        Implementations should populate self._execution_metadata with
        relevant metadata during execution for later retrieval via
        get_action_metadata().

        Args:
            action: Name of the action to execute (must be in
                supported_actions)
            parameters: Dictionary of parameter values for the action
            mode: Execution mode ('dry-run', 'run', 'compare')
            context: Workflow context for optimisation and intelligence
            logger: Optional logger for task execution reporting

        Returns:
            Dictionary of output values keyed by output name

        Raises:
            ActionExecutionError: If action execution fails
            ActionValidationError: If action is not supported
        """
        pass

    def validate_parameters(
        self, action: str, parameters: Dict[str, Any]
    ) -> bool:
        """Validate action and parameters against specifications.

        Validates that:
        1. The action is in supported_actions (if specified)
        2. All required parameters are provided

        Args:
            action: Name of the action to validate
            parameters: Dictionary of parameter values to validate

        Returns:
            True if action and parameters are valid

        Raises:
            ActionValidationError: If validation fails
        """
        # Validate action is supported if supported_actions is defined
        if self.supported_actions:
            if action not in self.supported_actions:
                raise ActionValidationError(
                    f"Unsupported action '{action}'. "
                    f"Supported: {self.supported_actions}"
                )
        return True  # Default: accept all parameters

    def get_action_metadata(self) -> Dict[str, Any]:
        """Return metadata about the provider execution.

        Called after run() completes to retrieve execution metadata
        for workflow caching and auditing purposes. Subclasses should
        populate self._execution_metadata during run() execution.

        The base implementation returns _execution_metadata with
        standard fields (action_name, action_version) added.

        Returns:
            Dictionary of metadata relevant to this provider.
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
