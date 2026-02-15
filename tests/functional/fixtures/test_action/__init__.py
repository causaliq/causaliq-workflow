"""
Test Action Package

Example of an external action provider package following the causaliq-workflow
convention. This demonstrates the production-ready pattern:

1. Export a class named 'ActionProvider' that inherits from
   causaliq_core.CausalIQActionProvider
2. Import this package and it becomes available as 'uses: test_action'
3. Zero configuration required - clean namespace with no conflicts

Usage in workflow:
```yaml
steps:
  - name: "Test Step"
    uses: "test_action"
    with:
      data_path: "/data/example.csv"
      output_dir: "/results"
```
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from causaliq_core import (
    ActionExecutionError,
    ActionInput,
    ActionResult,
    CausalIQActionProvider,
)

if TYPE_CHECKING:
    from causaliq_workflow.registry import WorkflowContext


class ActionProvider(CausalIQActionProvider):
    """Test action provider for demonstrating the causaliq-workflow plugin.

    This provider creates a simple test output file, demonstrating the
    standard ActionProvider interface that all external packages should
    implement.
    """

    # Prevent pytest from trying to collect this as a test class
    __test__ = False

    name = "test-action"
    version = "1.0.0"
    description = "Test action that creates a simple output file"
    author = "CausalIQ"

    inputs = {
        "data_path": ActionInput(
            name="data_path",
            description="Path to input data file",
            required=True,
            type_hint="str",
        ),
        "output_dir": ActionInput(
            name="output_dir",
            description="Directory for output files",
            required=True,
            type_hint="str",
        ),
        "message": ActionInput(
            name="message",
            description="Custom message to include in output",
            required=False,
            type_hint="str",
        ),
    }

    outputs = {
        "output_file": "Path to generated output file",
        "message_count": "Number of characters in the message",
        "status": "Action execution status",
    }

    def __init__(self) -> None:
        """Initialise test action."""
        super().__init__()

    def run(
        self,
        action: str,
        parameters: Dict[str, Any],
        mode: str = "dry-run",
        context: Optional["WorkflowContext"] = None,
        logger: Optional[Any] = None,
    ) -> ActionResult:
        """Execute test action.

        Args:
            action: Name of the action to execute
            parameters: Action parameters
            mode: Execution mode ('dry-run', 'run', 'compare')
            context: Workflow execution context
            logger: Optional workflow logger

        Returns:
            Tuple of (status, metadata, objects)

        Raises:
            ActionExecutionError: If execution fails
        """
        # Handle dry-run mode
        if mode == "dry-run":
            # Validate parameters without creating files
            required_keys = ["data_path", "output_dir"]
            for key in required_keys:
                if key not in parameters:
                    raise ActionExecutionError(
                        f"Missing required parameter: {key}"
                    )

            message = parameters.get("message", "Hello from test_action!")
            metadata = {
                "output_file": f"{parameters['output_dir']}/test_output.txt",
                "message_count": len(message),
            }
            return ("skipped", metadata, [])

        try:
            data_path = Path(parameters["data_path"])
            output_dir = Path(parameters["output_dir"])
            message = parameters.get("message", "Hello from test_action!")

            # Validate input file exists (only in run mode)
            if not data_path.exists():
                raise ActionExecutionError(
                    f"Input data file not found: {data_path}"
                )

            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create output file
            output_file = output_dir / "test_output.txt"

            # Create test content
            content = f"""Test Action Output
==================

Input file: {data_path}
Output directory: {output_dir}
Custom message: {message}
Execution mode: {mode}
Message length: {len(message)} characters

This demonstrates a working causaliq-workflow action package!
"""

            output_file.write_text(content, encoding="utf-8")

            metadata = {
                "output_file": str(output_file),
                "message_count": len(message),
            }
            return ("success", metadata, [])

        except Exception as e:
            raise ActionExecutionError(
                f"Test action execution failed: {e}"
            ) from e
