# Action Auto-Discovery Design

## Overview

The auto-discovery system implements a **plugin architecture** using Python
entry points where actions are automatically found and registered without
any configuration files. This design eliminates the need for manual registry
management while providing a seamless plugin ecosystem for causal discovery
workflows.

The system uses **lazy loading** to avoid circular import issues - entry
points are discovered at startup (metadata only), but the actual action
classes are only loaded when first used.

## How Auto-Discovery Works: The Complete Journey

### Phase 1: System Initialisation

#### Step 1: Workflow Engine Starts
When a user runs `causaliq-workflow experiment.yml`:

1. **WorkflowExecutor initialisation**: Creates a new `WorkflowExecutor`
   instance
2. **ActionRegistry creation**: Instantiates `ActionRegistry()` which triggers
   discovery
3. **Entry point discovery**: The registry scans for `causaliq.actions` entry
   points

#### Step 2: Entry Point Discovery (Lazy Loading)
The system discovers actions without importing them:

1. **Entry point enumeration**: Uses `importlib.metadata.entry_points()` to
   find all packages that declare `causaliq.actions` entry points
2. **Metadata recording**: Stores entry point metadata (name, module path)
   without loading
3. **Deferred loading**: Actual imports happen only when an action is first
   used

This lazy loading approach is critical for avoiding circular imports, since
action packages (like `causaliq-knowledge`) depend on `causaliq-workflow`.

### Phase 2: Action Loading (On Demand)

#### Step 3: First Use Triggers Loading
When a workflow references an action:

```yaml
steps:
  - name: "Generate Graph"
    uses: "causaliq-knowledge"  # Triggers lazy load
    with:
      action: "generate_graph"
```

The system:

1. **Entry point lookup**: Finds the entry point for "causaliq-knowledge"
2. **Class loading**: Calls `entry_point.load()` to import the action class
3. **Type validation**: Verifies it's a valid `BaseActionProvider` subclass
4. **Caching**: Stores the loaded class for future use

#### Step 4: Action Execution
Once loaded:

1. **Parameter preparation**: Collects parameters from the `with` block
2. **Input validation**: Action validates its own inputs using schemas
3. **Execution**: Calls `action.run(inputs)` with validated parameters
4. **Output handling**: Processes and stores action outputs

### Phase 3: Fallback Module Scanning

For backwards compatibility and development scenarios, the registry also
supports module scanning:

1. **Module enumeration**: Scans `sys.modules` for already-imported modules
2. **Convention detection**: Looks for modules exporting `ActionProvider`
3. **Registration**: Adds discovered actions to the registry

## The Plugin Developer Experience

### Creating an Action Package: Step-by-Step

#### Step 1: Standard Python Package Setup
Developers start with familiar Python packaging:

```bash
mkdir causaliq-pc-algorithm
cd causaliq-pc-algorithm
```

**File: pyproject.toml**
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "causaliq-pc-algorithm"
version = "1.0.0"
description = "PC algorithm implementation for CausalIQ workflows"
dependencies = [
    "causaliq-workflow>=0.1.1",
    "networkx>=2.8.0",
    "pandas>=1.5.0"
]

# CRITICAL: Register your action as an entry point
[project.entry-points."causaliq.actions"]
causaliq-pc-algorithm = "causaliq_pc_algorithm:ActionProvider"
```

The entry point declaration tells `causaliq-workflow` where to find your
action class. The format is:

```
action-name = "module.path:ClassName"
```

#### Step 2: Implement the Action Class
**File: src/causaliq_pc_algorithm/__init__.py**
```python
"""PC algorithm action for CausalIQ workflows."""

from causaliq_workflow.action import BaseActionProvider
import pandas as pd
import networkx as nx


# The class name can be anything, but must match the entry point
class ActionProvider(BaseActionProvider):
    """PC algorithm for causal structure learning."""

    name = "causaliq-pc-algorithm"
    version = "1.0.0"
    description = "PC algorithm for causal structure learning"

    def run(self, inputs, **kwargs):
        """Execute the PC algorithm.

        Args:
            inputs: Dictionary containing:
                - dataset: Path to CSV data file
                - alpha: Significance level (default: 0.05)
                - output_path: Where to save results

        Returns:
            Dictionary with graph_path, nodes, and edges count.
        """
        # Read data
        data = pd.read_csv(inputs["dataset"])

        # Run PC algorithm
        alpha = inputs.get("alpha", 0.05)
        graph = self._pc_algorithm(data, alpha)

        # Save results
        output_path = inputs["output_path"]
        nx.write_graphml(graph, f"{output_path}/graph.xml")

        return {
            "graph_path": f"{output_path}/graph.xml",
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
        }

    def _pc_algorithm(self, data, alpha):
        """PC algorithm implementation."""
        # Implementation here
        pass
```

#### Step 3: Installation and Immediate Availability
```bash
# Install the package (editable mode for development)
pip install -e .

# Action is immediately available in workflows
causaliq-workflow my-experiment.yml
```

**File: my-experiment.yml**
```yaml
description: "PC Algorithm Test"
id: pc-test

steps:
  - name: "Learn Structure"
    uses: "causaliq-pc-algorithm"  # Automatically discovered via entry point
    with:
      dataset: "/data/asia.csv"
      alpha: 0.01
      output_path: "/results/pc"
```

## Entry Point Discovery Implementation

### The Lazy Loading Pattern

```python
import sys
from importlib.metadata import entry_points
from typing import Dict, Optional, Type

