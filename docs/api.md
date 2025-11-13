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

## Workflow Execution Engine

### causaliq_pipeline.workflow

::: causaliq_pipeline.workflow.WorkflowExecutor
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: causaliq_pipeline.workflow.WorkflowExecutionError
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

::: causaliq_pipeline.schema.load_workflow_file
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

### Using WorkflowExecutor

```python
from causaliq_pipeline import WorkflowExecutor

# Create executor instance
executor = WorkflowExecutor()

# Parse and validate workflow
workflow = executor.parse_workflow("experiment.yml")
print(f"Workflow ID: {workflow['id']}")
print(f"Description: {workflow['description']}")

# Expand matrix variables
if "matrix" in workflow:
    jobs = executor.expand_matrix(workflow["matrix"])
    print(f"Generated {len(jobs)} jobs from matrix")
    
    # Each job contains the expanded matrix variables
    for i, job in enumerate(jobs):
        print(f"Job {i}: {job}")
        # Example: {'dataset': 'asia', 'algorithm': 'pc', 'alpha': 0.05}
```

### Flexible Path Configuration

```python
# Example workflow YAML showing flexible action parameters
workflow_yaml = """
id: "experiment-001"
description: "Flexible causal discovery experiment"
matrix:
  dataset: ["asia", "cancer"]
  algorithm: ["pc", "ges"]
  alpha: [0.01, 0.05]

steps:
  - name: "Structure Learning"
    uses: "dummy-structure-learner"
    with:
      dataset: "/experiments/data/{{dataset}}.csv"
      result: "/experiments/results/{{id}}/{{algorithm}}/graph_{{dataset}}_{{alpha}}.xml"
      alpha: "{{alpha}}"
      max_iter: 1000
"""

# Parse and expand
executor = WorkflowExecutor()
workflow = executor.parse_workflow_from_string(workflow_yaml)
jobs = executor.expand_matrix(workflow["matrix"])
# Creates 8 jobs (2×2×2) with customizable file paths
```

### Matrix Expansion Example

```python
from causaliq_pipeline import WorkflowExecutor

executor = WorkflowExecutor()

# Define matrix
matrix = {
    "algorithm": ["pc", "ges", "lingam"],
    "dataset": ["asia", "cancer"],
    "alpha": [0.01, 0.05]
}

# Expand into individual jobs
jobs = executor.expand_matrix(matrix)
# Results in 12 jobs (3 × 2 × 2 combinations)

for job in jobs:
    print(f"Algorithm: {job['algorithm']}, Dataset: {job['dataset']}, Alpha: {job['alpha']}")
```

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