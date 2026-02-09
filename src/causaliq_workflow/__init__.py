"""
causaliq-workflow: Template package for CausalIQ repos
"""

# Import core functionality
from .action import ActionExecutionError, ActionValidationError, CausalIQAction
from .cache import WorkflowCache
from .logger import LogLevel, WorkflowLogger  # noqa: F401
from .registry import ActionRegistry, ActionRegistryError, WorkflowContext
from .status import TaskStatus  # noqa: F401
from .workflow import WorkflowExecutionError, WorkflowExecutor

__version__ = "0.1.1.dev4"
__author__ = "CausalIQ"
__email__ = "info@causaliq.com"

# Package metadata
__title__ = "causaliq-workflow"
__description__ = "Template package for CausalIQ repos"

__url__ = "https://github.com/causaliq/causaliq-workflow"
__license__ = "MIT"

# Version tuple for programmatic access (only numeric parts)
VERSION = tuple(int(part) for part in __version__.split(".") if part.isdigit())

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "VERSION",
    "CausalIQAction",
    "ActionExecutionError",
    "ActionValidationError",
    "ActionRegistry",
    "ActionRegistryError",
    "WorkflowCache",
    "WorkflowContext",
    "WorkflowExecutor",
    "WorkflowExecutionError",
]
