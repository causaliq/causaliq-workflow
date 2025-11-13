# CausalIQ Pipeline - Technical Architecture

## System Overview

The causaliq-pipeline serves as the orchestration layer within the [CausalIQ ecosystem](https://github.com/causaliq/causaliq), coordinating causal discovery experiments through **GitHub Actions-inspired YAML workflows**. This architecture models causal discovery experiments as familiar CI/CD workflows, providing unprecedented flexibility while leveraging proven workflow patterns.

## Current Implementation Status

### ✅ Implemented Components (v0.1.0)

1. **Action Framework** (`causaliq_pipeline.action`)
   - Abstract base class for workflow actions
   - Type-safe input/output specifications
   - Comprehensive error handling with `ActionExecutionError` and `ActionValidationError`
   - 100% test coverage with unit and functional tests

2. **Schema Validation** (`causaliq_pipeline.schema`)
   - JSON Schema-based workflow validation
   - Support for GitHub Actions-style syntax
   - Matrix variables, with parameters, data_root/output_root validation
   - Comprehensive error reporting with schema path context

3. **Dummy Structure Learner Action** (`causaliq_pipeline.actions.dummy_structure_learner`)
   - Reference implementation demonstrating action framework
   - GraphML output format for causal graph representation
   - Matrix variable support (dataset, algorithm parameters)
   - Real filesystem operations with proper path construction

4. **Workflow Schema** (`causaliq_pipeline.schemas.causaliq-workflow.json`)
   - GitHub Actions-inspired syntax with causal discovery extensions
   - Matrix strategy support for parameterized experiments
   - Path construction with `data_root`, `output_root`, and `id` fields
   - Action parameters via `with` blocks

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

### 1. CI Workflow Engine (`causaliq_pipeline.workflow`)

```python
class CIWorkflowEngine:
    """Execute GitHub Actions-style workflows for causal discovery."""
    
    def parse_workflow(self, workflow_yaml: str) -> WorkflowDefinition:
        """Parse CI-style YAML using GitHub Actions schema."""
        
    def expand_matrix_strategy(self, strategy: MatrixStrategy) -> List[JobDefinition]:
        """Convert GitHub Actions matrix strategy to individual experiment jobs."""
        
    def execute_workflow(self, workflow: WorkflowDefinition) -> WorkflowResult:
        """Execute workflow with DASK task graph coordination."""
```

### 2. Package-Level Algorithm Registry (`causaliq_pipeline.algorithms`)

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

### 3. Action-Based Component Library (`causaliq_pipeline.actions`)

```python
class ActionRegistry:
    """Manage reusable workflow actions."""
    
    def register_action(self, name: str, version: str, action: Action) -> None:
        """Register versioned action: load-network@v1."""
        
    def execute_action(self, action_ref: str, inputs: Dict) -> ActionResult:
        """Execute action with input validation and output handling."""

class LoadNetworkAction(Action):
    """Action: load-network@v1 - Load causal network dataset."""
    
class CausalDiscoveryAction(Action):
    """Action: causal-discovery@v1 - Run causal discovery algorithm."""
    
class EvaluateGraphAction(Action):
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
- **causaliq-llm**: LLM integration via action-based architecture
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