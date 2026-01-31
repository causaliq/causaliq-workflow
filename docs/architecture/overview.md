# CausalIQ Workflow - Technical Architecture

## Architectural Vision: Configuration-Free Research Reproducibility Platform

### Core Architecture Principles

CausalIQ Workflow is designed as a **zero-configuration workflow orchestration engine** that enables reproducible causal discovery research through:

1. **Auto-Discovery Action System**: Actions are automatically discovered from installed Python packages - no configuration files required
2. **Sequential Steps with Matrix Expansion**: Simple, predictable workflow execution with powerful parameterization
3. **Conservative Execution**: Actions skip work if outputs already exist, enabling safe workflow restart and efficient re-runs
4. **Mode-Based Operation**: `--mode=dry-run|run|compare` provides validation, execution, and functional testing capabilities
5. **Convention-Based Plugin Pattern**: Actions follow simple naming conventions for automatic registration
6. **Implicit Parameter Passing**: CLI parameters flow through workflows without formal definitions
7. **Action-Level Validation**: Each action validates its own inputs (integrated with dry-run capability)
8. **Workflow Composition**: Workflows can call other workflows via `cqflow` commands, enabling complex research workflows
9. **Standardized Output**: Fixed filenames by type (`graph.xml`, `metadata.json`, `trace.csv`) with hierarchical organization

### Zero-Configuration Auto-Discovery

**How Action Discovery Works**: When a workflow runs, the system automatically finds and registers all available actions through Python's module introspection - no registry files, no configuration needed. Simply install a package that exports an `Action` class and it becomes available in workflows.

### Research Reproducibility Pattern

**Paper Reproduction** = Workflow-of-Workflows where:
- **Top-level workflow** defines paper reproduction strategy
- **Component workflows** handle specific analyses (structure learning, visualization, etc.)
- **causaliq-papers** processes workflow dependencies to generate targeted execution plans
- **causaliq-workflow** executes the optimized workflow graph

### Example: Simplified Workflow Architecture

```yaml
# paper-reproduction.yml (top-level workflow)
id: "peters2023causal-reproduction"
matrix:
  network: ["asia", "cancer"]
  algorithm: ["pc", "ges", "fci"]

steps:
  - name: "Structure Learning"
    uses: "causaliq-discovery"
    with:
      algorithm: "{{algorithm}}"
      dataset: "/data/{{network}}"
      output: "/results/{{id}}/{{algorithm}}/{{network}}"
      
  - name: "Analysis"
    uses: "causaliq-analysis"
    with:
      operation: "evaluate-graph"
      graph: "/results/{{id}}/{{algorithm}}/{{network}}"
      
  - name: "Generate Figures"
    uses: "causaliq-visualization"
    with:
      input: "/results/{{id}}/{{algorithm}}/{{network}}"
      output: "/results/{{id}}/figures"

# Workflow composition via CLI calls
steps:
  - name: "Run Structure Learning"
    run: |
      cqflow structure-learning.yml \
        --network="{{network}}" --algorithm="{{algorithm}}"
```

### Conservative Execution & Mode Control

```yaml
# CLI execution modes
cqflow workflow.yml --mode=dry-run    # Default: validate and preview (no execution)
cqflow workflow.yml --mode=run        # Execute workflow (skip if outputs exist)
cqflow workflow.yml --mode=compare    # Re-execute and compare with existing outputs
```

### Action Intelligence & Efficiency

```python
# Actions support robust execution patterns with validation
action.run(inputs, dry_run=True)    # (a) Validate and preview execution
action.run(inputs, force=False)     # (b) Skip if output file already exists (conservative)
action.compare(inputs)              # (c) Regenerate and compare with filesystem

# Implicit parameter passing - no formal definitions needed
class StructureLearnerAction(CausalIQAction):
    def run(self, inputs, matrix_job, dry_run=False):
        # Action handles its own validation
        self.validate_inputs(inputs)
        
        # Conservative execution: skip if outputs exist
        if not inputs.force and self.outputs_exist(inputs):
            return self.load_existing_outputs(inputs)
            
        if dry_run:
            return self.simulate_execution(inputs)
        return self.learn_structure(inputs)
```

## System Overview

