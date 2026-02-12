# Usage Examples

Comprehensive examples demonstrating common patterns and advanced usage of the CausalIQ Workflow framework.

## Basic Workflows

### Simple Action Execution

```python
from causaliq_workflow import WorkflowExecutor

# Create and execute a basic workflow
executor = WorkflowExecutor()

# Define workflow programmatically
simple_workflow = {
    "id": "simple-experiment",
    "description": "Basic structure learning experiment",
    "steps": [
        {
            "name": "Learn Structure", 
            "uses": "structure-learner",
            "with": {
                "data_path": "/data/asia.csv",
                "output_path": "/results/asia_structure.graphml",
                "algorithm": "pc",
                "alpha": 0.05
            }
        }
    ]
}

# Execute workflow
results = executor.execute_workflow(simple_workflow, mode="run")
print(f"Workflow completed: {results}")
```

### Loading from YAML

```yaml
# experiments/basic-experiment.yml
id: "basic-experiment"
description: "Structure learning with PC algorithm"
data_root: "/experiments/data"
output_root: "/experiments/results"

steps:
  - name: "PC Structure Learning"
    uses: "pc-learner"
    with:
      data_path: "{{data_root}}/asia.csv"
      output_path: "{{output_root}}/{{id}}/structure.graphml"
      alpha: 0.05
      max_depth: 3
```

```python
# Execute YAML workflow
workflow = executor.parse_workflow("experiments/basic-experiment.yml")
results = executor.execute_workflow(workflow, mode="run")
```

## Matrix Workflows

### Parameter Sweeps

```yaml
# experiments/parameter-sweep.yml
id: "parameter-sweep"
description: "Multi-algorithm parameter sweep"
data_root: "/experiments/data"
output_root: "/experiments/results"

matrix:
  dataset: ["asia", "cancer", "earthquake"]
  algorithm: ["pc", "ges", "lingam"]
  alpha: [0.01, 0.05, 0.1]

steps:
  - name: "Structure Learning"
    uses: "structure-learner"
    with:
      data_path: "{{data_root}}/{{dataset}}.csv"
      output_path: "{{output_root}}/{{id}}/{{dataset}}_{{algorithm}}_{{alpha}}.graphml"
      algorithm: "{{algorithm}}"
      alpha: "{{alpha}}"
      
  - name: "Validate Structure"
    uses: "structure-validator"
    with:
      structure_path: "{{output_root}}/{{id}}/{{dataset}}_{{algorithm}}_{{alpha}}.graphml"
      metrics_path: "{{output_root}}/{{id}}/{{dataset}}_{{algorithm}}_{{alpha}}_metrics.json"
```

```python
# Execute matrix workflow
workflow = executor.parse_workflow("experiments/parameter-sweep.yml")

# Show matrix expansion
if "matrix" in workflow:
    jobs = executor.expand_matrix(workflow["matrix"])
    print(f"Generated {len(jobs)} parameter combinations")
    
    # Preview first few jobs
    for i, job in enumerate(jobs[:3]):
        print(f"Job {i}: {job}")

# Execute all combinations
results = executor.execute_workflow(workflow, mode="run")
```

### Conditional Matrix

```yaml
# experiments/conditional-matrix.yml
id: "conditional-matrix"
description: "Matrix with conditional parameters"

matrix:
  dataset: ["small_data", "medium_data", "large_data"]
  algorithm: ["pc", "ges"]
  include:
    - dataset: "small_data"
      algorithm: "pc"
      alpha: 0.05
      max_iter: 1000
    - dataset: "medium_data" 
      algorithm: "pc"
      alpha: 0.01
      max_iter: 5000
    - dataset: "large_data"
      algorithm: "ges" 
      regularization: 0.1
      max_iter: 10000

steps:
  - name: "Adaptive Structure Learning"
    uses: "adaptive-learner"
    with:
      data_path: "/data/{{dataset}}.csv"
      algorithm: "{{algorithm}}"
      alpha: "{{alpha|default(0.05)}}"
      max_iter: "{{max_iter|default(1000)}}"
      regularization: "{{regularization|default(0.0)}}"
```

## Multi-Step Workflows

### Data Processing Pipeline

