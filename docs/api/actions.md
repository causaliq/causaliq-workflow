# Action Framework

The action framework provides the foundational classes for building reusable
workflow components that follow GitHub Actions patterns.

causaliq-workflow uses the `CausalIQActionProvider` base class from causaliq-core
for all action implementations. This ensures consistency across the CausalIQ
ecosystem and provides standardised interfaces for action validation, execution,
and result handling.

## causaliq-core Integration

causaliq-workflow imports the following from causaliq-core:

- **CausalIQActionProvider** - Abstract base class for all workflow actions
- **ActionInput** - Type-safe input specification for action parameters
- **ActionResult** - Tuple type for action return values (status, metadata,
  objects)
- **ActionValidationError** - Exception for parameter validation failures
- **ActionExecutionError** - Exception for runtime execution failures

## Core Classes

### causaliq_core.CausalIQActionProvider

The base class for all action providers in the CausalIQ ecosystem.

::: causaliq_core.CausalIQActionProvider
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

### causaliq_core.ActionInput

::: causaliq_core.ActionInput
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## Exception Handling

### causaliq_core.ActionExecutionError

::: causaliq_core.ActionExecutionError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

### causaliq_core.ActionValidationError

::: causaliq_core.ActionValidationError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

---

## Quick Example

```python
from typing import Any, Dict, Optional, Set, TYPE_CHECKING

from causaliq_core import (
    ActionInput,
    ActionResult,
    ActionValidationError,
    CausalIQActionProvider,
)

if TYPE_CHECKING:
    from causaliq_workflow.registry import WorkflowContext
    from causaliq_workflow.logger import WorkflowLogger


class MyStructureLearnerAction(CausalIQActionProvider):
    """Custom structure learning action."""

    name = "my-structure-learner"
    version = "1.0.0"
    description = "Custom causal structure learning implementation"
    author = "CausalIQ"

    supported_actions: Set[str] = {"learn_structure", "evaluate_graph"}
    supported_types: Set[str] = set()

    inputs = {
        "action": ActionInput(
            name="action",
            description="Action to perform",
            required=True,
            type_hint="str",
        ),
        "data_path": ActionInput(
            name="data_path",
            description="Path to input data file",
            required=True,
            type_hint="str",
        ),
        "alpha": ActionInput(
            name="alpha",
            description="Significance level",
            required=False,
            default=0.05,
            type_hint="float",
        ),
    }

    outputs = {
        "graph_path": "Path to output GraphML file",
        "node_count": "Number of nodes in learned graph",
        "edge_count": "Number of edges in learned graph",
    }

    def run(
        self,
        action: str,
        parameters: Dict[str, Any],
        mode: str = "dry-run",
        context: Optional[Any] = None,
        logger: Optional[Any] = None,
    ) -> ActionResult:
        """Execute the structure learning algorithm.

        Args:
            action: Name of action to execute (e.g., "learn_structure")
            parameters: Action parameters (data_path, output_dir, etc.)
            mode: Execution mode ("dry-run", "run", "compare")
            context: Workflow context with matrix values and cache
            logger: Optional logger for progress reporting

        Returns:
            ActionResult tuple (status, metadata, objects)
        """
        if action not in self.supported_actions:
            raise ActionValidationError(f"Unknown action: {action}")

        # Dry-run mode: return metadata only
        if mode == "dry-run":
            return ("skipped", {"dry_run": True}, [])

        # Your implementation here
        metadata = {
            "graph_path": "/path/to/output.graphml",
            "node_count": 5,
            "edge_count": 8,
        }

        # Objects list contains graph data
        objects = [
            {
                "type": "graphml",
                "name": "graph",
                "content": "<graphml>...</graphml>",
            }
        ]

        return ("success", metadata, objects)
```

## Design Patterns

### Action Implementation Guidelines

1. **Inherit from CausalIQActionProvider** - The base class from causaliq-core
   provides the standardised interface
2. **Define comprehensive inputs** - Use ActionInput for type safety and
   documentation
3. **Document outputs clearly** - Help users understand action results
4. **Handle errors gracefully** - Use ActionValidationError for parameter issues
   and ActionExecutionError for runtime failures
5. **Follow semantic versioning** - Enable workflow compatibility tracking
6. **Return ActionResult tuples** - Status string, metadata dict, and objects
   list
7. **Support dry-run mode** - Return early with skipped status for validation

### Testing Your Actions

```python
import pytest

from causaliq_core import ActionValidationError


# Test successful action execution.
def test_my_action_success() -> None:
    action = MyStructureLearnerAction()
    parameters = {
        "data_path": "/path/to/test_data.csv",
        "alpha": 0.05,
    }

    status, metadata, objects = action.run(
        "learn_structure", parameters, mode="run"
    )

    assert status == "success"
    assert "node_count" in metadata
    assert "edge_count" in metadata


# Test action validation with invalid action name.
def test_my_action_invalid_action() -> None:
    action = MyStructureLearnerAction()
    parameters = {"data_path": "/path/to/data.csv"}

    with pytest.raises(ActionValidationError):
        action.run("invalid_action", parameters, mode="run")


# Test dry-run mode returns skipped status.
def test_my_action_dry_run() -> None:
    action = MyStructureLearnerAction()
    parameters = {"data_path": "/path/to/data.csv"}

    status, metadata, objects = action.run(
        "learn_structure", parameters, mode="dry-run"
    )

    assert status == "skipped"
    assert metadata.get("dry_run") is True
    assert objects == []
```

---

**[← Back to API Overview](overview.md)** | **[Next: Action Registry →](registry.md)**