class ActionRegistry:
    def __init__(self):
        self._actions: Dict[str, Type[BaseActionProvider]] = {}
        self._entry_points: Dict[str, Any] = {}  # Metadata only
        self._discover_entry_points()

    def _discover_entry_points(self) -> None:
        """Discover entry points WITHOUT importing them."""
        # Python 3.10+ API
        if sys.version_info >= (3, 10):
            eps = entry_points(group="causaliq.actions")
        else:
            # Python 3.9 compatibility
            all_eps = entry_points()
            eps = all_eps.get("causaliq.actions", [])

        for ep in eps:
            # Store metadata only - no imports yet!
            self._entry_points[ep.name] = ep

    def _load_entry_point(self, name: str) -> Optional[Type[BaseActionProvider]]:
        """Load an entry point on first use."""
        if name not in self._entry_points:
            return None

        ep = self._entry_points[name]
        action_class = ep.load()  # Import happens here

        # Validate and cache
        if issubclass(action_class, BaseActionProvider):
            self._actions[name] = action_class
            return action_class
        return None

    def get_action_class(self, name: str) -> Type[BaseActionProvider]:
        """Get action class, loading from entry point if needed."""
        # Return cached action
        if name in self._actions:
            return self._actions[name]

        # Try lazy loading from entry point
        if name in self._entry_points:
            action_class = self._load_entry_point(name)
            if action_class:
                return action_class

        raise ActionRegistryError(f"Action '{name}' not found")
```

### Why Lazy Loading?

Lazy loading solves a critical circular import problem:

```
causaliq-workflow (provides BaseActionProvider base class)
       ↑
       └── causaliq-knowledge (imports BaseActionProvider, exports action)
```

If `causaliq-workflow` eagerly imported `causaliq-knowledge` during registry
initialisation, it would fail because `causaliq-knowledge` needs to import
from `causaliq-workflow` first.

By deferring the import until the action is actually used, we ensure:
1. `causaliq-workflow` initialises completely first
2. `causaliq-knowledge` can import from it safely
3. The action class is then loaded on demand

## Ecosystem Integration Patterns

### Distribution Strategy
Action packages follow standard Python distribution:

1. **PyPI publishing**: `pip install causaliq-tetrad-bridge`
2. **GitHub releases**: Direct installation from repositories
3. **Local development**: `pip install -e .` for development packages
4. **Version management**: Standard semantic versioning

### Dependency Management
Actions declare their dependencies naturally:

```toml
# Action package dependencies
dependencies = [
    "causaliq-workflow>=0.1.1",    # Framework dependency
    "rpy2>=3.5.0",                 # R interface (if needed)
    "jpype1>=1.4.0",               # Java interface (if needed)
    "scikit-learn>=1.2.0"          # Algorithm dependencies
]

# REQUIRED: Entry point registration
[project.entry-points."causaliq.actions"]
my-action = "my_action:ActionProvider"
```

### Cross-Language Bridge Pattern
For R and Java integrations:

```python
class RBridgeAction(BaseActionProvider):
    """Bridge to R-based causal discovery algorithms."""

    name = "r-bridge-action"
    version = "1.0.0"
    description = "Execute R algorithms via rpy2"

    def __init__(self):
        super().__init__()
        # Initialise R environment
        self.r_session = self._setup_r_environment()

    def run(self, inputs, **kwargs):
        # Execute R code through rpy2
        result = self.r_session.run_algorithm(inputs)
        return self._convert_r_output(result)
```

## Benefits of Entry Point Discovery

### For Users
1. **Zero configuration**: Install and use immediately
2. **No registry management**: No config files to maintain
3. **Standard workflow**: Familiar `pip install` → use pattern
4. **Automatic updates**: New action versions available immediately

### For Developers
1. **Standard Python packaging**: Use pyproject.toml entry points
2. **Simple registration**: One line in pyproject.toml
3. **Full Python ecosystem**: Use any Python dependencies
4. **Independent development**: No coordination with core framework needed
5. **No circular imports**: Lazy loading handles dependencies correctly

### For the Ecosystem
1. **Organic growth**: Easy to create and share actions
2. **Version management**: Standard semantic versioning
3. **Quality control**: Actions are regular Python packages with testing
4. **Documentation**: Standard Python documentation tools apply

## Quick Reference: Creating a New Action

### Minimal Example

**pyproject.toml:**
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "my-causaliq-action"
version = "1.0.0"
dependencies = ["causaliq-workflow>=0.1.1"]

[project.entry-points."causaliq.actions"]
my-causaliq-action = "my_causaliq_action:ActionProvider"

[tool.setuptools.packages.find]
where = ["src"]
```

**src/my_causaliq_action/__init__.py:**
```python
from causaliq_workflow.action import BaseActionProvider


class ActionProvider(BaseActionProvider):
    name = "my-causaliq-action"
    version = "1.0.0"
    description = "My custom action"

    def run(self, inputs, **kwargs):
        # Your implementation here
        return {"status": "complete", "result": inputs.get("value", 0) * 2}
```

**Usage in workflow.yaml:**
```yaml
description: "Test my action"
id: test-my-action

steps:
  - name: "Run my action"
    uses: "my-causaliq-action"
    with:
      value: 42
```

### Checklist

- [ ] Create `pyproject.toml` with entry point registration
- [ ] Implement action class inheriting from `BaseActionProvider`
- [ ] Set `name`, `version`, `description` class attributes
- [ ] Implement `run(self, inputs, **kwargs)` method
- [ ] Return a dictionary from `run()`
- [ ] Install with `pip install -e .` for development
- [ ] Test with `causaliq-workflow --dry-run workflow.yaml`