```yaml
# experiments/data-pipeline.yml
id: "data-processing-pipeline"
description: "Complete data processing and analysis pipeline"

matrix:
  dataset: ["healthcare", "finance", "biology"]
  preprocessing: ["standard", "robust"]

steps:
  - name: "Data Preprocessing"
    uses: "data-preprocessor"
    with:
      input_path: "/raw_data/{{dataset}}.csv"
      output_path: "/processed_data/{{dataset}}_{{preprocessing}}.csv"
      method: "{{preprocessing}}"
      remove_outliers: true
      normalize: true
      
  - name: "Feature Selection"
    uses: "feature-selector"
    with:
      input_path: "/processed_data/{{dataset}}_{{preprocessing}}.csv"
      output_path: "/features/{{dataset}}_{{preprocessing}}_selected.csv"
      method: "mutual_info"
      max_features: 50
      
  - name: "Structure Learning"
    uses: "structure-learner"
    with:
      data_path: "/features/{{dataset}}_{{preprocessing}}_selected.csv"
      output_path: "/structures/{{dataset}}_{{preprocessing}}_structure.graphml"
      algorithm: "pc"
      
  - name: "Model Validation"
    uses: "model-validator"
    with:
      structure_path: "/structures/{{dataset}}_{{preprocessing}}_structure.graphml"
      data_path: "/features/{{dataset}}_{{preprocessing}}_selected.csv"
      output_path: "/validation/{{dataset}}_{{preprocessing}}_results.json"
      k_fold: 5
      
  - name: "Generate Report"
    uses: "report-generator"
    with:
      structure_path: "/structures/{{dataset}}_{{preprocessing}}_structure.graphml"
      validation_path: "/validation/{{dataset}}_{{preprocessing}}_results.json"
      report_path: "/reports/{{dataset}}_{{preprocessing}}_report.html"
```

## Custom Actions

### Creating Domain-Specific Actions

```python
# custom_actions/causal_discovery.py
from causaliq_workflow.action import BaseActionProvider, ActionExecutionError
from typing import Any, Dict
import pandas as pd
import networkx as nx

class PCAlgorithmAction(BaseActionProvider):
    """PC algorithm for causal structure learning."""
    
    name = "pc-algorithm"
    version = "2.1.0"
    description = "Peter-Clark algorithm for causal discovery"
    supported_actions = {"learn_structure"}
    
    def run(
        self,
        action: str,
        parameters: Dict[str, Any],
        mode: str = "dry-run",
        context=None,
        logger=None,
    ) -> Dict[str, Any]:
        """Execute PC algorithm."""
        try:
            # Load data
            data_path = parameters["data_path"]
            data = pd.read_csv(data_path)
            
            # PC algorithm parameters
            alpha = parameters.get("alpha", 0.05)
            max_depth = parameters.get("max_depth", 3)
            
            # Run PC algorithm (simplified example)
            graph = self._run_pc_algorithm(data, alpha, max_depth)
            
            # Save results
            output_path = parameters["output_path"]
            nx.write_graphml(graph, output_path)
            
            return {
                "structure_path": output_path,
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "alpha_used": alpha,
                "max_depth_used": max_depth
            }
            
        except Exception as e:
            raise ActionExecutionError(f"PC algorithm failed: {e}") from e
    
    def _run_pc_algorithm(self, data, alpha, max_depth):
        """Simplified PC algorithm implementation."""
        # This would contain the actual PC algorithm logic
        # For demonstration, create a simple graph
        G = nx.DiGraph()
        G.add_nodes_from(data.columns)
        # Add some edges based on correlations (simplified)
        return G

class NetworkAnalysisAction(BaseActionProvider):
    """Network analysis and metrics calculation."""
    
    name = "network-analysis" 
    version = "1.3.0"
    description = "Compute network topology metrics"
    supported_actions = {"analyse_network"}
    
    def run(
        self,
        action: str,
        parameters: Dict[str, Any],
        mode: str = "dry-run",
        context=None,
        logger=None,
    ) -> Dict[str, Any]:
        """Analyse network structure."""
        try:
            # Load structure
            structure_path = parameters["structure_path"]
            graph = nx.read_graphml(structure_path)
            
            # Compute metrics
            metrics = {
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "density": nx.density(graph),
                "transitivity": nx.transitivity(graph),
                "average_clustering": nx.average_clustering(graph),
            }
            
            # Add centrality measures
            centrality = nx.degree_centrality(graph)
            metrics["max_centrality"] = max(centrality.values())
            metrics["avg_centrality"] = sum(centrality.values()) / len(centrality)
            
            # Save metrics
            output_path = parameters["output_path"]
            import json
            with open(output_path, "w") as f:
                json.dump(metrics, f, indent=2)
                
            return metrics
            
        except Exception as e:
            raise ActionExecutionError(f"Network analysis failed: {e}") from e
```

