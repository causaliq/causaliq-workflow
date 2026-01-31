# CausalIQ Workflow - Example Workflows

!!! info "Feature Implementation Status"
    This documentation includes both **currently implemented** features and **planned features**. Planned features are marked with warning boxes. Currently implemented:
    
    - ✅ Workflow parsing and validation
    - ✅ Matrix expansion into job configurations
    - ✅ Template variable substitution (`{{variable}}`)
    - ✅ Action registry and discovery
    - ✅ Schema validation (strings, numbers, booleans in `with:` blocks)
    
    Planned features (not yet implemented):
    
    - ⏳ Array values in `with:` blocks
    - ⏳ Series-based workflows
    - ⏳ Resource configuration
    - ⏳ LLM integration
    - ⏳ Advanced randomization strategies

## Design Philosophy: Inspired by CI-Workflows

The CausalIQ Workflows are *inspired* by the concepts within 
Continuous Integration (CI) workflows. They provide a subset of the features 
provided by CI workflows and much of the functionality is simplified to ease
the job of specifying CausalIQ workflows.

Key concepts in CausalIQ workflows are:

  - Workflows are a series of one or more *sequential* **steps**.
  - Steps can be either an **action** or they can **run** shell commands.
  - actions execute typical causal inference and evaluation activities like structure 
  learning, graph evaluation, causal inference etc., and actions:
    - are implemented in other CausalIQ packages such as causaliq-discovery,        causaliq-analysis etc. as specified in the **uses:** keyword of the step;
    - take parameters values for the action - e.g., the algorithm to use - are specified using the **with:** keyword;
    - actions can be *implemented intelligently* to perform their work efficiently and in parallel.
  - a **matrix** concept allows the set of steps to be repeated over multiple
  combinations of values, for example over a set of networks, sample sizes and
  algorithms. This is particularly valuable for large scale comparative experiments.
  - workflows may be run from the command line interface (CLI) using commands like:

    ```shell
    cqflow example_workflow.yaml --model=child,property
    ```
      - CLI arguments can be used to override workflow and matrix parameters so
        that the same workflow can be easily reused;
      - the **run:** command can be used to run a workflow so that "workflows of
        workflows" are supported.

The CausalIQ Workflow CLI has a **--mode** argument which controls its overall behaviour as follows:

  - **--mode=run**: this actually executes the workflow. Note that, in this case
 the actions in the workflow are performed *conservatively* - if the outputs of
 actions are already present on the file system the action is *not repeated*. This
 therefore faciltates restarting the workflow if it has previously been interrupted.
  - **--mode=dry-run**: this is the default behaviour and reports what *would* be done if **--mode=run** were used, but does not perform the actual actions. In doing so,
  it has the valuable side-effect of checking that the workflow definitions are
  all valid.
  - **--mode=compare**: all actions in the workflow will be re-run regardless of whether the output is present on the filesystem or not. If the output is present on the filesystem, the newly-generated output will replace it, and any differences with the previous version reported. This mode is therefore a very powerful form of functional testing.  

## Example Workflows in Causal Discovery

### Unparameterised single-step workflows

The first simple example is a minimal workflow that asks a LLM to propose a causal network for covid

```yaml
# llm_covid.yaml
steps:
  - name: "Llama3 proposes a covid graph"
    uses: "causaliq-knowledge"
    with:
      action: "generate_graph"
      context: "models/covid/covid_llm_context.json"
      result: "results/covid.db"
```
This is a single-step workflow with a minimal set of values defined for the 
single step:

- **name** - each step must be given a neame which is hopefully meaningful
- **uses** - the step must define which CausalIQ package it uses

and then has a variable number of parameters following the **with:** statment that
defines the processing to be undertaken by the package through its *CausalIQAction* interface. In this example, these are:

- **action** - this parameter is always present and defines what particular action
the package is required to do
- **context** - defines a JSON file providing details of the problem domain and its variables which will serve as input to the LLM for this action
- **result** - defines a results (sql-lite) database where results will be placed

The same result could be achieved using the causaliq-knowledge CLI command directly,
but using this simple workflow avoids having to specify the model and result locations on
the command line by using the following command:

```shell
cqflow llm_covid.yaml  # cqflow is a synonym for causaliq-workflow
```

Using `.yaml` workflow files becomes increasingly convenenient as additional parameters
are specified, for example, as in the following example:


