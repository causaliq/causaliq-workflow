"""
Action framework for CausalIQ workflow components.

This module provides the base classes and interfaces for implementing
reusable workflow actions that follow GitHub Actions patterns.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict


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


class Action(ABC):
    """Base class for all workflow actions."""

    # Action metadata
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = "CausalIQ"

    # Input/output specifications
    inputs: Dict[str, ActionInput] = {}
    outputs: Dict[str, str] = {}  # name -> description mapping

    @abstractmethod
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action with validated inputs, return outputs.

        Args:
            inputs: Dictionary of input values keyed by input name

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


class ActionExecutionError(Exception):
    """Raised when action execution fails."""

    pass


class ActionValidationError(Exception):
    """Raised when action input validation fails."""

    pass
