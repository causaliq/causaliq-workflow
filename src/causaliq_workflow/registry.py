"""
Action registry for dynamic discovery and execution of workflow actions.

Provides centralized management of actions from external packages using
setuptools entry points for clean plugin architecture.
"""

import inspect
import logging
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from causaliq_workflow.action import Action, ActionExecutionError

logger = logging.getLogger(__name__)


@dataclass
class WorkflowContext:
    """Workflow context for action execution optimization.

    Provides minimal context needed for actions to optimize across workflows.
    Actions receive specific data through inputs; context provides
    meta-information.

    Attributes:
        mode: Execution mode ('dry-run', 'run', 'compare')
        matrix: Complete matrix definition for cross-job optimization
    """

    mode: str
    matrix: Dict[str, List[Any]]


class ActionRegistryError(Exception):
    """Raised when action registry operations fail.

    This exception is raised when:
    - Requested action is not found in the registry
    - Action discovery fails during module scanning
    - Action validation fails
    - Other registry-related errors occur
    """

    pass


class ActionRegistry:
    """Registry for discovering and executing workflow actions dynamically.

    Uses import-time introspection to automatically discover actions when
    packages are imported. No configuration needed - just import the package
    and use 'uses: package-name' in workflows.

    Convention: Action packages should export an Action subclass named
    'CausalIQAction' in their __init__.py file to avoid namespace collisions.

    Attributes:
        _instance: Singleton instance of the ActionRegistry
        _actions: Dictionary mapping action names to Action classes
        _discovery_errors: List of errors encountered during action discovery
    """

    _instance: Optional["ActionRegistry"] = None

    def __init__(self) -> None:
        """Initialize registry and discover available actions.

        Initializes:
            _actions: Dictionary mapping action names to Action classes
            _discovery_errors: List to collect any discovery errors
        """
        self._actions: Dict[str, Type[Action]] = {}
        self._discovery_errors: List[str] = []
        self._discover_actions()

    def _discover_actions(self) -> None:
        """Discover actions by scanning imported modules for Action classes."""
        logger.info("Discovering available actions from imported modules...")

        # Scan all imported modules for Action classes
        for module_name, module in sys.modules.items():
            if module is None:
                continue  # type: ignore[unreachable]

            # Skip built-ins and standard library
            if not hasattr(module, "__file__") or module.__file__ is None:
                continue

            if module_name.startswith("_"):
                continue

            if "." in module_name:
                root_module = module_name.split(".")[0]
                if root_module in sys.builtin_module_names:
                    continue

            self._scan_module_for_actions(module_name, module)

    def _scan_module_for_actions(self, module_name: str, module: Any) -> None:
        """Scan a specific module for Action classes."""
        try:
            # Look for a CausalIQAction class exported at module level
            if hasattr(module, "CausalIQAction"):
                action_class = getattr(module, "CausalIQAction")

                # Verify it's actually an Action subclass
                if (
                    inspect.isclass(action_class)
                    and issubclass(action_class, Action)
                    and action_class != Action
                ):

                    # Use the root package name as action name
                    action_name = module_name.split(".")[0]

                    if action_name not in self._actions:
                        self._actions[action_name] = action_class
                        logger.info(
                            f"Registered action: {action_name} -> "
                            f"{action_class.__name__}"
                        )

        except Exception as e:
            error_msg = f"Error scanning module {module_name}: {e}"
            self._discovery_errors.append(error_msg)
            logger.warning(error_msg)

    @classmethod
    def register_action(
        cls, package_name: str, action_class: Type[Action]
    ) -> None:
        """Register an action class from a package.

        This is called automatically when packages are imported that follow
        the convention of exporting a 'CausalIQAction' class.
        """
        # Get the global registry instance (singleton pattern)
        if ActionRegistry._instance is None:
            ActionRegistry._instance = ActionRegistry()

        ActionRegistry._instance._actions[package_name] = action_class
        logger.info(
            f"Registered action: {package_name} -> {action_class.__name__}"
        )

    def get_available_actions(self) -> Dict[str, Type[Action]]:
        """Get dictionary of available action names to classes.

        Returns:
            Dictionary mapping action names to Action classes

        """
        return self._actions.copy()

    def get_discovery_errors(self) -> List[str]:
        """Get list of errors encountered during action discovery.

        Returns:
            List of error messages from discovery process

        """
        return self._discovery_errors.copy()

    def has_action(self, name: str) -> bool:
        """Check if action is available.

        Args:
            name: Action name to check

        Returns:
            True if action is available

        """
        return name in self._actions

    def get_action_class(self, name: str) -> Type[Action]:
        """Get action class by name.

        Args:
            name: Action name

        Returns:
            Action class

        Raises:
            ActionRegistryError: If action not found

        """
        if name not in self._actions:
            available = list(self._actions.keys())
            raise ActionRegistryError(
                f"Action '{name}' not found. Available actions: {available}"
            )

        return self._actions[name]

    def execute_action(
        self,
        name: str,
        inputs: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """Execute action with inputs and workflow context.

        Args:
            name: Action name
            inputs: Action input parameters
            context: Complete workflow context

        Returns:
            Action outputs dictionary

        Raises:
            ActionRegistryError: If action not found or execution fails

        """
        try:
            action_class = self.get_action_class(name)
            action = action_class()

            logger.info(f"Executing action '{name}' in mode '{context.mode}'")

            # Execute action with mode and context
            return action.run(inputs, mode=context.mode, context=context)

        except Exception as e:
            raise ActionExecutionError(
                f"Action '{name}' execution failed: {e}"
            ) from e

    def validate_workflow_actions(self, workflow: Dict[str, Any]) -> List[str]:
        """Validate all actions in workflow exist and can run.

        Args:
            workflow: Parsed workflow dictionary

        Returns:
            List of validation errors (empty if valid)

        """
        errors = []

        # Extract all action names from workflow steps
        for step in workflow.get("steps", []):
            if "uses" in step:
                action_name = step["uses"]
                if not self.has_action(action_name):
                    available = list(self._actions.keys())
                    errors.append(
                        f"Step '{step.get('name', 'unnamed')}' uses "
                        f"unknown action '{action_name}'. Available: "
                        f"{available}"
                    )

        # Include discovery errors
        errors.extend(self._discovery_errors)

        return errors

    def list_actions_by_package(self) -> Dict[str, List[str]]:
        """Group actions by source package for documentation.

        Returns:
            Dictionary mapping package names to action lists

        """
        packages: Dict[str, List[str]] = {}

        for action_name, action_class in self._actions.items():
            # Extract package name from module
            module_parts = action_class.__module__.split(".")
            if len(module_parts) > 0:
                package_name = module_parts[0]
            else:
                package_name = "unknown"

            if package_name not in packages:
                packages[package_name] = []

            packages[package_name].append(action_name)

        return packages