```yaml
# llm_covid.yaml
description: "Using gpt-4 to propose a causal graph using rich context"
root_dir: "c:/dev/causaliq/causaliq-research"

steps:
  - name: "GPT-4 proposes a covid graph"
    uses: "causaliq-knowledge"
    with:
      action: "generate_graph"
      llm: "openai/gpt-4o-mini"
      context_level: "rich"
      context: "models/covid/covid_llm_context.json"
      result: "results/covid.db"
```

Additional workflow-level parameters here are: 

- **description** - a human friendly description of the workflow
- **root_dir** - a base file location for all paths used in the workflow
(by default the current directory is used)

Additional parameters for the `generate_graph` step are:

- **llm** - explicit specification of LLM model to use instead of using the default LLM
- **context_level** - specify that a rich level of context is to be provided to the LLM

The next simple example runs the Tabu-Stable structure learning algorithm on 1000 synthetic rows from the Asia network. Specific parameters for structure learning are:

- **action** - specifices the structure learning action
- **algorithm** - the structure learning algorithm
- **sample_size** - how many rows of data to use
- **dataset** - file containing synthetically generated rows
- **debug** - is set true so that a detailed iteration-by-iteratuon analysis of
the learning process is included in the result
- **results** - the results database, where in this case an entry will be 
the learnt graph, an iteration trace, and structure learning metadata

```yaml
# tabu_asia.yaml
id: "tabu-stable_asia_1k"
description: "Tabu-stable learning Asia from 1K data with full trace"

steps:
  - name: "Learn Structure"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      algorithm: "tabu-stable"
      sample_size: "1k"
      dataset: "models/asia/asia_10k.data.gz"
      debug: True
      results: "results/tabu_stable.db"
```

The example below **updates** the metadata about a learned graph to evaluate
structural accuracy and some inference scores for all graphs learnt by asia.

!!! warning "Planned Feature"
    Array values in `with:` blocks (e.g., `dag_structure: ["f1", "shd"]` and `score: ["bic", "bde"]`) shown in this example are planned features. The current schema only supports string, number, and boolean values in action parameters.

```yaml
# evaluate_graph.yaml
description: "Evaluate structure and score of learned graphs"
model: "asia"

steps:
  - name: "Evaluate Graph"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      model: {{model}}
      true_graph: "models/{{model}}/{{model}}.xdsl"
      dag_structure: ["f1",shd"]
      cpdag_structure: "shd"
      score: ["bic", "bde"]
      results: "results/tabu_stable.db"
```


Another simple workflow might be to download resources from Zenodo. This would download all the resources associated with my PhD thesis and
unzip in the specified output folder.

```yaml
# download_paper.yaml
description: "Download assets for PhD Thesis"

steps:
  - name: "Download paper"
    uses: "causaliq-papers"
    with:
      operation: "download"
      doi: "10.5072/zenodo.338579"
      output: "/papers/2025KitsonThesis"
``` 

### Parameterised Structure Learning Example

We can make the simple learning example more general by adding workflow-level
variables to parameterise the workflow. In this example, the sample_size parameter has a
default value of 1000 if not specified on the command line, whereas the None
value for model (i.e. network) indicates that this must be specified on the command line. 
Note how the model and sample_size
parameters are used in the dataset and output action parameters so
that the correct input file and output folder are used.

```yaml
# tabu_learning.yaml
description: "Parameterised Tabu-stable learning"
sample_size: "1K"
model: None

steps:
  - name: "Learn Structure"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      algorithm: "tabu-stable"
      max_time: 10
      sample_size: {{sample_size}}
      dataset: "/models/{{model}}/{{network}}_10k.data.gz"
      output: "/results/tabu_stable.db
```
We can now run Tabu-Stable structure learning for any network and sample size using commands like:

```shell
cqflow tabu_learning.yaml --network=child --sample_size=500
``` 

### Multiple Step Examples


We could enhance this by adding a step before structure learning where an LLM provides an initial graph. In this example, the dataset is provided so that the
LLM has access to the values, and there is also some additional domain context provided in a json file. This could generate a graph.xml in the output folder
and probably also some metadata and/or history of the prompts and responses 
made to the LLM. Note that, this LLM generated graph would then be available
to be re-used in other experiments, and the prompts/response trail provides the
means to exactly replicate this result.

