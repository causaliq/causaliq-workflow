# CausalIQ Pipeline - Example Workflows

## Current Implementation Examples (v0.1.0)

### Basic Action Workflow

Our current implementation supports GitHub Actions-style workflows with action components:

```yaml
# basic_structure_learning.yaml
name: "Basic Structure Learning"
id: "basic-experiment-001"
data_root: "/data"
output_root: "/results"

steps:
  - name: "Learn Structure"
    uses: "dummy-structure-learner"
    with:
      dataset: "asia"
      algorithm: "dummy"
```

### Matrix Strategy Workflow

The implemented schema supports matrix variables for parameterized experiments:

```yaml
# matrix_experiment.yaml
name: "Algorithm Comparison Matrix"
id: "algo-comparison-001"
data_root: "/experiments/data"
output_root: "/experiments/results"

matrix:
  dataset: ["asia", "cancer"]
  algorithm: ["pc", "ges"]
  alpha: [0.01, 0.05]

steps:
  - name: "Structure Learning"
    uses: "dummy-structure-learner"
    with:
      max_iter: 1000
```

### Path Construction Pattern

Our implementation automatically constructs paths from matrix variables:

```yaml
# Input paths: {data_root}/{dataset}/input.csv
# - /experiments/data/asia/input.csv
# - /experiments/data/cancer/input.csv

# Output paths: {output_root}/{id}/{dataset}_{algorithm}/
# - /experiments/results/algo-comparison-001/asia_pc/
# - /experiments/results/algo-comparison-001/asia_ges/
# - /experiments/results/algo-comparison-001/cancer_pc/
# - /experiments/results/algo-comparison-001/cancer_ges/
```

## Implemented Features

### ✅ Action Framework
- **Action Registration**: Actions defined as Python classes
- **Type Safety**: Input/output specifications with type hints
- **Error Handling**: Comprehensive ActionExecutionError and ActionValidationError
- **GraphML Output**: Standardized format for causal graphs

### ✅ Schema Validation
- **GitHub Actions Syntax**: Familiar workflow patterns
- **Matrix Variables**: Full support for parameterized experiments  
- **Path Construction**: data_root, output_root, id fields
- **Action Parameters**: with blocks for action configuration

### ✅ Test Coverage
- **Functional Tests**: Real filesystem operations with tracked test data
- **Unit Tests**: Mocked dependencies for action logic testing
- **Schema Tests**: Comprehensive validation of all workflow features

## Example Action Implementation

```python
class DummyStructureLearnerAction(Action):
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

## Next Phase: Workflow Execution

### Planned WorkflowExecutor Implementation

```python
# Future implementation (Phase 2)
class WorkflowExecutor:
    """Execute complete workflows with matrix expansion."""
    
    def execute_workflow(self, workflow_path: str) -> WorkflowResult:
        """Parse YAML and execute all workflow steps."""
        
    def expand_matrix(self, matrix: Dict[str, List]) -> List[JobConfig]:
        """Convert matrix variables to individual jobs."""
        
    def construct_paths(self, job: JobConfig) -> PathConfig:
        """Build input/output paths from matrix variables."""
```
      
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
  package: "causaliq-llm"
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
causaliq-pipeline run pc_ges_comparison.yaml

# Dry-run to preview execution plan
causaliq-pipeline validate pc_ges_comparison.yaml --dry-run

# Monitor running workflow
causaliq-pipeline status workflow-abc123

# Pause running workflow
causaliq-pipeline pause workflow-abc123

# Resume paused workflow  
causaliq-pipeline resume workflow-abc123
```

### Advanced Options
```bash
# Override resource limits
causaliq-pipeline run experiment.yaml --max-jobs 16 --memory-per-job 8GB

# Run specific series only
causaliq-pipeline run experiment.yaml --series pc_series

# Export results in specific format
causaliq-pipeline results export workflow-abc123 --format csv --output results/
```

## Python API Examples

### Basic Workflow Execution
```python
from causaliq_pipeline import WorkflowManager, ConfigurationManager

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
from causaliq_pipeline.analysis import SeriesComparison

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
from causaliq_pipeline.config import ConfigurationInheritance

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

## Use Case 2: Production Causal Inference Pipeline

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
    package: "causaliq-pipeline"
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
    package: "causaliq-pipeline"
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
        package: "causaliq-pipeline"
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
    package: "causaliq-pipeline"
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
causaliq-pipeline run workflow.yaml --config production.yaml

# Validate workflow before execution
causaliq-pipeline validate workflow.yaml

# Interactive mode
causaliq-pipeline interactive --domain healthcare --data patient_data.csv

# Monitor running workflow
causaliq-pipeline status workflow-123

# Generate workflow template
causaliq-pipeline template --type discovery --domain finance

# List available packages and methods
causaliq-pipeline list-methods --package causaliq-discovery
```

## Integration Examples

### Python API Usage
```python
from causaliq_pipeline import WorkflowEngine, DaskClusterManager

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