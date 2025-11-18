# Action Registry

The action registry provides centralized discovery, management, and execution of workflow actions with plugin architecture support.

## Core Classes

### causaliq_workflow.registry

::: causaliq_workflow.registry.ActionRegistry
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
      members:
        - get_available_actions
        - get_action_class
        - has_action
        - execute_action
        - list_actions_by_package

::: causaliq_workflow.registry.WorkflowContext
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Exception Handling

::: causaliq_workflow.registry.ActionRegistryError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Usage Examples

### Basic Registry Operations

```python
from causaliq_workflow.registry import ActionRegistry, ActionRegistryError

# Create registry instance
registry = ActionRegistry()

# List all available actions
actions = registry.get_available_actions()
for action_name, action_class in actions.items():
    print(f"Action: {action_name} (v{action_class.version})")

# Check if specific action exists
if registry.has_action("my-structure-learner"):
    action_class = registry.get_action_class("my-structure-learner")
    print(f"Found action: {action_class.description}")

# Execute action directly through registry
try:
    result = registry.execute_action(
        "my-structure-learner",
        {"data_path": "/data/asia.csv", "alpha": 0.05}
    )
    print(f"Execution result: {result}")
except ActionRegistryError as e:
    print(f"Registry error: {e}")
```

### Plugin Discovery

```python
# List actions by package (useful for plugin systems)
actions_by_package = registry.list_actions_by_package()
for package, actions in actions_by_package.items():
    print(f"Package: {package}")
    for action in actions:
        print(f"  - {action}")

# Discover actions from specific packages
registry = ActionRegistry(packages=["my_custom_actions"])
custom_actions = registry.get_available_actions()
```

### Workflow Context

```python
from causaliq_workflow.registry import WorkflowContext

# Create workflow context for action execution
context = WorkflowContext(
    mode="run",
    matrix={"dataset": ["asia", "cancer"], "algorithm": ["pc", "ges"]},
)

# Context provides execution metadata for action optimization
print(f"Execution mode: {context.mode}")
print(f"Matrix definition: {context.matrix}")

# Actions can optimize across the full matrix space
if len(context.matrix.get("dataset", [])) > 1:
    print("Multi-dataset experiment - can pre-load data")
```

## Architecture Notes

The ActionRegistry uses Python's module discovery system to automatically find and register actions. Actions are discovered by:

1. **Package scanning** - Searches specified packages for Action subclasses
2. **Automatic registration** - Actions register themselves via class definition
3. **Name-based lookup** - Actions identified by their `name` class attribute
4. **Version tracking** - Support for action versioning and compatibility

This design enables a flexible plugin architecture where actions can be distributed as separate packages and automatically discovered at runtime.

---

**[← Previous: Actions](actions.md)** | **[Back to API Overview](../api.md)** | **[Next: Workflow Engine →](workflow.md)**