```yaml
# tabu_llm_learning.yaml
description: "Tabu-stable learning Asia with LLM initialisation"
sample_size: "1K"
model: None

steps:
  - name: "LLM Graph Initialisation"
    uses: "causaliq-knowledge"
    with:
      action: "generate_graph"
      context: "models/{{model}}/{{model}}_llm_context.json"
      result: "results/llm_graphs.db"

  - name: "Learn Structure"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      initial_graph: "results/llm_graphs.db"
      # etc ....
```

### Matrix Strategy Workflow

In many cases we will wish to run comparative experiments with a different result for each combinations of algorithm, network, and sample size and randomisation. Note how we structure the output folder path so that we ensure the result for each individual experiment is placed in its own folder. We also use an "id" workflow variablesto keep these results separate from those of other workflows.

Internally, the action - in this case causal-discovery - may be implemented intelligently to maximise efficiency. For example, in this case, it may read
the maximum number of rows from the filesystem dataset just once, and then adjust the effective sample size and randomisation internally for each individual experiment.

!!! warning "Planned Feature"
    The `randomise` workflow-level variable and array values in `with:` blocks (e.g., `randomise: {{randomise}}`) shown in this example are planned features. The current schema only supports string, number, and boolean values in action parameters.

```yaml
# matrix_experiment.yaml
description: "Algorithm stability comparison"
randomise: ["variable_order", "variable_name"]

matrix:
  model: ["asia", "cancer"]
  algorithm: ["pc", "ges"]
  sample_size: ["100", "1K"]
  seed: [1, 25]

steps:
  - name: "Structure Learning"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      algorithm: "{{algorithm}}"
      sample_size: "{{sample_size}}"
      dataset: "models/{{model}}/{{model}}_10k.data.gz"
      randomise: {{randomise}}
      seed: {{seed}}
      output: "results/algo_stability.db"
```

### Workflow of workflows

The ability of one workflow to call other parameterised workflows facilitates the creation and testing of complex CausalIQ workflows, for instance to run
all the experiments, analysis and asset generation for a research paper or thesis. CausalIQ Papers makes use of this to provide reproducibility of CausalIQ published papers.

The example below shows a simple top level workflow which might reproduce the experiments and analysis behind a thesis. The lower level workflows such as create_chapter_4.yaml might then call other workflows to perform the structure learning, result analysis and asset generation for Chapter 4.

```yaml
# reproduce_thesis.yaml

id: "Kitson2025thesis"

matrix:
  chapter: [4, 5, 6]

steps:
  name: "Create chapter {{chapter}}"
  run: "cqflow create_chapter_{{chapter}}.yaml --id={{id}}
```

### Parallel Jobs

CI workflows provide a **jobs:** keyword which allows multiple sequences of steps to run in parallel. We are not planning to implement this at the moment, instead relying on actions to provde parallelism using DAK tasks. This keeps CausalIQ Workflow functionality simple and reflects the fact that structure learning steps involving many individual structure learning experiments can keep even very powerful machines busy.

## Template Variables

### Flexible Path Templating Pattern

Our implementation supports flexible path templating using matrix variables:

```yaml
# Template variables can be used in action parameters:
# {{id}} - workflow identifier
# {{network}} - current matrix value for network
# {{algorithm}} - current matrix value for algorithm  
# {{sample_size}} - current matrix value for sample size

# Example expansion for graphs using matrix above:
# Job 1: dataset="/experiments/data/asia.csv", result="/experiments/results/algo-comparison-001/pc/asia/100"
# Job 2: dataset="/experiments/data/asia.csv", result="/experiments/results/algo-comparison-001/pc/asia/1K"
# Job 3: dataset="/experiments/data/asia.csv", result="/experiments/results/algo-comparison-001/ges/graph_asia_0.01.xml"
# ... (8 total combinations)
```

### Template Variable Validation

The workflow executor automatically validates that all template variables (`{{variable}}`) used in action parameters are available from either:
- **Workflow properties**: `id`, `description` 
- **Matrix variables**: Variables defined in the `matrix` section

**Valid Template Usage:**
```yaml
id: "my-experiment-001"
matrix:
  dataset: ["asia", "cancer"]
  algorithm: ["pc", "ges"]
  
steps:
  - uses: "dummy-structure-learner"
    with:
      # These are all valid - variables exist in workflow context
      output: "/results/{{id}}/{{dataset}}_{{algorithm}}"
      description: "Running {{algorithm}} on {{dataset}}"
```

**Invalid Template Usage (Validation Error):**
```yaml
id: "my-experiment-001"
matrix:
  dataset: ["asia", "cancer"]
  
steps:
  - uses: "dummy-structure-learner"
    with:
      # This will cause a WorkflowExecutionError
      output: "/results/{{unknown_variable}}/{{missing_param}}"
```

