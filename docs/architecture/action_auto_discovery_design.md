# Action Auto-Discovery Design

## Overview

The auto-discovery system implements a **convention-over-configuration** approach where actions are automatically found and registered without any configuration files. This design eliminates the need for manual registry management while providing a seamless plugin ecosystem for causal discovery workflows.

## How Auto-Discovery Works: The Complete Journey

### Phase 1: System Initialization

#### Step 1: Workflow Engine Starts
When a user runs `causaliq-workflow experiment.yml`:

1. **WorkflowExecutor initialization**: Creates a new `WorkflowExecutor` instance
2. **ActionRegistry creation**: Instantiates `ActionRegistry()` which triggers discovery
3. **Discovery activation**: The registry immediately begins scanning for actions

#### Step 2: Python Environment Scanning
The system methodically searches the Python environment:

1. **Module enumeration**: Uses `pkgutil.iter_modules()` to list all importable modules
2. **Safe import attempts**: Tries to import each module with comprehensive error handling
3. **Module filtering**: Focuses only on modules that successfully import

### Phase 2: Action Detection and Registration

#### Step 3: Convention-Based Detection
For each successfully imported module, the system applies the discovery convention:

1. **Attribute inspection**: Checks if the module has an attribute named 'CausalIQAction'
2. **Type validation**: Verifies that the 'CausalIQAction' attribute is a class
3. **Inheritance verification**: Confirms it inherits from `causaliq_workflow.action.Action`
4. **Action validation**: Ensures the class implements required abstract methods

#### Step 4: Automatic Registration
When an action is detected:

1. **Name extraction**: Uses the module name as the action identifier
2. **Registry storage**: Stores mapping: `{module_name: CausalIQAction_class}`
3. **Metadata collection**: Gathers action name, version, description from the class
4. **Availability confirmation**: Marks the action as ready for workflow use

### Phase 3: Workflow Execution Integration

#### Step 5: YAML Parsing and Action Resolution
When processing a workflow file:

```yaml
steps:
  - name: "Custom Analysis"
    uses: "my_custom_action"  # This triggers action lookup
    with:
      parameter: "value"
```

The system follows this resolution path:

1. **Action name extraction**: Parses `uses: "my_custom_action"`
2. **Registry lookup**: Searches registered actions for "my_custom_action"
2. **Class retrieval**: Gets the corresponding CausalIQAction class
3. **Instance creation**: Instantiates the action with `CausalIQAction()`

#### Step 6: Dynamic Action Execution
During step execution:

1. **Parameter preparation**: Collects parameters from the `with` block
2. **Input validation**: Action validates its own inputs using schemas
3. **Execution**: Calls `action.run(inputs)` with validated parameters
4. **Output handling**: Processes and stores action outputs

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
[project]
name = "causaliq-pc-algorithm"
version = "1.0.0"
description = "PC algorithm implementation for CausalIQ workflows"
dependencies = [
    "causaliq-workflow>=0.1.0",
    "networkx>=2.8.0",
    "pandas>=1.5.0"
]
```

#### Step 2: Implement the Action Convention
**File: causaliq_pc_algorithm/__init__.py**
```python
from causaliq_workflow.action import CausalIQAction
import pandas as pd
import networkx as nx

# Must be named 'CausalIQAction' for auto-discovery
class CausalIQAction(CausalIQAction):
    name = "causaliq-pc-algorithm"
    version = "1.0.0" 
    description = "PC algorithm for causal structure learning"
    
    def run(self, inputs):
        # Read data
        data = pd.read_csv(inputs['dataset'])
        
        # Run PC algorithm
        alpha = inputs.get('alpha', 0.05)
        graph = self.pc_algorithm(data, alpha)
        
        # Save results
        output_path = inputs['output_path']
        nx.write_graphml(graph, f"{output_path}/graph.xml")
        
        return {
            "graph_path": f"{output_path}/graph.xml",
            "nodes": len(graph.nodes),
            "edges": len(graph.edges)
        }
    
    def pc_algorithm(self, data, alpha):
        # PC algorithm implementation
        pass
```

#### Step 3: Installation and Immediate Availability
```bash
# Install the package
pip install causaliq-pc-algorithm

# Action is immediately available in workflows
causaliq-workflow my-experiment.yml
```

**File: my-experiment.yml**
```yaml
name: "PC Algorithm Test"
steps:
  - name: "Learn Structure"
    uses: "causaliq-pc-algorithm"  # Automatically discovered
    with:
      dataset: "/data/asia.csv"
      alpha: 0.01
      output_path: "/results/pc"
```

## Discovery Process Implementation Details

### Module Introspection Strategy
The system uses Python's built-in introspection capabilities:

```python
import pkgutil
import importlib
from typing import Dict, Type

class ActionRegistry:
    def __init__(self):
        self.actions: Dict[str, Type[Action]] = {}
        self._discover_actions()
    
    def _discover_actions(self):
        """Automatically discover and register all available actions."""
        
        # Scan all importable modules
        for finder, module_name, ispkg in pkgutil.iter_modules():
            try:
                # Safely attempt to import module
                module = importlib.import_module(module_name)
                
                # Check for CausalIQAction class using naming convention
                if hasattr(module, 'CausalIQAction'):
                    action_class = getattr(module, 'CausalIQAction')
                    
                    # Verify it's actually a CausalIQAction subclass
                    if (isinstance(action_class, type) and 
                        issubclass(action_class, CausalIQAction) and 
                        action_class != CausalIQAction):
                        
                        # Register using module name
                        self.actions[module_name] = action_class
                        
            except ImportError:
                # Skip modules that can't be imported
                continue
```

### Error Handling and Resilience
The discovery process is designed to be robust:

1. **Import error tolerance**: Failed module imports are silently skipped
2. **Type safety**: Strict validation of action classes
3. **Namespace isolation**: Each action operates in its own namespace
4. **Graceful degradation**: System continues working even if some actions fail to load

### Performance Considerations
The auto-discovery system is optimized for efficiency:

1. **Lazy loading**: Actions are only instantiated when needed
2. **One-time discovery**: Module scanning happens once during registry creation
3. **Minimal overhead**: Discovery adds negligible startup time
4. **Cached results**: Action registry is reused across workflow steps

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
    "causaliq-workflow>=0.1.0",    # Framework dependency
    "rpy2>=3.5.0",                 # R interface (if needed)
    "jpype1>=1.4.0",               # Java interface (if needed)
    "scikit-learn>=1.2.0"          # Algorithm dependencies
]
```

### Cross-Language Bridge Pattern
For R and Java integrations:

```python
class RBridgeAction(CausalIQAction):
    def __init__(self):
        # Initialize R environment
        self.r_session = self._setup_r_environment()
    
    def run(self, inputs):
        # Execute R code through rpy2
        result = self.r_session.run_algorithm(inputs)
        return self._convert_r_output(result)
```

## Benefits of the Auto-Discovery Approach

### For Users
1. **Zero configuration**: Install and use immediately
2. **No registry management**: No config files to maintain
3. **Standard workflow**: Familiar pip install → use pattern
4. **Automatic updates**: New action versions available immediately

### For Developers
1. **Standard Python packaging**: No custom build systems
2. **Simple convention**: Just export a 'CausalIQAction' class
3. **Full Python ecosystem**: Use any Python dependencies
4. **Independent development**: No coordination with core framework needed

### For the Ecosystem
1. **Organic growth**: Easy to create and share actions
2. **Version management**: Standard semantic versioning
3. **Quality control**: Actions are regular Python packages with testing
4. **Documentation**: Standard Python documentation tools apply