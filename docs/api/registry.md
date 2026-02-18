# Action Registry

The action registry provides centralised discovery, management, and execution
of workflow actions with plugin architecture support.

The registry uses entry points to discover action providers from installed
packages, enabling a clean plugin architecture where actions can be distributed
as separate packages.

## causaliq-core Integration

The registry imports the following from causaliq-core:

- **CausalIQActionProvider** - Base class that all discovered actions must
  implement
- **ActionExecutionError** - Exception type for action execution failures

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
        - validate_workflow_actions

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
if registry.has_action("causaliq-workflow"):
    action_class = registry.get_action_class("causaliq-workflow")
    print(f"Found action: {action_class.description}")

# Execute action directly through registry
try:
    result = registry.execute_action(
        "causaliq-workflow",
        action="echo",
        parameters={"message": "Hello", "nodes": 3},
        mode="dry-run",
    )
    print(f"Execution result: {result}")
except ActionRegistryError as e:
    print(f"Registry error: {e}")
```

### Entry Point Discovery

Actions are discovered via Python entry points. Packages register their
actions in `pyproject.toml`:

```toml
[project.entry-points."causaliq.actions"]
my-package = "my_package:ActionProvider"
```

The registry discovers entry points at startup (metadata only) and loads them
lazily on first use to avoid circular imports.

```python
# Entry points are loaded when first accessed
registry = ActionRegistry()

# Check discovered entry points
print(f"Available actions: {list(registry.get_available_actions().keys())}")
```

### Workflow Context

```python
from causaliq_workflow.registry import WorkflowContext

# Create workflow context for action execution
context = WorkflowContext(
    mode="run",
    matrix={"dataset": ["asia", "cancer"], "algorithm": ["pc", "ges"]},
    matrix_values={"dataset": "asia", "algorithm": "pc"},
)

# Context provides execution metadata for action optimisation
print(f"Execution mode: {context.mode}")
print(f"Matrix definition: {context.matrix}")
print(f"Current matrix values: {context.matrix_values}")

# Get cache key for current matrix combination
print(f"Matrix key: {context.matrix_key}")  # SHA-256 hash, 16 chars
```

## Architecture Notes

The ActionRegistry uses Python's entry point system to automatically find and
register actions. Actions are discovered by:

1. **Entry point scanning** - Discovers `causaliq.actions` entry points from
   installed packages
2. **Lazy loading** - Entry points recorded at startup but loaded on first use
3. **Module fallback** - Also scans imported modules for CausalIQActionProvider
   subclasses
4. **Name-based lookup** - Actions identified by their entry point name or
   `name` class attribute

This design enables a flexible plugin architecture where actions can be
distributed as separate packages and automatically discovered at runtime,
while avoiding circular import issues.

---

**[← Previous: Actions](actions.md)** | **[Back to API Overview](overview.md)** | **[Next: Workflow Engine →](workflow.md)**