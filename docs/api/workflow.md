# Workflow Engine

The workflow execution engine provides powerful workflow parsing, validation, and execution with matrix expansion and template variable support.

## Core Classes

### causaliq_workflow.workflow

::: causaliq_workflow.workflow.WorkflowExecutor
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
      members:
        - parse_workflow
        - expand_matrix
        - execute_workflow

## Exception Handling

::: causaliq_workflow.workflow.WorkflowExecutionError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Usage Examples

### Basic Workflow Execution

```python
from causaliq_workflow import WorkflowExecutor, WorkflowExecutionError
from causaliq_workflow.registry import ActionRegistry

# Create executor instance
executor = WorkflowExecutor()

try:
    # Parse and validate workflow (includes template variable validation)
    workflow = executor.parse_workflow("experiment.yml")
    print(f"Workflow ID: {workflow['id']}")
    print(f"Description: {workflow['description']}")
    
    # Execute the complete workflow
    results = executor.execute_workflow(workflow, mode="run")
    print(f"Workflow completed successfully")
    
except WorkflowExecutionError as e:
    print(f"Workflow execution failed: {e}")
```

### Matrix Expansion

```python
from causaliq_workflow import WorkflowExecutor

executor = WorkflowExecutor()

# Define matrix for parameter sweeps
matrix = {
    "algorithm": ["pc", "ges", "lingam"],
    "dataset": ["asia", "cancer"],
    "alpha": [0.01, 0.05]
}

# Expand into individual parameter combinations
jobs = executor.expand_matrix(matrix)
print(f"Generated {len(jobs)} jobs from matrix")  # Results in 12 jobs (3 × 2 × 2)

for i, job in enumerate(jobs):
    print(f"Job {i}: Algorithm={job['algorithm']}, Dataset={job['dataset']}, Alpha={job['alpha']}")
```

### Template Variable System

```python
# The WorkflowExecutor automatically validates template variables during parsing
# Template variables ({{variable}}) are checked against available context

# Example: Valid template usage
valid_workflow = {
    "id": "test-001",
    "description": "Template validation example", 
    "matrix": {"dataset": ["asia"], "algorithm": ["pc"]},
    "steps": [{
        "uses": "my-custom-action",
        "with": {
            "output": "/results/{{id}}/{{dataset}}_{{algorithm}}.xml",
            "description": "Processing {{dataset}} with {{algorithm}}"
        }
    }]
}

try:
    workflow = executor.parse_workflow_dict(valid_workflow)
    print("Template validation passed!")
except WorkflowExecutionError as e:
    if "Unknown template variables" in str(e):
        print(f"Template validation failed: {e}")
        # Example: "Unknown template variables: missing_var. Available context: id, dataset, algorithm"
    else:
        print(f"Workflow execution failed: {e}")
```

### Advanced Workflow Features

```python
# Example workflow YAML showing flexible action parameters
workflow_yaml = \"\"\"
id: "experiment-001"
description: "Flexible causal discovery experiment"
matrix:
  dataset: ["asia", "cancer"]
  algorithm: ["pc", "ges"]
  alpha: [0.01, 0.05]

steps:
  - name: "Structure Learning"
    uses: "my-structure-learner"
    with:
      data_path: "/experiments/data/{{dataset}}.csv"
      output_dir: "/experiments/results/{{id}}/{{algorithm}}/"
      alpha: "{{alpha}}"
      max_iter: 1000
      
  - name: "Validation"
    uses: "validate-graph"
    with:
      graph_path: "/experiments/results/{{id}}/{{algorithm}}/graph.graphml"
      metrics_output: "/experiments/results/{{id}}/{{algorithm}}/metrics.json"
\"\"\"

# Save and parse the workflow
with open("experiment.yml", "w") as f:
    f.write(workflow_yaml)
    
workflow = executor.parse_workflow("experiment.yml")

# Matrix expansion creates jobs with substituted variables
if "matrix" in workflow:
    jobs = executor.expand_matrix(workflow["matrix"])
    # Creates 8 jobs (2×2×2) with customizable file paths
    
    for job in jobs:
        print(f"Job: {job}")
        # Example output: {'dataset': 'asia', 'algorithm': 'pc', 'alpha': 0.01}
```

## Template Variable Context

Template variables can reference:

1. **Workflow properties**: `{{id}}`, `{{description}}`, `{{name}}`
2. **Matrix variables**: Any variables defined in the `matrix` section
3. **Step context**: Variables available during step execution
4. **File paths**: Dynamic path generation using workflow context

### Available Template Variables

| Context | Variables | Example |
|---------|-----------|---------|
| Workflow | `id`, `description`, `name` | `{{id}}` |
| Matrix | User-defined matrix vars | `{{dataset}}`, `{{algorithm}}` |
| Paths | `data_root`, `output_root` | `{{output_root}}/results` |

## Error Handling

The WorkflowExecutor provides detailed error reporting for:

- **Parse errors**: Invalid YAML/JSON syntax
- **Schema validation**: Workflow structure validation
- **Template errors**: Unknown or invalid template variables
- **Action errors**: Action execution failures
- **Matrix errors**: Invalid matrix definitions

---

**[← Previous: Registry](registry.md)** | **[Back to API Overview](overview.md)** | **[Next: Cache →](cache.md)**