# CausalIQ Workflow - Technical Architecture

## Architectural Vision: Configuration-Free Research Reproducibility Platform

### Core Architecture Principles

CausalIQ Workflow is designed as a **zero-configuration workflow orchestration
engine** that enables reproducible causal discovery research through:

1. **Entry Point-Based Action Discovery**: Actions are automatically discovered
   via Python entry points - no configuration files required
2. **Lazy Loading**: Action classes are loaded on first use, avoiding circular
   import issues
3. **Sequential Steps with Matrix Expansion**: Simple, predictable workflow
   execution with powerful parameterisation
4. **Conservative Execution**: Actions skip work if outputs already exist,
   enabling safe workflow restart and efficient re-runs
5. **Mode-Based Operation**: `--mode=dry-run|run|compare` provides validation,
   execution, and functional testing capabilities
6. **Plugin Architecture**: Third-party packages can register actions via
   entry points. Results are passed between packages using open standard
   formats e.g. JSON and .graphml
7. **Implicit Parameter Passing**: CLI parameters flow through workflows
   without formal definitions
8. **Action-Level Validation**: Each action validates its own inputs
   (integrated with dry-run capability)
9. **Workflow Composition**: Workflows can call other workflows via `cqflow`
   commands, enabling complex research workflows
10. **Workflow Cache Storage**: Results stored in SQLite-based Workflow Caches
    with matrix values as keys, enabling compact storage and fast lookup

### Entry Point-Based Auto-Discovery

**How Action Discovery Works**: When a workflow runs, the system discovers
actions through Python entry points. Packages register their actions in
`pyproject.toml`:

```toml
[project.entry-points."causaliq.actions"]
my-action = "my_package:ActionProvider"
```

Actions are discovered at startup (metadata only) and loaded lazily on first
use. This avoids circular imports since action packages depend on
`causaliq-workflow`.

### Research Reproducibility Pattern

**Paper Reproduction** = Workflow-of-Workflows where:
- **Top-level workflow** defines paper reproduction strategy
- **Component workflows** handle specific analyses (structure learning,
  visualisation, etc.)
- **causaliq-papers** processes workflow dependencies to generate targeted
  execution plans
- **causaliq-workflow** executes the optimised workflow graph

### Example: Simplified Workflow Architecture

```yaml
# paper-reproduction.yml (top-level workflow)
id: "peters2023causal-reproduction"
matrix:
  model: ["asia", "cancer"]
  algorithm: ["pc", "ges", "fci"]

# Workflow Cache stores all results - matrix values used as cache keys
workflow_cache: "results/{{id}}_cache.db"

steps:
  - name: "Structure Learning"
    uses: "causaliq-discovery"
    with:
      algorithm: "{{algorithm}}"
      model: "models/{{model}}/{{model}}.json"
      # No output path needed - results written to workflow_cache
      # Cache key derived from matrix: {network: "asia", algorithm: "pc"}

  - name: "Analysis"
    uses: "causaliq-analysis"
    with:
      operation: "evaluate-graph"
      # Graph retrieved from workflow_cache using matrix key

  - name: "Generate Figures"
    uses: "causaliq-visualisation"
    with:
      output: "results/{{id}}/figures"  # Figures still go to filesystem
```

### Conservative Execution & Mode Control

```yaml
# CLI execution modes
cqflow workflow.yml --mode=dry-run    # Default: validate and preview
cqflow workflow.yml --mode=run        # Execute workflow (skip if outputs exist)
cqflow workflow.yml --mode=compare    # Re-execute and compare with existing
```

### Action Intelligence & Efficiency

```python
# Actions support robust execution patterns with validation
action.run(inputs, dry_run=True)    # (a) Validate and preview execution
action.run(inputs, force=False)     # (b) Skip if output exists (conservative)
action.compare(inputs)              # (c) Regenerate and compare with filesystem

# Implicit parameter passing - no formal definitions needed
class StructureLearnerAction(BaseActionProvider):
    def run(self, inputs, matrix_job=None, dry_run=False, **kwargs):
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
- Checks if the module has an 'ActionProvider' attribute
- Verifies that it's a subclass of `causaliq_workflow.action.BaseActionProvider`
- Registers the action using the module name as the action identifier
- Builds a runtime lookup table: `{action_name: ActionProvider_class}`

#### 4. **Workflow Resolution**
When a workflow step specifies `uses: "my-custom-action"`:
- The registry looks up "my-custom-action" in the registered actions
- Instantiates the corresponding ActionProvider class
- Passes workflow parameters to the action's `run()` method

### Zero-Configuration Plugin Pattern

#### Creating a New Action Package
Developers create action packages by following a simple convention:

**Step 1: Package Structure**
```
my-custom-action/
├── pyproject.toml           # Standard Python package config
├── my_custom_action/        # Package directory  
│   └── __init__.py         # Must export 'ActionProvider' class
└── README.md
```

**Step 2: Action Implementation**
```python
# my_custom_action/__init__.py
from causaliq_workflow.action import BaseActionProvider

class ActionProvider(BaseActionProvider):  # Must be named 'ActionProvider'
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
- **Namespace safety**: 'ActionProvider' avoids conflicts with generic 'Action' classes in other packages
- **Version management**: Standard semantic versioning through package versions

## Workflow Caches

Workflow caches are filesystem objects which store results from workflow actions. They are SQLite-based with matrix values as keys, enabling compact storage and fast lookup.