**Error Message Example:**
```
WorkflowExecutionError: Unknown template variables: unknown_variable, missing_param
Available context: id, description, dataset
```

## Implemented Features

### ✅ Action Framework
- **Action Registration**: Actions defined as Python classes
- **Type Safety**: Input/output specifications with type hints
- **Error Handling**: Comprehensive ActionExecutionError and ActionValidationError
- **GraphML Output**: Standardized format for causal graphs

### ✅ Workflow Execution Engine
- **YAML Parsing**: Parse and validate GitHub Actions-style workflow files
- **Matrix Expansion**: Convert matrix variables into individual job configurations
- **Flexible Path Templating**: User-controlled path generation with {{}} template variables
- **Template Variable Validation**: Automatic validation of {{variable}} patterns against available context
- **Error Propagation**: Comprehensive error handling with WorkflowExecutionError

### ✅ Schema Validation
- **GitHub Actions Syntax**: Familiar workflow patterns
- **Matrix Variables**: Full support for parameterized experiments  
- **Flexible Action Parameters**: Template variables in action `with:` blocks
- **Action Parameters**: with blocks for action configuration

### ✅ Test Coverage
- **Functional Tests**: Real filesystem operations with tracked test data
- **Unit Tests**: Mocked dependencies for action logic testing
- **Schema Tests**: Comprehensive validation of all workflow features
- **100% Coverage**: Complete test coverage including edge cases

## Example Action Implementation

```python
class DummyStructureLearnerAction(CausalIQAction):
    """Reference action implementation."""
    
    name = "dummy-structure-learner"
    version = "1.0.0"
    
    inputs = {
        "data_path": ActionInput(
            name="data_path",
            description="Path to input CSV dataset (auto-constructed)",
            required=True,
            type_hint="str",
        ),
        "output_dir": ActionInput(
            name="output_dir", 
            description="Directory for output files (auto-constructed)",
            required=True,
            type_hint="str",
        ),
        "dataset": ActionInput(
            name="dataset",
            description="Dataset name from matrix",
            required=True,
            type_hint="str",
        ),
        "algorithm": ActionInput(
            name="algorithm",
            description="Algorithm name from matrix",
            required=True,
            type_hint="str",
        ),
    }
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Create GraphML output file."""
        # Implementation creates valid GraphML file
        # Returns graph_path, node_count, edge_count
```

## Current Implementation: WorkflowExecutor

### WorkflowExecutor Implementation (Phase 1 Complete)

```python
from causaliq_workflow import WorkflowExecutor

# Parse workflow and expand matrix
executor = WorkflowExecutor()
workflow = executor.parse_workflow("experiment.yml")

# Matrix expansion example
matrix = {"algorithm": ["pc", "ges"], "dataset": ["asia", "cancer"], "alpha": [0.01, 0.05]}
jobs = executor.expand_matrix(matrix)  # Returns 8 job configurations

# Example workflow with flexible paths
workflow_example = {
    "id": "experiment-001",
    "description": "Flexible causal discovery experiment",
    "matrix": matrix,
    "steps": [{
        "name": "Structure Learning",
        "uses": "dummy-structure-learner", 
        "with": {
            "dataset": "/experiments/data/{{dataset}}.csv",
            "result": "/experiments/results/{{id}}/{{algorithm}}/graph_{{dataset}}_{{alpha}}.xml",
            "alpha": "{{alpha}}"
        }
    }]
}

# Each job contains expanded matrix variables for template substitution
for job in jobs:
    print(f"Job: {job}")
    # Example: {'algorithm': 'pc', 'dataset': 'asia', 'alpha': 0.01}
```

**Implemented Features**:
- ✅ Parse and validate YAML workflow files
- ✅ Expand matrix variables into job configurations
- ✅ Support flexible path templating with {{}} variables
- ✅ Comprehensive error handling and 100% test coverage

**Next Phase**: Action execution engine with template variable substitution

!!! warning "Planned Feature"
    The `series`, `resources`, `analysis`, and `monitoring` workflow sections shown below are planned features and not yet implemented in the current schema.

