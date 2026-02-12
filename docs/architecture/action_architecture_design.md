# Action Architecture

## Overview

The action architecture provides reusable, automatically-discoverable workflow
components following GitHub Actions patterns. Actions are **zero-configuration
plugins** that become available immediately upon installation, with no registry
files or manual setup required.

## Auto-Discovery Action Framework

### How Actions Are Found and Used

#### The Discovery Lifecycle

1. **Installation Phase**: Developer installs action package
   (`pip install my-action`)
2. **Discovery Phase**: Framework discovers entry points at startup (metadata
   only)
3. **Lazy Loading Phase**: Action classes are loaded on first use
4. **Execution Phase**: Workflows reference actions by name
   (`uses: "my-action"`)

#### Entry Point-Based Action Registration

Actions register themselves using Python entry points in `pyproject.toml`:

```toml
# pyproject.toml
[project.entry-points."causaliq.actions"]
my-action = "my_action:ActionProvider"
```

The action class implementation:

```python
# my_action/__init__.py
from causaliq_workflow.action import BaseActionProvider


class ActionProvider(BaseActionProvider):
    name = "my-action"
    version = "1.0.0"
    description = "Performs custom analysis"

    def run(self, inputs, **kwargs):
        # Implementation here
        return {"status": "complete"}
```

### Base Action Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import semantic_version

@dataclass
class ActionInput:
    """Define action input specification."""
    name: str
    description: str
    required: bool = False
    default: Any = None
    type_hint: str = "Any"

@dataclass
class ActionOutput:
    """Define action output specification."""
    name: str
    description: str
    value: Any

class BaseActionProvider(ABC):
    """Base class for all workflow actions."""
    
    # Action metadata
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    
    # Input/output specifications
    inputs: Dict[str, ActionInput] = {}
    outputs: Dict[str, str] = {}  # name -> description mapping
    
    @abstractmethod
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action with validated inputs, return outputs."""
        pass
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and process input values."""
        validated = {}
        
        for input_name, input_spec in self.inputs.items():
            if input_spec.required and input_name not in inputs:
                raise ValueError(f"Required input '{input_name}' missing for action {self.name}")
            
            value = inputs.get(input_name, input_spec.default)
            validated[input_name] = value
        
        return validated
    
    def format_outputs(self, raw_outputs: Dict[str, Any]) -> Dict[str, ActionOutput]:
        """Format raw outputs with metadata."""
        formatted = {}
        
        for name, value in raw_outputs.items():
            description = self.outputs.get(name, f"Output from {self.name}")
            formatted[name] = ActionOutput(
                name=name,
                description=description,
                value=value
            )
        
        return formatted
```

### Auto-Discovery Action Registry

The registry automatically discovers and manages actions without configuration:

```python
import pkgutil
import importlib
from typing import Dict, Type, Any

class ActionRegistry:
    """Automatically discover and manage workflow actions."""
    
    def __init__(self):
        self._actions: Dict[str, Type[BaseActionProvider]] = {}
        self._discover_actions()  # Automatic discovery on initialization
    
    def _discover_actions(self):
        """Scan Python environment for action packages."""
        
        # Iterate through all importable modules
        for finder, module_name, ispkg in pkgutil.iter_modules():
            try:
                # Attempt to import the module
                module = importlib.import_module(module_name)
                
                # Check if module exports an 'ActionProvider' class
                if hasattr(module, 'ActionProvider'):
                    action_class = getattr(module, 'ActionProvider')
                    
                    # Verify it's a proper BaseActionProvider subclass
                    if (isinstance(action_class, type) and 
                        issubclass(action_class, BaseActionProvider) and 
                        action_class != BaseActionProvider):
                        
                        # Register using module name as action identifier
                        self._actions[module_name] = action_class
                        
            except ImportError:
                # Skip modules that can't be imported
                continue
    
    def get_available_actions(self) -> Dict[str, Type[BaseActionProvider]]:
        """Return copy of available actions."""
        return self._actions.copy()
    
    def get_action_class(self, action_name: str) -> Type[BaseActionProvider]:
        """Get action class by name."""
        if action_name not in self._actions:
            raise ActionRegistryError(f"Action '{action_name}' not found. Available actions: {list(self._actions.keys())}")
        return self._actions[action_name]
