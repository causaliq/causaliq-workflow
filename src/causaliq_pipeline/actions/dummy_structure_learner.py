"""
Dummy structure learning action for testing workflow execution.

This action provides a simple placeholder that validates the action framework
without requiring real causal discovery algorithms or graph representations.
"""

from pathlib import Path
from typing import Any, Dict

from causaliq_pipeline.action import Action, ActionExecutionError, ActionInput


class DummyStructureLearnerAction(Action):
    """Dummy structure learning action that creates an empty graph file."""

    name = "dummy-structure-learner"
    version = "1.0.0"
    description = "Dummy action that creates an empty graph file for testing"
    author = "CausalIQ"

    inputs = {
        "data_path": ActionInput(
            name="data_path",
            description="Path to input CSV dataset (auto-constructed)",
            required=True,
            type_hint="str",
        ),
        "output_dir": ActionInput(
            name="output_dir",
            description="Directory for output files (auto-constructed)",
            required=True,
            type_hint="str",
        ),
        "dataset": ActionInput(
            name="dataset",
            description="Dataset name from matrix",
            required=True,
            type_hint="str",
        ),
        "algorithm": ActionInput(
            name="algorithm",
            description="Algorithm name from matrix",
            required=True,
            type_hint="str",
        ),
    }

    outputs = {
        "graph_path": "Path to generated GraphML file",
        "node_count": "Number of nodes in the graph",
        "edge_count": "Number of edges in the graph",
    }

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Create a dummy empty GraphML file.

        Args:
            inputs: Dictionary containing data_path, output_dir, and matrix
                vars

        Returns:
            Dictionary with graph_path, node_count, and edge_count

        Raises:
            ActionExecutionError: If file operations fail
        """
        try:
            data_path = Path(inputs["data_path"])
            output_dir = Path(inputs["output_dir"])

            # Validate input file exists
            if not data_path.exists():
                raise ActionExecutionError(
                    f"Input data file not found: {data_path}"
                )

            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create output GraphML file path
            graph_path = output_dir / "learned_graph.graphml"

            # Create dummy GraphML content
            dummy_content = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="dummy_graph" edgedefault="directed">
    <!-- Empty graph - no nodes or edges -->
  </graph>
</graphml>"""

            graph_path.write_text(dummy_content, encoding="utf-8")

            return {
                "graph_path": str(graph_path),
                "node_count": 0,
                "edge_count": 0,
            }

        except Exception as e:
            raise ActionExecutionError(
                f"Dummy structure learning failed: {e}"
            ) from e