```yaml
# series_workflow_example.yaml (Planned Feature)
  ges_series:
    algorithm: "ges" 
    package: "causaliq-discovery"
    datasets: ["alarm", "asia"]  # Reference same datasets
    sample_sizes: [100, 500, 1000]
    randomizations: 10
    hyperparameters:
      score_type: ["bic", "aic"]

# Resource configuration
resources:
  max_parallel_jobs: 8
  memory_limit_per_job: "4GB"
  runtime_limit_per_job: "30m"
  total_runtime_limit: "4h"

# Analysis configuration
analysis:
  compare_series: ["pc_series", "ges_series"]
  metrics: ["shd", "precision", "recall", "f1"]
  statistical_significance: 0.05
  output_format: ["csv", "json"]

# Logging and monitoring
monitoring:
  progress_updates: "1m"
  log_level: "INFO"
  save_intermediate: true
```

## Use Case 2: External Package Integration

!!! warning "Planned Feature"
    The `series`, `external_packages`, `resources`, and `validation` workflow sections shown in this example are planned features and not yet implemented in the current schema.

### Scenario
Use R bnlearn package alongside Python algorithms for comprehensive comparison.

### Multi-Package Workflow
```yaml
# multi_package_comparison.yaml
metadata:
  name: "python_r_algorithm_comparison"
  description: "Compare Python and R causal discovery implementations"

series:
  python_pc:
    algorithm: "pc"
    package: "causaliq-discovery"
    datasets: ["alarm"]
    sample_sizes: [500, 1000]
    randomizations: 5
    hyperparameters:
      alpha: 0.05
      
  r_bnlearn_pc:
    algorithm: "pc.stable"
    package: "r_bnlearn"
    datasets: ["alarm"]  # Same datasets for comparison
    sample_sizes: [500, 1000] 
    randomizations: 5
    hyperparameters:
      alpha: 0.05
      test: "cor"

# External package requirements
external_packages:
  r_bnlearn:
    check_installation: true
    required_version: ">=4.7"
    install_if_missing: false  # Fail if not available

resources:
  max_parallel_jobs: 4  # Fewer for external packages
  memory_limit_per_job: "8GB"
  
validation:
  dry_run: true  # Preview before execution
  check_dependencies: true
```

## Use Case 3: Configuration Inheritance

!!! warning "Planned Feature"
    The `defaults`, `inherits`, and inheritance-based workflow configuration shown in this example are planned features and not yet implemented in the current schema.

### Scenario
Create specific experiments based on common base configuration.

### Base Configuration
```yaml
# base_causal_experiment.yaml
metadata:
  name: "base_causal_discovery_template"
  description: "Base template for causal discovery experiments"

defaults:
  datasets:
    - name: "alarm" 
      zenodo_id: "alarm_networks_v1"
    - name: "asia"
      zenodo_id: "asia_networks_v1"
  sample_sizes: [100, 500, 1000]
  randomizations: 10
  
resources:
  max_parallel_jobs: 6
  memory_limit_per_job: "4GB"
  runtime_limit_per_job: "1h"
  
monitoring:
  log_level: "INFO"
  progress_updates: "30s"
```

### Inherited Specific Experiment
```yaml
# pc_alpha_study.yaml
inherits: "base_causal_experiment.yaml"

metadata:
  name: "pc_alpha_sensitivity_study"
  description: "Study effect of alpha parameter on PC algorithm"

overrides:
  series:
    pc_alpha_study:
      algorithm: "pc"
      package: "causaliq-discovery" 
      hyperparameters:
        alpha: [0.001, 0.01, 0.05, 0.1, 0.2]
      
  analysis:
    metrics: ["shd", "precision", "recall"]
    focus_parameter: "alpha"
    statistical_tests: true
```

## Use Case 4: LLM Integration for Model Averaging

!!! warning "Planned Feature"
    The `series`, `llm_analysis`, and `model_averaging` workflow sections shown in this example are planned features and not yet implemented in the current schema.

### Scenario
Use LLM to guide intelligent model averaging across multiple algorithm results.

