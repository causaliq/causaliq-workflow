"""
Action registry for dynamic discovery and execution of workflow actions.

Provides centralised management of action providers from external packages
using setuptools entry points for clean plugin architecture.
"""

import hashlib
import inspect
import json
import logging
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from causaliq_workflow.action import (
    ActionExecutionError,
    BaseActionProvider,
)

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.cache import WorkflowCache

logger = logging.getLogger(__name__)

# Length of truncated SHA-256 hash (16 hex chars = 64 bits)
HASH_LENGTH = 16


@dataclass
class WorkflowContext:
    """Workflow context for action execution optimisation.

    Provides minimal context needed for actions to optimise across workflows.
    Actions receive specific data through inputs; context provides
    meta-information.

    Attributes:
        mode: Execution mode ('dry-run', 'run', 'compare')
        matrix: Complete matrix definition for cross-job optimisation
        matrix_values: Current job's specific matrix variable values
        cache: Optional WorkflowCache for storing step results
    """

    mode: str
    matrix: Dict[str, List[Any]]
    matrix_values: Dict[str, Any] = field(default_factory=dict)
    cache: Optional["WorkflowCache"] = None

    @property
    def matrix_key(self) -> str:
        """Compute cache key from matrix values.

        Returns a truncated SHA-256 hash (16 hex characters) of the
        matrix variable values, suitable for use as a cache key.

        The hash is computed from JSON-serialised matrix_values with
        sorted keys for deterministic ordering.

        Returns:
            Truncated hex hash string (16 characters), or empty string
            if matrix_values is empty.

        Example:
            >>> context = WorkflowContext(
            ...     mode="run",
            ...     matrix={"algorithm": ["pc", "ges"]},
            ...     matrix_values={"algorithm": "pc"}
            ... )
            >>> len(context.matrix_key)
            16
        """
        if not self.matrix_values:
            return ""
        key_json = json.dumps(
            self.matrix_values, sort_keys=True, separators=(",", ":")
        )
        full_hash = hashlib.sha256(key_json.encode("utf-8")).hexdigest()
        return full_hash[:HASH_LENGTH]


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

    Convention: Action packages should export a BaseActionProvider subclass
    named 'ActionProvider' in their __init__.py file to avoid namespace
    collisions.

    Attributes:
        _instance: Singleton instance of the ActionRegistry
        _actions: Dictionary mapping action names to BaseActionProvider classes
        _entry_points: Dictionary of lazy-loadable entry points
        _discovery_errors: List of errors encountered during action discovery
    """

    _instance: Optional["ActionRegistry"] = None

    def __init__(self) -> None:
        """Initialise registry and discover available action providers.

        Initialises:
            _actions: Dictionary mapping action names to BaseActionProvider
            _entry_points: Dictionary of entry points for lazy loading
            _discovery_errors: List to collect any discovery errors
        """
        self._actions: Dict[str, Type[BaseActionProvider]] = {}
        self._entry_points: Dict[str, Any] = {}  # Lazy-loaded entry points
        self._discovery_errors: List[str] = []
        self._discover_actions()

    def _discover_actions(self) -> None:
        """Discover actions via entry points and imported modules."""
        logger.info("Discovering available actions...")

        # First, discover entry points (lazy - just record names, don't import)
        self._discover_entry_points()

        # Then scan imported modules as fallback
        self._discover_via_modules()

    def _discover_entry_points(self) -> None:
        """Discover entry points without importing them (lazy loading).

        Entry points are recorded but not loaded until actually needed.
        This avoids circular import issues since we don't import the
        action packages until execution time.
        """
        try:
            if sys.version_info >= (3, 10):
                from importlib.metadata import entry_points

                eps = entry_points(group="causaliq.actions")
            else:
                from importlib.metadata import entry_points

                all_eps = entry_points()
                eps = all_eps.get("causaliq.actions", [])

            for ep in eps:
                # Just record the entry point, don't load it yet
                self._entry_points[ep.name] = ep
                logger.info(
                    f"Discovered action entry point: {ep.name} "
                    f"(will load on first use)"
                )

        except Exception as e:
            logger.debug(f"Entry point discovery not available: {e}")

    def _load_entry_point(
        self, name: str
    ) -> Optional[Type[BaseActionProvider]]:
        """Load an entry point on demand.

        Args:
            name: Entry point name to load

        Returns:
            Loaded action class or None if loading fails
        """
        if name not in self._entry_points:
            return None

        ep = self._entry_points[name]
        try:
            action_class = ep.load()
            if (
                inspect.isclass(action_class)
                and issubclass(action_class, BaseActionProvider)
                and action_class is not BaseActionProvider
            ):
                # Cache the loaded class
                self._actions[name] = action_class
                logger.info(
                    f"Loaded action from entry point: "
                    f"{name} -> {action_class.__name__}"
                )
                return action_class
            else:
                error_msg = (
                    f"Entry point {name} does not export ActionProvider"
                )
                self._discovery_errors.append(error_msg)
                logger.warning(error_msg)
                return None
        except Exception as e:
            error_msg = f"Error loading entry point {name}: {e}"
            self._discovery_errors.append(error_msg)
            logger.warning(error_msg)
            return None

    def _discover_via_modules(self) -> None:
        """Discover actions by scanning imported modules for ActionProvider."""
        logger.info("Scanning imported modules for action providers...")

        # Scan all imported modules for ActionProvider classes
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
        """Scan a specific module for ActionProvider classes."""
        try:
            # Look for ActionProvider class exported at module level
            provider_class = None
            if hasattr(module, "ActionProvider"):
                provider_class = getattr(module, "ActionProvider")

            if provider_class is not None:
                action_class = provider_class

                # Verify it's actually a BaseActionProvider subclass
                if (
                    inspect.isclass(action_class)
                    and issubclass(action_class, BaseActionProvider)
                    and action_class is not BaseActionProvider
                ):

                    # Use the root package name as action name
                    action_name = module_name.split(".")[0]

                    if action_name not in self._actions:
                        self._actions[action_name] = action_class
                        logger.info(
                            f"Registered action: {action_name} -> "
                            f"{action_class.__name__}"
                        )

                        # Also register by action hyphenated name if different
                        if (
                            hasattr(action_class, "name")
                            and action_class.name != action_name
                        ):
                            hyphenated_name = action_class.name
                            if hyphenated_name not in self._actions:
                                self._actions[hyphenated_name] = action_class
                                logger.info(
                                    f"Registered action: {hyphenated_name} -> "
                                    f"{action_class.__name__} (alias)"
                                )

        except Exception as e:
            error_msg = f"Error scanning module {module_name}: {e}"
            self._discovery_errors.append(error_msg)
            logger.warning(error_msg)

    @classmethod
    def register_action(
        cls, package_name: str, action_class: Type[BaseActionProvider]
    ) -> None:
        """Register an action provider class from a package.

        This is called automatically when packages are imported that follow
        the convention of exporting an 'ActionProvider' class.
        """
        # Get the global registry instance (singleton pattern)
        if ActionRegistry._instance is None:
            ActionRegistry._instance = ActionRegistry()

        ActionRegistry._instance._actions[package_name] = action_class
        logger.info(
            f"Registered action: {package_name} -> {action_class.__name__}"
        )

    def get_available_actions(self) -> Dict[str, Type[BaseActionProvider]]:
        """Get dictionary of available action names to classes.

        Note: Entry points that haven't been loaded yet will not appear
        in the returned dictionary. Use get_available_action_names() to
        get all available action names including lazy-loadable ones.

        Returns:
            Dictionary mapping action names to BaseActionProvider classes

        """
        return self._actions.copy()

    def get_available_action_names(self) -> List[str]:
        """Get list of all available action names.

        Includes both loaded actions and lazy-loadable entry points.

        Returns:
            List of available action names
        """
        names = set(self._actions.keys())
        names.update(self._entry_points.keys())
        return sorted(names)

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
            True if action is available (loaded or lazy-loadable)

        """
        return name in self._actions or name in self._entry_points

    def get_action_class(self, name: str) -> Type[BaseActionProvider]:
        """Get action class by name, loading from entry point if needed.

        Args:
            name: Action name

        Returns:
            BaseActionProvider class

        Raises:
            ActionRegistryError: If action not found or fails to load

        """
        # Return cached action if available
        if name in self._actions:
            return self._actions[name]

        # Try to load from entry point
        if name in self._entry_points:
            action_class = self._load_entry_point(name)
            if action_class is not None:
                return action_class
            raise ActionRegistryError(
                f"Action '{name}' entry point failed to load"
            )

        # Action not found
        available = list(self._actions.keys()) + list(
            self._entry_points.keys()
        )
        raise ActionRegistryError(
            f"Action '{name}' not found. Available actions: {available}"
        )

    def execute_action(
        self,
        name: str,
        inputs: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """Execute action with inputs and workflow context.

        Extracts the 'action' key from inputs and passes it separately
        to the provider's run() method along with the remaining parameters.

        After execution, automatically calls get_action_metadata() and
        includes the metadata in the result under 'action_metadata' key.

        Args:
            name: Provider name (e.g., 'causaliq/knowledge')
            inputs: Action parameters including 'action' key
            context: Complete workflow context

        Returns:
            Action outputs dictionary with 'action_metadata' key added

        Raises:
            ActionRegistryError: If action not found or execution fails

        """
        try:
            action_class = self.get_action_class(name)
            action_instance = action_class()

            # Extract action name from inputs, remaining are parameters
            action_name = inputs.get("action", "")
            parameters = {k: v for k, v in inputs.items() if k != "action"}

            logger.info(
                f"Executing action '{action_name}' from provider '{name}' "
                f"in mode '{context.mode}'"
            )

            # Execute action with separated action and parameters
            result = action_instance.run(
                action_name, parameters, mode=context.mode, context=context
            )

            # Automatically capture action metadata after execution
            result["action_metadata"] = action_instance.get_action_metadata()

            return result

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
                    available = self.get_available_action_names()
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