### Using Custom Actions

```yaml
# experiments/custom-workflow.yml
id: "custom-causal-discovery"
description: "Workflow using custom actions"

matrix:
  dataset: ["asia", "cancer"]
  alpha: [0.01, 0.05]

steps:
  - name: "PC Structure Learning"
    uses: "pc-algorithm"
    with:
      data_path: "/data/{{dataset}}.csv"
      output_path: "/results/{{dataset}}_{{alpha}}_structure.graphml"
      alpha: "{{alpha}}"
      max_depth: 3
      
  - name: "Network Analysis"
    uses: "network-analysis"
    with:
      structure_path: "/results/{{dataset}}_{{alpha}}_structure.graphml"
      output_path: "/results/{{dataset}}_{{alpha}}_metrics.json"
```

## Error Handling and Validation

### Robust Workflow Execution

```python
from causaliq_workflow import WorkflowExecutor, WorkflowExecutionError
from causaliq_workflow.schema import WorkflowValidationError
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def execute_workflow_safely(workflow_path: str) -> bool:
    """Execute workflow with comprehensive error handling."""
    executor = WorkflowExecutor()
    
    try:
        # Parse and validate
        logger.info(f"Loading workflow: {workflow_path}")
        workflow = executor.parse_workflow(workflow_path)
        logger.info(f"Workflow loaded: {workflow['id']}")
        
        # Execute with error handling
        results = executor.execute_workflow(workflow, mode="run")
        logger.info("Workflow completed successfully")
        
        return True
        
    except FileNotFoundError:
        logger.error(f"Workflow file not found: {workflow_path}")
        return False
        
    except WorkflowValidationError as e:
        logger.error(f"Workflow validation failed: {e}")
        logger.error(f"Schema path: {e.schema_path}")
        return False
        
    except WorkflowExecutionError as e:
        logger.error(f"Workflow execution failed: {e}")
        # Check for specific error types
        if "Template" in str(e):
            logger.error("Template variable issue - check matrix and step parameters")
        elif "Action" in str(e):
            logger.error("Action execution issue - check action inputs and availability")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

# Execute multiple workflows with error recovery
workflow_files = [
    "experiments/experiment-1.yml",
    "experiments/experiment-2.yml", 
    "experiments/experiment-3.yml"
]

successful_workflows = []
failed_workflows = []

for workflow_file in workflow_files:
    if execute_workflow_safely(workflow_file):
        successful_workflows.append(workflow_file)
    else:
        failed_workflows.append(workflow_file)

print(f"Successful: {len(successful_workflows)}")
print(f"Failed: {len(failed_workflows)}")
```

## Integration Examples

### Jupyter Notebook Integration