```

#### How Discovery Works Step-by-Step

1. **Registry Initialization**: When `ActionRegistry()` is created, discovery starts automatically
2. **Module Scanning**: Uses `pkgutil.iter_modules()` to iterate through all Python modules
3. **Safe Import**: Attempts to import each module, skipping those that fail
4. **Convention Check**: Looks for a class named 'ActionProvider' in each module
5. **Validation**: Ensures the ActionProvider class inherits from the base BaseActionProvider class
6. **Registration**: Maps module name to ActionProvider class for workflow lookup

#### Action Package Development Workflow

**Step 1: Create Standard Python Package**
```bash
mkdir my_custom_action
cd my_custom_action
```

**Step 2: Define Package Structure**
```
my_custom_action/
├── pyproject.toml
├── my_custom_action/
│   └── __init__.py  # Must export 'ActionProvider' class
└── README.md
```

**Step 3: Implement Action Convention**
```python
# my_custom_action/__init__.py
from causaliq_workflow.action import BaseActionProvider

class ActionProvider(BaseActionProvider):  # Must be named 'ActionProvider'
    name = "my-custom-action"
    version = "1.0.0" 
    description = "Custom analysis action"
    
    def run(self, inputs):
        # Action implementation
        result = self.perform_analysis(inputs['data'])
        return {"analysis_result": result}
```

**Step 4: Install and Use Immediately**
```bash
pip install my_custom_action
causaliq-workflow my-experiment.yml  # Action automatically available
```
```

## Auto-Discovery Action Examples

### Example 1: Simple Analysis Action

**Package: causaliq_analysis**

```python
# causaliq_analysis/__init__.py
from causaliq_workflow.action import BaseActionProvider
import pandas as pd
import networkx as nx

class ActionProvider(BaseActionProvider):  # Auto-discovered by this name
    name = "causaliq-analysis"
    version = "1.0.0"
    description = "Basic causal graph analysis"
    
    def run(self, inputs):
        """Analyze causal graph structure."""
        graph_path = inputs['graph_path']
        graph = nx.read_graphml(graph_path)
        
        analysis = {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges), 
            "density": nx.density(graph),
            "is_dag": nx.is_directed_acyclic_graph(graph)
        }
        
        return {"analysis": analysis}
```

**Usage in Workflow:**
```yaml
steps:
  - name: "Analyze Graph"
    uses: "causaliq_analysis"  # Automatically discovered
    with:
      graph_path: "/results/learned_graph.xml"
```

### Example 2: Data Loading Action

**Package: causaliq_data**

```python
# causaliq_data/__init__.py  
from causaliq_workflow.action import BaseActionProvider
import pandas as pd
from pathlib import Path

class ActionProvider(BaseActionProvider):
    name = "causaliq-data"
    version = "2.1.0"
    description = "Load and preprocess causal datasets"
    
    def run(self, inputs):
        """Load dataset with optional preprocessing."""
        dataset_name = inputs['dataset']
        sample_size = inputs.get('sample_size')
        
        # Load from standard datasets
        if dataset_name == "asia":
            data = self._load_asia_network()
        elif dataset_name == "cancer":
            data = self._load_cancer_network()
        else:
            # Load from file path
            data = pd.read_csv(dataset_name)
        
        # Apply sampling if requested
        if sample_size and sample_size < len(data):
            data = data.sample(n=sample_size, random_state=42)
        
        output_path = inputs['output_path']
        data.to_csv(f"{output_path}/data.csv", index=False)
        
        return {
            "data_path": f"{output_path}/data.csv",
            "rows": len(data),
            "columns": len(data.columns)
        }
```

### Example 3: Algorithm Bridge Action

**Package: causaliq_pc_algorithm**

