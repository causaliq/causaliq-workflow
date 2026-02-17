"""Built-in action provider for causaliq-workflow.

Provides an 'echo' action for testing workflow execution, cache storage,
and export/import functionality without external dependencies.
"""

from typing import Any, Dict, List, Optional, Set

from causaliq_core import (
    ActionInput,
    ActionResult,
    ActionValidationError,
    CausalIQActionProvider,
)

# Supported actions
SUPPORTED_ACTIONS = {"echo"}


class WorkflowActionProvider(CausalIQActionProvider):
    """Built-in action provider for workflow testing.

    Provides an 'echo' action that creates a simple entry with metadata
    and two objects (JSON and GraphML) for testing the full workflow
    pipeline including cache storage and export.

    Example workflow:
        steps:
          - name: "Test Echo"
            uses: "causaliq-workflow"
            with:
              action: "echo"
              message: "Hello World"
              nodes: 3
    """

    name = "causaliq-workflow"
    version = "1.0.0"
    description = "Built-in workflow testing action"
    author = "CausalIQ"

    supported_actions: Set[str] = SUPPORTED_ACTIONS
    supported_types: Set[str] = set()

    inputs = {
        "action": ActionInput(
            name="action",
            description="Action to perform ('echo')",
            required=True,
            type_hint="str",
        ),
        "message": ActionInput(
            name="message",
            description="Message to echo in output",
            required=False,
            default="Hello from causaliq-workflow!",
            type_hint="str",
        ),
        "nodes": ActionInput(
            name="nodes",
            description="Number of nodes in test graph (2-10)",
            required=False,
            default=3,
            type_hint="int",
        ),
    }

    outputs = {
        "message": "The echoed message",
        "node_count": "Number of nodes in generated graph",
        "edge_count": "Number of edges in generated graph",
    }

    def _validate_parameters(
        self, action: str, parameters: Dict[str, Any]
    ) -> None:
        """Validate action and parameters.

        Args:
            action: Action to perform.
            parameters: Parameter dictionary.

        Raises:
            ActionValidationError: If validation fails.
        """
        if action not in SUPPORTED_ACTIONS:
            raise ActionValidationError(
                f"Unknown action: '{action}'. "
                f"Supported actions: {SUPPORTED_ACTIONS}"
            )

        # Validate and coerce nodes parameter (may be string from template)
        nodes = parameters.get("nodes", 3)
        try:
            nodes = int(nodes)
        except (ValueError, TypeError):
            raise ActionValidationError(
                f"'nodes' must be an integer between 2 and 10, got: {nodes}"
            )
        if nodes < 2 or nodes > 10:
            raise ActionValidationError(
                f"'nodes' must be an integer between 2 and 10, got: {nodes}"
            )

    def run(
        self,
        action: str,
        parameters: Dict[str, Any],
        mode: str = "dry-run",
        context: Optional[Any] = None,
        logger: Optional[Any] = None,
    ) -> ActionResult:
        """Execute the specified action.

        Args:
            action: Action to perform ('echo').
            parameters: Action parameters.
            mode: Execution mode ('dry-run' or 'run').
            context: Workflow context.
            logger: Optional workflow logger.

        Returns:
            ActionResult tuple (status, metadata, objects).

        Raises:
            ActionValidationError: If validation fails.
        """
        self._validate_parameters(action, parameters)

        if action == "echo":
            return self._run_echo(parameters, mode)

        # Should not reach here after validation
        raise ActionValidationError(f"Unknown action: {action}")

    def _run_echo(
        self,
        parameters: Dict[str, Any],
        mode: str,
    ) -> ActionResult:
        """Execute the echo action.

        Args:
            parameters: Action parameters.
            mode: Execution mode.

        Returns:
            ActionResult with JSON and GraphML objects.
        """
        message = parameters.get("message", "Hello from causaliq-workflow!")
        nodes = int(parameters.get("nodes", 3))

        # Build simple chain graph: A -> B -> C -> ...
        node_names = [chr(ord("A") + i) for i in range(nodes)]
        edges = [(node_names[i], node_names[i + 1]) for i in range(nodes - 1)]

        # Build metadata
        metadata: Dict[str, Any] = {
            "message": message,
            "node_count": nodes,
            "edge_count": len(edges),
            "mode": mode,
        }

        # Dry-run: return metadata only, no objects
        if mode == "dry-run":
            metadata["dry_run"] = True
            return ("skipped", metadata, [])

        # Build JSON content
        json_content = self._build_json_content(message, node_names, edges)

        # Build GraphML content
        graphml_content = self._build_graphml_content(node_names, edges)

        # Build objects list
        objects: List[Dict[str, Any]] = [
            {
                "type": "json",
                "name": "echo_data",
                "content": json_content,
            },
            {
                "type": "graphml",
                "name": "graph",
                "content": graphml_content,
            },
        ]

        return ("success", metadata, objects)

    def _build_json_content(
        self,
        message: str,
        nodes: List[str],
        edges: List[tuple],
    ) -> str:
        """Build JSON content for echo action.

        Args:
            message: Echo message.
            nodes: List of node names.
            edges: List of (source, target) tuples.

        Returns:
            JSON string.
        """
        import json

        data = {
            "message": message,
            "nodes": nodes,
            "edges": [{"source": s, "target": t} for s, t in edges],
        }
        return json.dumps(data, indent=2)

    def _build_graphml_content(
        self,
        nodes: List[str],
        edges: List[tuple],
    ) -> str:
        """Build GraphML content for echo action.

        Args:
            nodes: List of node names.
            edges: List of (source, target) tuples.

        Returns:
            GraphML XML string.
        """
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
            '  <graph id="G" edgedefault="directed">',
        ]

        # Add nodes
        for node in nodes:
            lines.append(f'    <node id="{node}"/>')

        # Add edges
        for i, (source, target) in enumerate(edges):
            lines.append(
                f'    <edge id="e{i}" source="{source}" target="{target}"/>'
            )

        lines.append("  </graph>")
        lines.append("</graphml>")

        return "\n".join(lines)


# Export as ActionProvider for auto-discovery
ActionProvider = WorkflowActionProvider