### LLM-Enhanced Workflow
```yaml
# llm_model_averaging.yaml
metadata:
  name: "llm_guided_model_averaging"
  description: "Use LLM for intelligent model averaging"

# First run multiple algorithms
series:
  pc_results:
    algorithm: "pc"
    package: "causaliq-discovery"
    datasets: ["healthcare_study"]
    sample_sizes: [1000]
    randomizations: 5
    hyperparameters:
      alpha: 0.05
      
  ges_results:
    algorithm: "ges"
    package: "causaliq-discovery"
    datasets: ["healthcare_study"]
    sample_sizes: [1000]
    randomizations: 5
    hyperparameters:
      score_type: "bic"

# LLM integration for analysis
llm_analysis:
  stage: "post_discovery"
  package: "causaliq-knowledge"
  tasks:
    - task: "analyze_algorithm_outputs"
      inputs: ["pc_results", "ges_results"]
      domain_knowledge: "healthcare/cardiology"
      
    - task: "suggest_averaging_weights"
      based_on: "algorithm_reliability_analysis"
      
    - task: "validate_combined_graph"
      domain_expertise: true

# Model averaging using LLM suggestions
model_averaging:
  package: "causaliq-analysis"
  method: "llm_weighted_average"
  inputs: ["pc_results", "ges_results", "llm_suggestions"]
```

## Use Case 5: Dataset Download and Randomization

!!! warning "Planned Feature"
    The `datasets`, `randomization`, `series`, and `analysis` workflow sections shown in this example are planned features and not yet implemented in the current schema.

### Scenario
Automated dataset download from Zenodo with systematic randomization for robustness testing.

### Dataset Management Workflow
```yaml
# dataset_robustness_study.yaml
metadata:
  name: "dataset_robustness_analysis"
  description: "Study algorithm robustness to data variations"

# Dataset configuration with automatic download
datasets:
  primary_dataset:
    name: "benchmark_networks"
    source: "zenodo"
    zenodo_id: "benchmark_causal_v2"
    cache_locally: true
    
# Randomization strategies  
randomization:
  strategies:
    - type: "subsample"
      fractions: [0.7, 0.8, 0.9, 1.0]
      
    - type: "variable_reorder"
      random_seeds: [42, 123, 456]
      
    - type: "noise_injection"
      noise_levels: [0.0, 0.05, 0.1]
      noise_type: "gaussian"

# Series using randomized datasets
series:
  robustness_test:
    algorithm: "pc"
    package: "causaliq-discovery"
    apply_all_randomizations: true
    hyperparameters:
      alpha: 0.05
      
# Analysis focuses on robustness metrics
analysis:
  robustness_metrics:
    - "stability_across_subsamples"
    - "invariance_to_ordering"
    - "noise_resistance"
  generate_robustness_report: true
```

## CLI Usage Examples

### Basic Execution
```bash
# Execute a series-based workflow
causaliq-workflow run pc_ges_comparison.yaml

# Dry-run to preview execution plan
causaliq-workflow validate pc_ges_comparison.yaml --dry-run

# Monitor running workflow
causaliq-workflow status workflow-abc123

# Pause running workflow
causaliq-workflow pause workflow-abc123

# Resume paused workflow  
causaliq-workflow resume workflow-abc123
```

### Advanced Options
```bash
# Override resource limits
causaliq-workflow run experiment.yaml --max-jobs 16 --memory-per-job 8GB

# Run specific series only
causaliq-workflow run experiment.yaml --series pc_series

# Export results in specific format
causaliq-workflow results export workflow-abc123 --format csv --output results/
```

## Python API Examples

### Basic Workflow Execution
```python
from causaliq_workflow import WorkflowManager, ConfigurationManager

# Load and validate configuration
config_manager = ConfigurationManager()
workflow_config = config_manager.load_workflow("pc_ges_comparison.yaml")

# Execute workflow
workflow_manager = WorkflowManager()
result = workflow_manager.execute_workflow(workflow_config)

# Access results by series
pc_results = result.get_series_results("pc_series")
ges_results = result.get_series_results("ges_series")
```

### Series Analysis
```python
from causaliq_workflow.analysis import SeriesComparison

# Compare algorithm performance across series
comparison = SeriesComparison()
comparison.add_series("PC Algorithm", pc_results)
comparison.add_series("GES Algorithm", ges_results)

# Generate comparison metrics
metrics = comparison.compare_algorithms(["shd", "precision", "recall"])
statistical_significance = comparison.statistical_test(alpha=0.05)

# Export results
comparison.export_results("algorithm_comparison.csv")
```

### Configuration Inheritance
```python
from causaliq_workflow.config import ConfigurationInheritance

# Create experiment based on template
inheritance = ConfigurationInheritance()
base_config = inheritance.load_base("base_causal_experiment.yaml")

# Apply specific overrides
specific_config = inheritance.create_derived(
    base_config,
    overrides={
        "series": {
            "custom_study": {
                "algorithm": "fci",
                "hyperparameters": {"alpha": 0.01}
            }
        }
    }
)
```

