"""
causaliq-pipeline: Template package for CausalIQ repos
"""

# Import core functionality
from .workflow import WorkflowExecutionError, WorkflowExecutor

__version__ = "0.1.0"
__author__ = "CausalIQ"
__email__ = "info@causaliq.com"

# Package metadata
__title__ = "causaliq-pipeline"
__description__ = "Template package for CausalIQ repos"

__url__ = "https://github.com/causaliq/causaliq-pipeline"
__license__ = "MIT"

# Version tuple for programmatic access
VERSION = tuple(map(int, __version__.split(".")))

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "VERSION",
    "WorkflowExecutor",
    "WorkflowExecutionError",
]
