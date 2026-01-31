# Schema Validation

The schema validation system provides robust workflow validation against JSON schemas with detailed error reporting and custom schema support.

## Core Functions

### causaliq_workflow.schema

::: causaliq_workflow.schema.validate_workflow
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: causaliq_workflow.schema.load_schema
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: causaliq_workflow.schema.load_workflow_file
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Exception Handling

::: causaliq_workflow.schema.WorkflowValidationError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Usage Examples

### Basic Workflow Validation

```python
from causaliq_workflow.schema import validate_workflow, WorkflowValidationError

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
            "uses": "my-custom-action",
            "with": {
                "alpha": 0.05,
            },
        }
    ],
}

try:
    result = validate_workflow(workflow_data)
    print("Workflow validation passed!")
    print(f"Validated workflow: {result['id']}")
except WorkflowValidationError as e:
    print(f"Validation failed: {e}")
    print(f"Schema path: {e.schema_path}")
    if hasattr(e, 'validator'):
        print(f"Validation details: {e.validator}")
```

### Loading and Using Custom Schemas

```python
from causaliq_workflow.schema import load_schema, validate_workflow
from pathlib import Path

# Load custom schema from file
schema_path = Path("my-custom-schema.json")
schema = load_schema(schema_path)

# Use custom schema with validation
try:
    validate_workflow(workflow_data, schema)
    print("Custom schema validation passed!")
except WorkflowValidationError as e:
    print(f"Custom validation failed: {e}")
```

### Loading Workflow Files

```python
from causaliq_workflow.schema import load_workflow_file
from pathlib import Path

# Load workflow from YAML or JSON file
workflow_path = Path("experiments/my-experiment.yml")
workflow_data = load_workflow_file(workflow_path)

print(f"Loaded workflow: {workflow_data['id']}")
print(f"Steps: {len(workflow_data.get('steps', []))}")

# File loading supports both YAML and JSON formats
json_workflow = load_workflow_file("experiments/experiment.json")
yaml_workflow = load_workflow_file("experiments/experiment.yml")
```

### Comprehensive Validation Pipeline

```python
from causaliq_workflow.schema import load_workflow_file, validate_workflow, WorkflowValidationError
from pathlib import Path

def validate_workflow_file(file_path: Path) -> dict:
    """Load and validate a workflow file with detailed error reporting."""
    try:
        # Load workflow from file
        workflow_data = load_workflow_file(file_path)
        print(f"✓ Loaded workflow from {file_path}")
        
        # Validate against schema
        validated_workflow = validate_workflow(workflow_data)
        print(f"✓ Schema validation passed for workflow '{validated_workflow['id']}'")
        
        return validated_workflow
        
    except FileNotFoundError:
        print(f"✗ Workflow file not found: {file_path}")
        raise
    except WorkflowValidationError as e:
        print(f"✗ Schema validation failed:")
        print(f"  Error: {e}")
        if hasattr(e, 'schema_path'):
            print(f"  Schema path: {e.schema_path}")
        raise
    except Exception as e:
        print(f"✗ Unexpected error loading workflow: {e}")
        raise

# Usage
workflow_files = [
    Path("experiments/causal-discovery.yml"),
    Path("experiments/model-validation.json"),
    Path("experiments/parameter-sweep.yml")
]

for workflow_file in workflow_files:
    try:
        workflow = validate_workflow_file(workflow_file)
        print(f"Ready to execute: {workflow['id']}\\n")
    except Exception as e:
        print(f"Skipping invalid workflow: {workflow_file}\\n")
```

## Schema Structure

The default workflow schema validates:

### Required Fields
- `id`: Unique workflow identifier
- `steps`: Array of workflow steps

### Optional Fields
- `name`: Human-readable workflow name
- `description`: Workflow description
- `matrix`: Parameter matrix for expansion
- `data_root`: Base path for data files
- `output_root`: Base path for output files

### Step Schema
Each step must include:
- `uses`: Action identifier
- `name` (optional): Human-readable step name
- `with` (optional): Action parameters

### Matrix Schema
Matrix definitions support:
- **Simple arrays**: `{"param": ["value1", "value2"]}`
- **Nested structures**: Complex parameter combinations
- **Type validation**: Ensures consistent parameter types

## Error Reporting

WorkflowValidationError provides detailed information:

```python
try:
    validate_workflow(invalid_workflow)
except WorkflowValidationError as e:
    print(f"Validation error: {e}")
    print(f"Schema path: {e.schema_path}")
    
    # Access underlying jsonschema validation details
    if hasattr(e, 'validator'):
        print(f"Failed constraint: {e.validator}")
        print(f"Schema context: {e.schema_path}")
```

## Custom Schema Development

```python
# Example custom schema with additional constraints
custom_schema = {
    "type": "object",
    "required": ["id", "version", "steps"],
    "properties": {
        "id": {"type": "string", "pattern": "^[a-z0-9-]+$"},
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "description": {"type": "string", "maxLength": 200},
        "matrix": {
            "type": "object",
            "patternProperties": {
                "^[a-z_]+$": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": ["string", "number"]}
                }
            }
        },
        "steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["uses"],
                "properties": {
                    "name": {"type": "string"},
                    "uses": {"type": "string"},
                    "with": {"type": "object"}
                }
            }
        }
    }
}

# Save and use custom schema
import json
with open("custom-workflow-schema.json", "w") as f:
    json.dump(custom_schema, f, indent=2)

custom_schema_obj = load_schema("custom-workflow-schema.json")
validate_workflow(workflow_data, custom_schema_obj)
```

---

**[← Previous: Workflow Engine](workflow.md)** | **[Back to API Overview](overview.md)** | **[Next: CLI Interface →](cli.md)**