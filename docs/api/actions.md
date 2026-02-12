# Action Framework

The action framework provides the foundational classes for building reusable workflow components that follow GitHub Actions patterns.

## Core Classes

### causaliq_workflow.action

::: causaliq_workflow.action.BaseActionProvider
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: causaliq_workflow.action.ActionInput
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: causaliq_workflow.action.ActionOutput
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Exception Handling

::: causaliq_workflow.action.ActionExecutionError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: causaliq_workflow.action.ActionValidationError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Quick Example

```python
from causaliq_workflow.action import BaseActionProvider, ActionExecutionError
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from causaliq_workflow.registry import WorkflowContext
    from causaliq_workflow.logger import WorkflowLogger

class MyStructureLearnerAction(BaseActionProvider):
    """Custom structure learning action."""
    
    name = "my-structure-learner"
    version = "1.0.0"
    description = "Custom causal structure learning implementation"
    supported_actions = {"learn_structure", "evaluate_graph"}
    
    def run(
        self,
        action: str,
        parameters: Dict[str, Any],
        mode: str = "dry-run",
        context: Optional["WorkflowContext"] = None,
        logger: Optional["WorkflowLogger"] = None,
    ) -> Dict[str, Any]:
        """Execute the structure learning algorithm.
        
        Args:
            action: Name of action to execute (e.g., "learn_structure")
            parameters: Action parameters (data_path, output_dir, etc.)
            mode: Execution mode ("dry-run", "run", "compare")
            context: Workflow context with matrix values and cache
            logger: Optional logger for progress reporting
        
        Returns:
            Dictionary with action outputs
        """
        try:
            # Your implementation here
            return {
                "graph_path": "/path/to/output.graphml",
                "node_count": 5,
                "edge_count": 8,
            }
        except Exception as e:
            raise ActionExecutionError(f"Structure learning failed: {e}") from e
```

## Design Patterns

### Action Implementation Guidelines

1. **Inherit from BaseActionProvider base class** - Provides standardized interface
2. **Define comprehensive inputs** - Use ActionInput for type safety
3. **Document outputs clearly** - Help users understand action results
4. **Handle errors gracefully** - Use ActionExecutionError and ActionValidationError
5. **Follow semantic versioning** - Enable workflow compatibility tracking
6. **Create GraphML output** - Use standardized format for causal graphs

### Testing Your Actions

```python
import pytest
from pathlib import Path
from causaliq_workflow.action import ActionExecutionError

def test_my_action_success():
    """Test successful action execution."""
    action = MyStructureLearnerAction()
    parameters = {
        "data_path": "/path/to/test_data.csv",
        "output_dir": "/path/to/output",
        "alpha": 0.05,
    }
    
    result = action.run("learn_structure", parameters, mode="run")
    
    assert "graph_path" in result
    assert "node_count" in result
    assert "edge_count" in result
    assert Path(result["graph_path"]).exists()

def test_my_action_missing_file():
    """Test action fails gracefully with missing input."""
    action = MyStructureLearnerAction()
    parameters = {
        "data_path": "/nonexistent/file.csv",
        "output_dir": "/path/to/output",
    }
    
    with pytest.raises(ActionExecutionError):
        action.run("learn_structure", parameters, mode="run")
```

---

**[← Back to API Overview](overview.md)** | **[Next: Action Registry →](registry.md)**