```python
# causaliq_pc_algorithm/__init__.py
from causaliq_workflow.action import BaseActionProvider
import pandas as pd
import networkx as nx

class ActionProvider(BaseActionProvider):
    name = "causaliq-pc-algorithm" 
    version = "1.5.2"
    description = "PC algorithm for causal structure learning"
    
    def run(self, inputs):
        """Execute PC algorithm."""
        data_path = inputs['data_path']
        alpha = inputs.get('alpha', 0.05)
        output_path = inputs['output_path']
        
        # Load data
        data = pd.read_csv(data_path)
        
        # Run PC algorithm (implementation details omitted)
        graph = self._execute_pc_algorithm(data, alpha)
        
        # Save results
        nx.write_graphml(graph, f"{output_path}/graph.xml")
        
        # Generate metadata
        metadata = {
            "algorithm": "pc",
            "alpha": alpha,
            "nodes": len(graph.nodes),
            "edges": len(graph.edges)
        }
        
        with open(f"{output_path}/metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "graph_path": f"{output_path}/graph.xml",
            "metadata_path": f"{output_path}/metadata.json",
            "edge_count": len(graph.edges)
        }
            columns = dataset.columns.tolist()
            np.random.shuffle(columns)
            randomised = dataset[columns]
            transformation_log.append(f"Shuffled column order: {' -> '.join(columns)}")
            
        elif strategy == "subsample":
            subsample_size = min(len(dataset) // 2, 1000)
            randomised = dataset.sample(n=subsample_size).reset_index(drop=True)
            transformation_log.append(f"Subsampled to {subsample_size} rows")
            
        elif strategy == "bootstrap":
            randomised = dataset.sample(n=len(dataset), replace=True).reset_index(drop=True)
            transformation_log.append("Bootstrap resampling applied")
            
        else:
            raise ValueError(f"Unknown randomisation strategy: {strategy}")
        
        return {
            "randomised_dataset": randomised,
            "transformation_log": transformation_log
        }
```

### Algorithm Execution Actions

```python
import networkx as nx

class CausalDiscoveryAction(BaseActionProvider):
    """Execute causal discovery algorithm from various packages."""
    
    name = "causal-discovery"
    version = "1.0.0"
    description = "Run causal discovery algorithm with automatic package detection"
    
    inputs = {
        "algorithm": ActionInput("algorithm", "Algorithm name (pc, ges, lingam, etc.)", required=True),
        "package": ActionInput("package", "Algorithm package (bnlearn, tetrad, causal-learn, auto)", default="auto"),
        "data": ActionInput("data", "Input dataset", required=True),
        "parameters": ActionInput("parameters", "Algorithm-specific parameters", default={})
    }
    
    outputs = {
        "learned_graph": "Learned causal graph as NetworkX DiGraph",
        "algorithm_info": "Information about algorithm execution",
        "performance_metrics": "Execution time, memory usage, convergence info"
    }
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute causal discovery algorithm."""
        algorithm = inputs["algorithm"].lower()
        package = inputs["package"]
        data = inputs["data"]
        parameters = inputs["parameters"]
        
        # Auto-detect package if needed
        if package == "auto":
            package = self._detect_best_package(algorithm)
        
        # Execute algorithm
        start_time = time.time()
        
        if package == "bnlearn":
            learned_graph, algo_info = self._execute_bnlearn(algorithm, data, parameters)
        elif package == "tetrad":
            learned_graph, algo_info = self._execute_tetrad(algorithm, data, parameters)
        elif package == "causal-learn":
            learned_graph, algo_info = self._execute_causal_learn(algorithm, data, parameters)
        else:
            raise ValueError(f"Unsupported package: {package}")
        
        execution_time = time.time() - start_time
        
        performance_metrics = {
            "execution_time_seconds": execution_time,
            "algorithm": algorithm,
            "package": package,
            "num_variables": len(data.columns),
            "num_samples": len(data),
            "num_edges": learned_graph.number_of_edges()
        }
        
        return {
            "learned_graph": learned_graph,
            "algorithm_info": algo_info,
            "performance_metrics": performance_metrics
        }
    
    def _detect_best_package(self, algorithm: str) -> str:
        """Detect best available package for algorithm."""
        algorithm_packages = {
            "pc": ["bnlearn", "causal-learn", "tetrad"],
            "ges": ["causal-learn", "tetrad"], 
            "lingam": ["causal-learn"],
            "iamb": ["bnlearn"],
            "gs": ["bnlearn"]
        }
        
        preferred_packages = algorithm_packages.get(algorithm, ["causal-learn"])
        
        # Check availability and return first available
        for package in preferred_packages:
            if self._is_package_available(package):
                return package
        
        raise RuntimeError(f"No available package found for algorithm: {algorithm}")
    
    def _execute_bnlearn(self, algorithm: str, data: pd.DataFrame, 
                        parameters: Dict) -> tuple:
        """Execute algorithm using R bnlearn."""
        try:
            import rpy2.robjects as ro
            from rpy2.robjects import pandas2ri
        }
```

