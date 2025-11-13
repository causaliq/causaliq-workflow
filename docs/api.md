# API Reference

## Core Action Framework

### causaliq_pipeline.action

::: causaliq_pipeline.action.Action
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: causaliq_pipeline.action.ActionInput
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: causaliq_pipeline.action.ActionOutput
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: causaliq_pipeline.action.ActionExecutionError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: causaliq_pipeline.action.ActionValidationError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## Schema Validation

### causaliq_pipeline.schema

::: causaliq_pipeline.schema.WorkflowValidationError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: causaliq_pipeline.schema.load_schema
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: causaliq_pipeline.schema.validate_workflow
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## Built-in Actions

### causaliq_pipeline.actions

::: causaliq_pipeline.actions.DummyStructureLearnerAction
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## CLI Interface

### causaliq_pipeline.cli

::: causaliq_pipeline.cli
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

---

## Usage Examples

### Creating a Custom Action

```python
from causaliq_pipeline.action import Action, ActionInput, ActionExecutionError
from typing import Any, Dict

class MyStructureLearnerAction(Action):
    """Custom structure learning action."""
    
    name = "my-structure-learner"
    version = "1.0.0"
    description = "Custom causal structure learning implementation"
    author = "Your Name"
    
    inputs = {
        "data_path": ActionInput(
            name="data_path",
            description="Path to input CSV dataset",
            required=True,
            type_hint="str",
        ),
        "output_dir": ActionInput(
            name="output_dir",
            description="Directory for output files",
            required=True,
            type_hint="str",
        ),
        "alpha": ActionInput(
            name="alpha",
            description="Significance level for independence tests",
            required=False,
            default=0.05,
            type_hint="float",
        ),
    }
    
    outputs = {
        "graph_path": "Path to generated GraphML file",
        "node_count": "Number of nodes in the learned graph",
        "edge_count": "Number of edges in the learned graph",
    }
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the structure learning algorithm."""
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

### Validating Workflows

```python
from causaliq_pipeline.schema import validate_workflow, WorkflowValidationError

workflow_data = {
    "name": "My Experiment",
    "id": "experiment-001",
    "data_root": "/data",
    "output_root": "/results",
    "matrix": {
        "dataset": ["asia", "cancer"],
        "algorithm": ["pc", "ges"],
    },
    "steps": [
        {
            "name": "Structure Learning",
            "uses": "my-structure-learner",
            "with": {
                "alpha": 0.05,
            },
        }
    ],
}

try:
    result = validate_workflow(workflow_data)
    print("Workflow validation passed!")
except WorkflowValidationError as e:
    print(f"Validation failed: {e}")
    print(f"Schema path: {e.schema_path}")
```

### Loading Custom Schemas

```python
from causaliq_pipeline.schema import load_schema
from pathlib import Path

# Load custom schema
schema_path = Path("my-custom-schema.json")
schema = load_schema(schema_path)

# Use with validation
validate_workflow(workflow_data, schema)
```

## Development Guidelines

### Action Implementation Patterns

1. **Inherit from Action base class** - Provides standardized interface
2. **Define comprehensive inputs** - Use ActionInput for type safety
3. **Document outputs clearly** - Help users understand action results
4. **Handle errors gracefully** - Use ActionExecutionError and ActionValidationError
5. **Follow semantic versioning** - Enable workflow compatibility tracking
6. **Create GraphML output** - Use standardized format for causal graphs

### Testing Your Actions

```python
import pytest
from pathlib import Path
from causaliq_pipeline.action import ActionExecutionError

def test_my_action_success():
    """Test successful action execution."""
    action = MyStructureLearnerAction()
    inputs = {
        "data_path": "/path/to/test_data.csv",
        "output_dir": "/path/to/output",
        "alpha": 0.05,
    }
    
    result = action.run(inputs)
    
    assert "graph_path" in result
    assert "node_count" in result
    assert "edge_count" in result
    assert Path(result["graph_path"]).exists()

def test_my_action_missing_file():
    """Test action fails gracefully with missing input."""
    action = MyStructureLearnerAction()
    inputs = {
        "data_path": "/nonexistent/file.csv",
        "output_dir": "/path/to/output",
    }
    
    with pytest.raises(ActionExecutionError):
        action.run(inputs)
```