```python
# notebook_integration.py
from causaliq_workflow import WorkflowExecutor
import matplotlib.pyplot as plt
import networkx as nx
import json

class NotebookWorkflowRunner:
    """Workflow execution optimized for Jupyter notebooks."""
    
    def __init__(self):
        self.executor = WorkflowExecutor()
        self.results = {}
    
    def run_experiment(self, workflow_path, display_results=True):
        """Run workflow and display results inline."""
        workflow = self.executor.parse_workflow(workflow_path)
        
        print(f"🔄 Executing: {workflow['id']}")
        print(f"📋 Description: {workflow.get('description', 'No description')}")
        
        # Show matrix expansion if present
        if "matrix" in workflow:
            jobs = self.executor.expand_matrix(workflow["matrix"])
            print(f"🔢 Matrix jobs: {len(jobs)}")
            
        # Execute
        results = self.executor.execute_workflow(workflow, mode="run")
        self.results[workflow['id']] = results
        
        if display_results:
            self.display_results(workflow['id'])
            
        return results
    
    def display_results(self, workflow_id):
        """Display workflow results with visualizations."""
        results = self.results.get(workflow_id)
        if not results:
            print("No results available")
            return
            
        # Display summary
        print("\\n📊 Results Summary:")
        for step_result in results:
            if isinstance(step_result, dict) and "structure_path" in step_result:
                self.visualize_structure(step_result["structure_path"])
                
    def visualize_structure(self, structure_path):
        """Visualize learned causal structure."""
        try:
            graph = nx.read_graphml(structure_path)
            
            plt.figure(figsize=(10, 8))
            pos = nx.spring_layout(graph)
            nx.draw(graph, pos, with_labels=True, node_color='lightblue', 
                   node_size=1000, font_size=10, arrows=True)
            plt.title(f"Causal Structure ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges)")
            plt.show()
            
        except Exception as e:
            print(f"Visualization failed: {e}")

# Usage in Jupyter notebook
runner = NotebookWorkflowRunner()

# Run experiments
runner.run_experiment("experiments/pc-analysis.yml")
runner.run_experiment("experiments/ges-analysis.yml")

# Compare results
print("\\n📈 Experiment Comparison:")
for workflow_id, results in runner.results.items():
    print(f"{workflow_id}: {len(results)} steps completed")
```

### Docker Integration

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy workflow framework
COPY causaliq_workflow/ ./causaliq_workflow/
COPY experiments/ ./experiments/
COPY data/ ./data/

# Create output directory
RUN mkdir -p /app/results

# Default command
CMD ["python", "-m", "causaliq_workflow", "experiments/default-experiment.yml", "--output-dir", "/app/results"]
```

```bash
# Build and run
docker build -t causal-workflow .

# Run specific experiment
docker run -v $(pwd)/results:/app/results causal-workflow \\
    python -m causaliq_workflow experiments/large-scale-analysis.yml

# Run with custom data
docker run -v $(pwd)/data:/app/custom_data -v $(pwd)/results:/app/results causal-workflow \\
    python -m causaliq_workflow experiments/custom-data-experiment.yml
```

## Performance Optimization

### Parallel Matrix Execution

```python
from causaliq_workflow import WorkflowExecutor
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

def execute_matrix_job(workflow_data, job_index, job_params):
    """Execute single matrix job in separate process."""
    try:
        executor = WorkflowExecutor()
        
        # Create job-specific workflow
        job_workflow = workflow_data.copy()
        # Apply matrix parameters to workflow
        # (implementation would substitute template variables)
        
        results = executor.execute_workflow(job_workflow, mode="run")
        return job_index, results, None
        
    except Exception as e:
        return job_index, None, str(e)

def execute_workflow_parallel(workflow_path, max_workers=None):
    """Execute matrix workflow with parallel job execution."""
    executor = WorkflowExecutor()
    workflow = executor.parse_workflow(workflow_path)
    
    if "matrix" not in workflow:
        # No matrix, execute normally
        return executor.execute_workflow(workflow, mode="run")
    
    # Expand matrix
    jobs = executor.expand_matrix(workflow["matrix"])
    
    if max_workers is None:
        max_workers = min(len(jobs), mp.cpu_count())
    
    print(f"Executing {len(jobs)} matrix jobs with {max_workers} workers")
    
    results = {}
    errors = {}
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all jobs
        future_to_job = {
            executor.submit(execute_matrix_job, workflow, i, job): i 
            for i, job in enumerate(jobs)
        }
        
        # Collect results
        for future in as_completed(future_to_job):
            job_index = future_to_job[future]
            job_index_result, result, error = future.result()
            
            if error:
                errors[job_index] = error
                print(f"❌ Job {job_index} failed: {error}")
            else:
                results[job_index] = result
                print(f"✅ Job {job_index} completed")
    
    print(f"\\nCompleted: {len(results)}/{len(jobs)} jobs")
    if errors:
        print(f"Errors: {len(errors)} jobs failed")
        
    return results, errors

# Usage
results, errors = execute_workflow_parallel("experiments/large-matrix.yml", max_workers=8)
```

---

**[← Previous: CLI Interface](cli.md)** | **[Back to API Overview](overview.md)**