## Benefits of Auto-Discovery Architecture

### For Action Developers

#### Zero Configuration Setup
- **No registry management**: No need to maintain configuration files or plugin registries
- **Standard Python patterns**: Use familiar `pyproject.toml`, `pip install`, and package structure
- **Immediate availability**: Actions become available as soon as the package is installed
- **Simple convention**: Just export a class named 'Action' from the package

#### Development Workflow  
1. **Create package**: Standard Python package with `pyproject.toml`
2. **Implement action**: Export 'Action' class following the interface
3. **Test locally**: `pip install -e .` for development testing
4. **Publish**: Standard PyPI publishing or GitHub releases
5. **Use immediately**: Actions available in all workflows without restart

### For Workflow Authors

#### Seamless Integration
- **Familiar syntax**: Uses standard GitHub Actions-style `uses: "action-name"`
- **No configuration**: No need to declare or configure actions before use
- **Version management**: Standard semantic versioning through package versions
- **Dependency handling**: Python's pip handles all dependencies automatically

#### Ecosystem Growth
- **Organic discovery**: New actions become available automatically
- **Community contributions**: Easy for community to create and share actions
- **Quality assurance**: Actions are regular Python packages with standard testing
- **Documentation**: Standard Python documentation tools apply

### For the Framework

#### Architectural Benefits
- **Reduced complexity**: No registry files, configuration, or plugin management code
- **Robustness**: Discovery failures don't break the system (graceful degradation)  
- **Performance**: Lazy loading and one-time discovery minimize overhead
- **Maintainability**: Less framework code means easier maintenance

#### Ecosystem Integration
- **Standard distribution**: Uses PyPI and standard Python packaging
- **Cross-platform**: Works wherever Python works
- **Version compatibility**: Standard semantic versioning for compatibility management
- **Testing integration**: Actions can be tested with standard Python testing tools

## Auto-Discovery Implementation Patterns

### Cross-Language Bridges
Actions can bridge to R, Java, and other languages:

```python
# causaliq_bnlearn/__init__.py
from causaliq_workflow.action import BaseActionProvider
import rpy2.robjects as ro

class ActionProvider(BaseActionProvider):
    name = "causaliq-bnlearn"
    
    def __init__(self):
        # Initialize R environment once
        ro.r('library(bnlearn)')
        
    def run(self, inputs):
        # Bridge to R bnlearn package
        algorithm = inputs['algorithm']  # 'pc', 'gs', 'iamb', etc.
        ro.globalenv['data'] = inputs['data']
        ro.r(f'result <- {algorithm}(data)')
        return {"graph": self._convert_to_networkx(ro.r('result'))}
```

### Algorithm Collections
Single packages can provide multiple related algorithms:

```python  
# causaliq_constraint_based/__init__.py
class ActionProvider(BaseActionProvider):
    name = "causaliq-constraint-based"
    
    def run(self, inputs):
        algorithm = inputs['algorithm']
        
        if algorithm == 'pc':
            return self._run_pc(inputs)
        elif algorithm == 'fci':
            return self._run_fci(inputs)
        elif algorithm == 'cfci':
            return self._run_cfci(inputs)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
```

This auto-discovery architecture creates a vibrant, extensible ecosystem where actions can be developed, shared, and used with minimal friction while maintaining the robustness and reliability needed for scientific workflows.