This focused approach emphasizes the series concept and immediate implementation needs while providing practical examples for the three-month development phase.

## Use Case 2: Production Causal Inference Workflow

!!! warning "Planned Feature"
    This production workflow configuration demonstrates planned features including `parameters`, `resources`, `monitoring`, `depends_on`, `inputs`, `outputs`, and streaming data integration. These are not yet implemented in the current schema.

### Scenario
A business wants to continuously analyze the causal impact of marketing campaigns on customer behavior using streaming data.

### Workflow Configuration
```yaml
# production_inference_workflow.yaml
metadata:
  name: "marketing_causal_inference"
  version: "2.1"
  description: "Real-time causal inference for marketing effectiveness"
  environment: "production"

parameters:
  data_stream: "kafka://marketing-events"
  batch_size: 10000
  update_frequency: "1h"
  lookback_window: "30d"

resources:
  dask_cluster: "kubernetes://marketing-cluster"
  min_workers: 3
  max_workers: 20
  auto_scale: true
  memory_per_worker: "4GB"

monitoring:
  metrics_endpoint: "prometheus://metrics"
  alert_threshold: 0.1
  slack_notifications: true

steps:
  - name: "stream_ingestion"
    package: "causaliq-data"
    method: "ingest_stream"
    parameters:
      source: ${parameters.data_stream}
      batch_size: ${parameters.batch_size}
      schema_validation: true
    outputs: ["raw_events"]
    
  - name: "real_time_preprocessing"
    package: "causaliq-data"
    method: "preprocess_streaming"
    depends_on: ["stream_ingestion"]
    parameters:
      window_size: ${parameters.lookback_window}
      features: ["campaign_type", "customer_segment", "channel", "timestamp"]
      target: "conversion"
    inputs: ["raw_events"]
    outputs: ["processed_batch"]

  - name: "causal_graph_update"
    package: "causaliq-discovery"
    method: "incremental_learning"
    depends_on: ["real_time_preprocessing"]
    parameters:
      existing_graph: "models/marketing_graph.pkl"
      update_threshold: 1000
      stability_check: true
    inputs: ["processed_batch"]
    outputs: ["updated_graph", "graph_changes"]

  - name: "intervention_effects"
    package: "causaliq-inference"
    method: "estimate_ate"
    depends_on: ["causal_graph_update"]
    parameters:
      treatment_vars: ["campaign_type", "channel"]
      outcome_var: "conversion"
      adjustment_sets: "auto"
    inputs: ["updated_graph", "processed_batch"]
    outputs: ["treatment_effects", "confidence_intervals"]

  - name: "anomaly_detection"
    package: "causaliq-monitoring"
    method: "detect_effect_anomalies"
    depends_on: ["intervention_effects"]
    parameters:
      baseline_window: "7d"
      anomaly_threshold: 2.0
    inputs: ["treatment_effects"]
    outputs: ["anomalies", "alerts"]

  - name: "automated_insights"
    package: "causaliq-workflow"
    method: "llm_generate_insights"
    depends_on: ["intervention_effects", "anomaly_detection"]
    parameters:
      context: "marketing_optimization"
      include_recommendations: true
      business_constraints: "config/business_rules.yaml"
    inputs: ["treatment_effects", "anomalies", "graph_changes"]
    outputs: ["insights", "recommendations"]

  - name: "dashboard_update"
    package: "causaliq-visualization"
    method: "update_dashboard"
    depends_on: ["automated_insights"]
    parameters:
      dashboard_id: "marketing_causal_dashboard"
      auto_refresh: true
    inputs: ["treatment_effects", "insights", "recommendations"]
    outputs: ["dashboard_url"]

triggers:
  schedule: "0 * * * *"  # Every hour
  data_threshold: 5000   # Trigger if 5k new events
  
failure_handling:
  retry_attempts: 3
  fallback_to_previous: true
  alert_on_failure: true
```

## Use Case 3: Interactive Research Exploration

!!! warning "Planned Feature"
    This interactive exploration workflow demonstrates planned features including interactive mode, LLM-assisted analysis, `user_interaction`, `state`, and iterative workflow refinement. These are not yet implemented in the current schema.

### Scenario  
An interactive session where researchers explore causal relationships with LLM assistance and iterative refinement.