Workflow actions typically write their outputs as **entries** in workflow caches. Each entry consists of:

 - metadata describing the action, for example, the `algorithm` used in a structure learning action, or the `llm_model` used in an LLM graph generate action. The JSON is tokenised when stored in the cache for compactness.
 - optionally, the entry may contain one or more data objects, for example, a graph produced by structure learning or generated by an LLM. The objects in an LLM entry are listed in a "manifest" section of the metadata and specify the ActionProvider used to create each data object, e.g. "causaliq-discovery" and the data object type, e.g. "graph". 
 
DataProvider actions check if their output is already present in the workflow cache and if so do not re-generate the output. This provides the basis for the conservative execution and reproducibility that CausalIQ Workfows offer.

Workflow caches often contain the results from a large series of experiments - for example, structure learning over a range of models (networks), algorithms and sample sizes. They may therefore contain tens of thousands of entries or more.

Workflow actions can read entries from workflow caches too.
Thus, they provide the mechanism for workflow actions to provide their output as the input to other actions, a typical example is that a `causaliq-discovery` action might write an entry with a learned graph object, and then a subsequent `causaliq-analysis` action might read that graph object and evaluate its structural accuracy, adding, for example the F1 value to the entry's metadata.

The design focus for workflow caches is speed and compactness, and because of this, their contents are not human readable. However, given that transparency is another goal of the CausalIQ ecosystem, CausalIQ ActionProviders are required to implement two special methods:

 - `serialise(data_type, data)` which converts internal data objects to open-standard format strings such as GraphML.
 - `deserialise(data_type, content)` which converts open-standard format strings back to internal data objects.

The `causaliq-workflow` CLI provides an `export_cache` command which exports the whole contents of a workflow cache to a directory structure of standard-format files which are human-readable and processable by third party tools. It is this open-standards export of the workflow cache that would be stored on Zenodo for example. Similarly, an `import_cache` command provides the capability to convert these open-standard format files back into workflow caches, ready to participate in CausalIQ workflows.

Importantly, the `serialise` and `deserialise` methods work with string content rather than files, which provides the means by which ActionProviders can read workflow cache entries *without understanding the compressed internal format of the entry cache*. Third-parties writing actions therefore need only be able to process standards-based formats as inputs, and need not, for example, use any CausalIQ code, as long as they implement the BaseActionProvider interface.

The `causaliq-workflow` package itself is responsible for:

 - converting internal format cache entries to and from open-standards format which ActionProviders consume and produce. It does this by looking at the entry's metadata, and using the appropriate packages and data object types to convert the internal format to the open-standards that any ActionProvider can consume.
 - managing conservative execution

### Serialise and Deserialise Method Specifications

ActionProviders that produce data objects (e.g., graphs) must implement `serialise()` and `deserialise()` methods. These methods convert between internal data objects and open-standard format strings. The format used is determined by the provider implementation (e.g., GraphML for graphs).

#### serialise Method

Converts internal data objects to open-standard format strings.

**Parameters:**
- `data_type` (str): Type of data object (e.g., "graph")
- `data` (Any): The data object to serialise

**Returns:**
- `str`: Open-standard format string representation

**Example:**
```python
from causaliq_knowledge import ActionProvider

provider = ActionProvider()
graph = provider.run("generate_graph", params, mode="run")["graph"]

# Serialise to GraphML string
graphml_str = provider.serialise("graph", graph)
```

#### deserialise Method

Converts open-standard format strings to internal data objects.

**Parameters:**
- `data_type` (str): Type of data object (e.g., "graph")
- `content` (str): Open-standard format string

**Returns:**
- The deserialised data object

**Example:**
```python
# Read GraphML from file
with open("graph.graphml") as f:
    graphml_content = f.read()

# Deserialise to internal object
graph = provider.deserialise("graph", graphml_content)
```

#### In-Memory Data Flow

When `causaliq-workflow` needs to pass data between actions from different providers, it uses these methods:

```python
# Producer action writes graph to cache
# Consumer action from different package needs the graph...

# 1. Workflow retrieves graph object from producer action result
graph = producer_result["graph"]

# 2. Serialise to open-standard format string
graph_str = producer_provider.serialise("graph", graph)

# 3. Consumer deserialises to its internal format (if different)
consumer_graph = consumer_provider.deserialise("graph", graph_str)

# 4. Consumer processes the graph
consumer_provider.run(
    action="analyse",
    parameters={"graph": consumer_graph, ...}
)
```

This architecture ensures:
- **Decoupling**: Consumers don't need producer's internal format knowledge
- **Open standards**: All data exchanged as JSON, GraphML, etc.
- **Third-party friendly**: External packages only implement standard I/O


## Core Architectural Decisions


### GitHub Actions Foundation

The architecture is built on GitHub Actions workflow patterns, adapted for causal discovery:

```yaml
name: "Causal Discovery Experiment"
id: "asia-comparison-001"
data_root: "data"
workflow_cache: "results/{{id}}_cache.db"  # All results stored here

matrix:
  dataset: ["asia", "cancer"]  
  algorithm: ["pc", "ges"]

steps:
  - name: "Structure Learning"
    uses: "dummy-structure-learner"
    with:
      alpha: 0.05
      max_iter: 1000
      # Results cached with key: {dataset, algorithm}
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


## Integration with CausalIQ Ecosystem

### Package Coordination
- **causaliq-discovery**: Core algorithms integrated as package plugins
- **causaliq-knowledge**: Knowledge provision via action-based architecture
- **causaliq-analysis**: Statistical analysis actions and workflow post-processing
- **causaliq-research**: Configuration and result storage with CI workflow metadata

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