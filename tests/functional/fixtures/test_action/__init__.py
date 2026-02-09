"""
Test Action Package

Example of an external action package following the causaliq-workflow
convention. This demonstrates the production-ready pattern:

1. Export a class named 'CausalIQAction' that inherits from
   causaliq_workflow.action.CausalIQAction
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

from causaliq_workflow.action import (
    ActionExecutionError,
    ActionInput,
)
from causaliq_workflow.action import CausalIQAction as BaseAction

if TYPE_CHECKING:
    from causaliq_workflow.registry import WorkflowContext


class CausalIQAction(BaseAction):
    """Test action for demonstrating the causaliq-workflow plugin system.

    This action creates a simple test output file, demonstrating the standard
    Action interface that all external packages should implement.
    """

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
        inputs: Dict[str, Any],
        mode: str = "dry-run",
        context: Optional["WorkflowContext"] = None,
    ) -> Dict[str, Any]:
        """Execute test action.

        Args:
            inputs: Action input parameters
            mode: Execution mode ('dry-run', 'run', 'compare')
            context: Workflow execution context

        Returns:
            Dictionary containing output values

        Raises:
            ActionExecutionError: If execution fails
        """
        # Handle dry-run mode
        if mode == "dry-run":
            # Validate inputs without creating files
            required_keys = ["data_path", "output_dir"]
            for key in required_keys:
                if key not in inputs:
                    raise ActionExecutionError(
                        f"Missing required input: {key}"
                    )

            message = inputs.get("message", "Hello from test_action!")
            return {
                "output_file": f"{inputs['output_dir']}/test_output.txt",
                "message_count": len(message),
                "status": "dry-run-success",
            }

        try:
            data_path = Path(inputs["data_path"])
            output_dir = Path(inputs["output_dir"])
            message = inputs.get("message", "Hello from test_action!")

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

            return {
                "output_file": str(output_file),
                "message_count": len(message),
                "status": "success",
            }

        except Exception as e:
            raise ActionExecutionError(
                f"Test action execution failed: {e}"
            ) from e