### Workflow Configuration
```yaml
# interactive_exploration_workflow.yaml
metadata:
  name: "interactive_causal_exploration"
  version: "1.0"
  description: "LLM-assisted interactive causal discovery"
  mode: "interactive"

parameters:
  data_source: "research/climate_data.csv"
  domain: "climate_science"
  interaction_mode: "jupyter"

resources:
  dask_cluster: "local"
  workers: 2
  memory_per_worker: "6GB"

interaction:
  llm_model: "gpt-4"
  enable_suggestions: true
  save_conversation: true

steps:
  - name: "initial_analysis"
    package: "causaliq-data"
    method: "exploratory_analysis"
    parameters:
      generate_summary: true
      correlation_analysis: true
    outputs: ["data_summary", "correlations"]

  - name: "llm_initial_consultation"
    package: "causaliq-workflow"
    method: "llm_domain_consultation"
    depends_on: ["initial_analysis"]
    parameters:
      domain: ${parameters.domain}
      task: "What causal relationships should we investigate in this climate dataset?"
      context_data: true
    inputs: ["data_summary", "correlations"]
    outputs: ["domain_insights", "suggested_relationships"]
    interactive: true

  - name: "guided_discovery"
    package: "causaliq-discovery"
    method: "guided_search"
    depends_on: ["llm_initial_consultation"]
    parameters:
      prior_knowledge: "domain_insights"
      search_strategy: "hypothesis_driven"
    inputs: ["data_summary", "suggested_relationships"]
    outputs: ["candidate_graphs"]
    interactive: true

  - name: "iterative_refinement"
    type: "interactive_loop"
    depends_on: ["guided_discovery"]
    max_iterations: 10
    steps:
      - name: "graph_evaluation"
        package: "causaliq-validation"
        method: "evaluate_graph"
        inputs: ["candidate_graphs"]
        outputs: ["evaluation_metrics"]

      - name: "llm_feedback"
        package: "causaliq-workflow"
        method: "llm_evaluate_graph"
        parameters:
          domain: ${parameters.domain}
          include_suggestions: true
        inputs: ["candidate_graphs", "evaluation_metrics"]
        outputs: ["llm_feedback", "improvement_suggestions"]
        interactive: true

      - name: "user_decision"
        type: "user_input"
        prompt: "Based on the LLM feedback, would you like to: (1) Accept graph (2) Refine further (3) Try different approach?"
        outputs: ["user_choice"]

      - name: "conditional_refinement"
        type: "conditional"
        condition: "user_choice == 'refine'"
        package: "causaliq-discovery"
        method: "refine_graph"
        inputs: ["candidate_graphs", "improvement_suggestions"]
        outputs: ["refined_graphs"]

  - name: "final_interpretation"
    package: "causaliq-workflow"
    method: "llm_comprehensive_interpretation"
    depends_on: ["iterative_refinement"]
    parameters:
      domain: ${parameters.domain}
      include_limitations: true
      suggest_experiments: true
    inputs: ["candidate_graphs", "evaluation_metrics"]
    outputs: ["final_interpretation", "experiment_suggestions"]

notebook_integration:
  auto_generate_cells: true
  include_visualizations: true
  save_checkpoints: true
```

## Example CLI Usage

```bash
# Execute a workflow
causaliq-workflow run workflow.yaml --config production.yaml

# Validate workflow before execution
causaliq-workflow validate workflow.yaml

# Interactive mode
causaliq-workflow interactive --domain healthcare --data patient_data.csv

# Monitor running workflow
causaliq-workflow status workflow-123

# Generate workflow template
causaliq-workflow template --type discovery --domain finance

# List available packages and methods
causaliq-workflow list-methods --package causaliq-discovery
```

## Integration Examples

### Python API Usage
```python
from causaliq_workflow import WorkflowEngine, DaskClusterManager

# Set up DASK cluster
cluster_manager = DaskClusterManager()
client = cluster_manager.create_local_cluster(workers=4)

# Initialize workflow engine
engine = WorkflowEngine(client=client)

# Load and execute workflow
result = engine.execute_workflow("workflow.yaml")

# Access results
causal_graph = result.get_output("ensemble_graph")
interpretation = result.get_output("interpretation")

# Interactive LLM consultation
llm_analyzer = engine.get_llm_analyzer()
insights = llm_analyzer.interpret_results(result.all_outputs, domain="healthcare")
```

### Jupyter Notebook Integration
```python
%%causaliq_workflow
metadata:
  name: "notebook_workflow"
  
steps:
  - name: "discovery"
    package: "causaliq-discovery"
    method: "pc"
    parameters:
      alpha: 0.05
    
# Results automatically displayed in notebook
```