The causaliq-workflow serves as the orchestration layer within the [CausalIQ ecosystem](https://github.com/causaliq/causaliq), coordinating causal discovery experiments through **GitHub Actions-inspired YAML workflows**. This architecture models causal discovery experiments as familiar CI/CD workflows, providing unprecedented flexibility while leveraging proven workflow patterns.

## Current Implementation Status

### ✅ Implemented Components (v0.1.0)

1. **Auto-Discovery Action Registry** (`causaliq_workflow.registry`)
   - **Zero-configuration action discovery**: Automatically finds all installed action packages
   - **Convention-based registration**: Packages export 'CausalIQAction' class for automatic registration  
   - **Python module introspection**: Uses `pkgutil.iter_modules()` for discovery without config files
   - **Runtime action lookup**: Dynamic resolution of action names to classes during workflow execution
   - **Namespace isolation**: Each action package maintains its own namespace and dependencies

2. **Action Framework** (`causaliq_workflow.action`)
   - Abstract base class `CausalIQAction` for workflow actions
   - Type-safe input/output specifications
   - Comprehensive error handling with `ActionExecutionError` and `ActionValidationError`
   - 100% test coverage with unit and functional tests

3. **Schema Validation** (`causaliq_workflow.schema`)
   - JSON Schema-based workflow validation
   - Support for GitHub Actions-style syntax
   - Matrix variables, with parameters, data_root/output_root validation
   - Comprehensive error reporting with schema path context

4. **Workflow Execution Engine** (`causaliq_workflow.workflow`)
   - `WorkflowExecutor` class for parsing YAML workflows
   - Matrix expansion with cartesian product generation
   - Path construction from matrix variables and workflow configuration
   - Integration with auto-discovery action registry

5. **Example Action Package** (`tests/functional/fixtures/test_action`)
   - Reference implementation demonstrating auto-discovery pattern
   - GraphML output format for causal graph representation
   - Matrix variable support (dataset, algorithm parameters)
   - Real filesystem operations with proper path construction

6. **Workflow Schema** (`causaliq_workflow.schemas.causaliq-workflow.json`)
   - GitHub Actions-inspired syntax with causal discovery extensions
   - Matrix strategy support for parameterized experiments
   - Path construction with `data_root`, `output_root`, and `id` fields
   - Action parameters via `with` blocks

## Auto-Discovery Architecture: How It Works

### The Discovery Process: Step-by-Step

#### 1. **Workflow Execution Begins**
When you run `causaliq-workflow my-experiment.yml`, the system:
- Creates a new `ActionRegistry` instance
- Triggers the automatic discovery process
- Scans all installed Python packages for actions

#### 2. **Package Scanning Phase**
The registry uses Python's module introspection to:
- Iterate through all importable modules using `pkgutil.iter_modules()`
- Attempt to import each module safely (catching import errors)
- Look for modules that export an 'Action' class

#### 3. **Convention-Based Registration**
For each discovered module, the system:
- Checks if the module has a 'CausalIQAction' attribute
- Verifies that it's a subclass of `causaliq_workflow.action.CausalIQAction`
- Registers the action using the module name as the action identifier
- Builds a runtime lookup table: `{action_name: CausalIQAction_class}`

#### 4. **Workflow Resolution**
When a workflow step specifies `uses: "my-custom-action"`:
- The registry looks up "my-custom-action" in the registered actions
- Instantiates the corresponding CausalIQAction class
- Passes workflow parameters to the action's `run()` method

### Zero-Configuration Plugin Pattern

#### Creating a New Action Package
Developers create action packages by following a simple convention:

**Step 1: Package Structure**
```
my-custom-action/
├── pyproject.toml           # Standard Python package config
├── my_custom_action/        # Package directory  
│   └── __init__.py         # Must export 'CausalIQAction' class
└── README.md
```

**Step 2: Action Implementation**
```python
# my_custom_action/__init__.py
from causaliq_workflow.action import CausalIQAction

class CausalIQAction(CausalIQAction):  # Must be named 'CausalIQAction'
    name = "my-custom-action"
    description = "Performs custom analysis"
    
    def run(self, inputs):
        # Action logic here
        return {"result": "analysis complete"}
```

**Step 3: Installation & Discovery**
```bash
pip install my-custom-action    # Install the package
causaliq-workflow my-workflow.yml  # Action automatically discovered
```

#### Why This Works
- **No configuration files**: No registry.json, no plugin.xml, no setup scripts
- **Standard Python packaging**: Uses familiar pyproject.toml and pip install
- **Immediate availability**: Actions become available as soon as the package is installed
- **Namespace safety**: 'CausalIQAction' avoids conflicts with generic 'Action' classes in other packages
- **Version management**: Standard semantic versioning through package versions

## Core Architectural Decisions


### GitHub Actions Foundation

The architecture is built on GitHub Actions workflow patterns, adapted for causal discovery:

```yaml
name: "Causal Discovery Experiment"
id: "asia-comparison-001"
data_root: "/data"
output_root: "/results"

matrix:
  dataset: ["asia", "cancer"]  
  algorithm: ["pc", "ges"]

steps:
  - name: "Structure Learning"
    uses: "dummy-structure-learner"
    with:
      alpha: 0.05
      max_iter: 1000
```

### Action-Based Components

Actions are reusable workflow components with semantic versioning:

```python
class Action(ABC):
    """Abstract base class for all workflow actions."""
    
    name: str                    # Action identifier
    version: str                 # Semantic version
    description: str             # Human description  
    inputs: Dict[str, ActionInput]   # Type-safe inputs
    outputs: Dict[str, str]      # Output descriptions
    
    @abstractmethod
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the action with given inputs."""
```



## Core Architecture Components

### 1. Workflow Execution Engine (`causaliq_workflow.workflow`)

```python
class WorkflowExecutor:
    """Parse and execute GitHub Actions-style workflows with matrix expansion."""
    
    def parse_workflow(self, workflow_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse workflow YAML file with validation and template variable validation."""
        
    def expand_matrix(self, matrix: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """Expand matrix variables into individual job configurations."""
        
    def _extract_template_variables(self, text: Any) -> Set[str]:
        """Extract {{variable}} patterns from strings using regex."""
        
    def _validate_template_variables(self, variables: Set[str], context: Set[str]) -> None:
        """Validate template variables against available context."""
        
    def _collect_template_variables(self, obj: Any) -> Set[str]:
        """Recursively collect template variables from workflow configuration."""
```

**Current Implementation Status**: ✅ **Phase 1 Complete**
- Parse and validate YAML workflow files
- Matrix expansion with cartesian product generation  
- Template variable validation with context checking
- Path construction from matrix variables
- 100% test coverage with comprehensive error handling

**Next Phase**: Step execution, environment management, conditional execution

### 2. Package-Level Algorithm Registry (`causaliq_workflow.algorithms`)

```python
class AlgorithmRegistry:
    """Manage package-level algorithm plugins."""
    
    def discover_packages(self) -> List[AlgorithmPackage]:
        """Auto-discover bnlearn, Tetrad, causal-learn packages."""
        
    def execute_algorithm(self, package: str, algorithm: str, 
                         data: Dataset, params: Dict) -> Result:
        """Execute algorithm with cross-language bridge handling."""

class BnlearnPackage:
    """R bnlearn package integration via rpy2."""
    
class TetradPackage:
    """Java Tetrad package integration via py4j."""
    
class CausalLearnPackage:  
    """Python causal-learn direct integration."""
```

### 3. Action-Based Component Library (`causaliq_workflow.actions`)

```python
class ActionRegistry:
    """Manage reusable workflow actions."""
    
    def register_action(self, name: str, version: str, action: CausalIQAction) -> None:
        """Register versioned action: load-network@v1."""
        
    def execute_action(self, action_ref: str, inputs: Dict) -> ActionResult:
        """Execute action with input validation and output handling."""

class LoadNetworkAction(CausalIQAction):
    """Action: load-network@v1 - Load causal network dataset."""
    
class CausalDiscoveryAction(CausalIQAction):
    """Action: causal-discovery@v1 - Run causal discovery algorithm."""
    
class EvaluateGraphAction(CausalIQAction):
    """Action: evaluate-graph@v1 - Evaluate learned graph against true graph."""
```

## CI Workflow Syntax Examples

### Basic Matrix Workflow
```yaml
name: "Algorithm Comparison"

strategy:
  matrix:
    algorithm: ["PC", "GES", "LINGAM"]
    network: ["asia", "sachs", "alarm"]
    sample_size: [100, 500, 1000]
  
  exclude:
    - algorithm: "LINGAM"
      network: "alarm"  # LINGAM doesn't work with discrete data

steps:
  - name: "Load Network Data"
    uses: "load-network@v1"
    with:
      network_name: "${{ matrix.network }}"
      sample_size: "${{ matrix.sample_size }}"
    
  - name: "Run Causal Discovery"
    uses: "causal-discovery@v1"
    with:
      algorithm: "${{ matrix.algorithm }}"
      package: "auto-detect"
      data: "${{ steps.load_network.outputs.dataset }}"
        
  - name: "Evaluate Results"
    uses: "evaluate-graph@v1"
    with:
      learned_graph: "${{ steps.causal_discovery.outputs.graph }}"
      true_graph: "${{ steps.load_network.outputs.true_graph }}"
```

### Conditional Execution
```yaml
steps:
  - name: "Run PC Algorithm"
    uses: "causal-discovery@v1"
    with:
      algorithm: "pc"
      package: "bnlearn"
  
  - name: "Run GES Algorithm"
    if: "${{ matrix.sample_size >= 500 }}"  # Only for larger samples
    uses: "causal-discovery@v1"
    with:
      algorithm: "ges"
      package: "causal-learn"
```

## DASK Integration Architecture

### CI Workflow → DASK Task Graph Conversion

```python
class DaskTaskGraphBuilder:
    """Convert CI workflows into DASK task graphs."""
    
    def build_workflow_graph(self, workflow: WorkflowDefinition) -> Dict:
        """Convert CI workflow steps into DASK computation graph."""
        
    def handle_matrix_strategy(self, strategy: MatrixStrategy) -> List[TaskDefinition]:
        """Convert matrix strategy into parallel DASK tasks."""
        
    def manage_cross_language_bridges(self, action: Action) -> TaskWrapper:
        """Manage R/Java bridges with proper lifecycle and cleanup."""
```

### Resource Management

CI workflow features map to DASK execution controls:

- `max_parallel`: DASK worker pool size limitation
- `timeout_minutes`: Per-task timeout enforcement
- `runs_on`: DASK cluster specification (local/remote)
- `fail_fast`: Task failure propagation strategy

## Cross-Language Integration

### R bnlearn Integration
- **Bridge**: rpy2 with automatic data conversion
- **Lifecycle**: Package-level R session management
- **Error Handling**: Graceful R exception translation

### Java Tetrad Integration  
- **Bridge**: py4j with JVM lifecycle management
- **Data Conversion**: Pandas ↔ Tetrad data structures
- **Resource Management**: Proper JVM cleanup

### Python causal-learn Integration
- **Direct Integration**: Native Python execution
- **Optimised Paths**: No cross-language overhead
- **Data Handling**: Efficient NumPy/Pandas operations

## Template Processing

### GitHub Actions-Style Variables

```yaml
env:
  RANDOM_SEED: 42
  DATA_DIR: "${{ github.workspace }}/data"

steps:
  - name: "Process ${{ matrix.network }} with ${{ matrix.algorithm }}"
    with:
      output_path: "${{ env.DATA_DIR }}/results/${{ matrix.network }}_${{ matrix.algorithm }}.json"
```

### Jinja2 Implementation
- **Syntax**: `${{ variable.property }}` exactly matching GitHub Actions
- **Context**: Matrix variables, environment variables, step outputs
- **Security**: Safe template processing with variable validation

## Integration with CausalIQ Ecosystem

### Package Coordination
- **causaliq-discovery**: Core algorithms integrated as package plugins
- **causaliq-knowledge**: Knowledge provision via action-based architecture
- **causaliq-analysis**: Statistical analysis actions and workflow post-processing
- **causaliq-experiments**: Configuration and result storage with CI workflow metadata

### Development Standards
- **GitHub Actions schema compliance**: Official JSON schema for validation
- **Action versioning**: Semantic versioning for all reusable actions
- **CausalIQ integration standards**: Plugin architecture, result standardisation
- **79-character line limit**: All code adheres to CausalIQ formatting standards
- **Type safety**: Full MyPy type checking with strict configuration

## Design Patterns

### YAML-First Configuration
- All workflow functionality expressible through YAML
- External workflow definitions without code changes
- Clear, actionable error messages for configuration issues

### Package-Level Plugin Architecture
- Dynamic discovery and registration of algorithm packages
- Cross-language bridge management at package level
- Preference resolution for algorithm conflicts

### Action-Based Composability
- Reusable, versioned workflow components
- Standardised input/output interfaces
- Community potential for shared actions

This architecture transforms causal discovery workflow definition from domain-specific patterns into familiar CI/CD workflows, dramatically reducing the learning curve while providing enterprise-grade features for research.