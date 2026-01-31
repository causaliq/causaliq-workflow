# CI Workflow Matrix Strategy Implementation

## Overview

The matrix strategy implementation provides the GitHub Actions-style `strategy.matrix` functionality within the unified CI workflow engine. This is **not** a separate matrix expansion system, but rather a core component of the CI workflow architecture that handles the complex logic of experiment combination generation.

## GitHub Actions Matrix Strategy

### Core Matrix Features

The implementation supports all GitHub Actions matrix strategy features:

```yaml
strategy:
  matrix:
    algorithm: ["PC", "GES", "LINGAM"]
    network: ["asia", "sachs"]
    sample_size: [100, 500]
  
  exclude:
    - algorithm: "LINGAM"
      network: "alarm"  # Remove specific combinations
  
  include:
    - algorithm: "PC"
      network: "asia"
      alpha: 0.01      # Add combinations with extra parameters
  
  fail_fast: false      # Continue other jobs if one fails
  max_parallel: 8       # Limit concurrent execution
```

### Matrix Strategy Implementation

```python
import itertools
from typing import Dict, List, Any

class CIMatrixStrategy:
    """Implement GitHub Actions matrix strategy within CI workflow engine."""
    
    def expand_matrix_strategy(self, strategy_config: Dict) -> List[Dict]:
        """
        Generate all job combinations from strategy.matrix configuration.
        
        This is part of the CI workflow engine, not a separate expansion system.
        
        Input:
          strategy:
            matrix:
              algorithm: ["PC", "GES", "LINGAM"]
              network: ["asia", "sachs"]
              sample_size: [100, 500]
        
        Output:
          12 jobs with all combinations of algorithm × network × sample_size
        """
        matrix_config = strategy_config.get("matrix", {})
        exclude_rules = strategy_config.get("exclude", [])
        include_rules = strategy_config.get("include", [])
        
        # Generate base cartesian product
        base_jobs = self._generate_base_combinations(matrix_config)
        
        # Apply exclude rules
        filtered_jobs = self._apply_exclude_rules(base_jobs, exclude_rules)
        
        # Apply include rules  
        final_jobs = self._apply_include_rules(filtered_jobs, include_rules)
        
        return final_jobs
```

### Advanced Matrix Features

```python
def apply_exclude_rules(self, jobs: List[Dict], exclude_rules: List[Dict]) -> List[Dict]:
    """
    Remove jobs matching exclude patterns.
    
    Example:
      exclude:
        - algorithm: "LINGAM"
          network: "alarm"  # Remove LINGAM + alarm combination
        - sample_size: 100
          algorithm: "GES"   # Remove GES + 100 sample size combination
    """
    filtered_jobs = []
    
    for job in jobs:
        should_exclude = False
        
        for exclude_rule in exclude_rules:
            if self._job_matches_pattern(job, exclude_rule):
                should_exclude = True
                break
        
        if not should_exclude:
            filtered_jobs.append(job)
    
    return filtered_jobs

def apply_include_rules(self, jobs: List[Dict], include_rules: List[Dict]) -> List[Dict]:
    """
    Add specific job combinations even if not in matrix.
    
    Example:
      include:
        - algorithm: "PC"
          network: "asia"
          sample_size: 50    # Add PC + asia + 50 even though 50 not in matrix
          alpha: 0.01        # Add extra parameter for this combination
    """
    extended_jobs = jobs.copy()
    
    for include_rule in include_rules:
        # Check if this combination already exists
        if not any(self._job_matches_pattern(job, include_rule) for job in jobs):
            extended_jobs.append(include_rule.copy())
    
    return extended_jobs

def _job_matches_pattern(self, job: Dict, pattern: Dict) -> bool:
    """Check if job matches the given pattern (all pattern keys must match)."""
    for key, value in pattern.items():
        if key not in job or job[key] != value:
            return False
    return True
```

## Template Substitution Engine

### Jinja2 Integration for Variable Substitution

```python
import jinja2
from typing import Dict, Any

class TemplateProcessor:
    """Handle GitHub Actions-style template substitution."""
    
    def __init__(self):
        # Configure Jinja2 with GitHub Actions syntax
        self.env = jinja2.Environment(
            variable_start_string="${{",
            variable_end_string="}}",
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def substitute_job_variables(self, template: str, job_context: Dict) -> str:
        """
        Process template with job-specific variables.
        
        Example:
          template: "network_${{ matrix.network }}_${{ matrix.sample_size }}.csv"
          job_context: {"matrix": {"network": "asia", "sample_size": 100}}
          result: "network_asia_100.csv"
        """
        jinja_template = self.env.from_string(template)
        return jinja_template.render(**job_context)
    
    def build_job_context(self, job: Dict, workflow_env: Dict, 
                         step_outputs: Dict = None) -> Dict:
        """
        Build complete context for template substitution.
        
        Available variables:
        - matrix.*: Matrix variables for current job
        - env.*: Environment variables
        - steps.*: Outputs from previous steps
        - github.*: GitHub Actions compatibility variables
        """
        context = {
            "matrix": job,
            "env": workflow_env,
            "github": {
                "workspace": "/tmp/causaliq-workspace",  # Configurable
                "run_id": "12345",  # Generated
                "run_number": "1"
            }
        }
        
        if step_outputs:
            context["steps"] = step_outputs
        
        return context
```

## Integration with DASK Task Graphs

### Job → DASK Task Conversion

```python
import dask
from typing import Dict, List, Callable

class DaskTaskGraphBuilder:
    """Convert matrix jobs into DASK computation graph."""
    
    def build_workflow_graph(self, jobs: List[Dict], 
                            workflow_definition: Dict) -> Dict:
        """
        Convert expanded matrix jobs into DASK task graph.
        
        Each job becomes a series of DASK tasks corresponding to workflow steps.
        Dependencies between steps are handled through DASK delayed mechanism.
        """
        graph = {}
        
        for job_idx, job in enumerate(jobs):
            job_id = f"job_{job_idx}"
            step_results = {}
            
            # Process each step in the workflow
            for step_idx, step in enumerate(workflow_definition["steps"]):
                step_id = f"{job_id}_step_{step_idx}"
                step_name = step.get("name", f"step_{step_idx}")
                
                # Build step task with dependencies
                step_task = self._build_step_task(
                    step=step,
                    job_context=job,
                    previous_results=step_results,
                    workflow_env=workflow_definition.get("env", {})
                )
                
                graph[step_id] = step_task
                step_results[step_name] = step_id
        
        return graph
    
    def _build_step_task(self, step: Dict, job_context: Dict, 
                        previous_results: Dict, workflow_env: Dict) -> tuple:
        """
        Build individual DASK task for workflow step.
        
        Returns tuple: (function, *args) suitable for DASK graph
        """
        action_name = step["uses"]
        action_inputs = step.get("with", {})
        
        # Substitute templates in action inputs
        template_processor = TemplateProcessor()
        full_context = template_processor.build_job_context(
            job=job_context,
            workflow_env=workflow_env,
            step_outputs=previous_results
        )
        
        substituted_inputs = {}
        for key, value in action_inputs.items():
            if isinstance(value, str):
                substituted_inputs[key] = template_processor.substitute_job_variables(
                    value, full_context
                )
            else:
                substituted_inputs[key] = value
        
        # Return DASK task tuple
        return (
            self._execute_action,
            action_name,
            substituted_inputs,
            job_context,
            previous_results
        )
    
    def _execute_action(self, action_name: str, inputs: Dict, 
                       job_context: Dict, previous_results: Dict) -> Any:
        """Execute workflow action with proper error handling."""
        from causaliq_workflow.actions import ActionRegistry
        
        registry = ActionRegistry()
        return registry.execute_action(action_name, inputs)
```

## Performance Optimisations

### Intelligent Job Batching

```python
class MatrixOptimiser:
    """Optimise matrix job execution for performance."""
    
    def batch_similar_jobs(self, jobs: List[Dict], max_batch_size: int = 10) -> List[List[Dict]]:
        """
        Group jobs by similarity for efficient resource usage.
        
        Jobs using same algorithm/package can share initialisation costs.
        Jobs using same dataset can share data loading costs.
        """
        batches = []
        
        # Group by algorithm package for shared initialisation
        algorithm_groups = {}
        for job in jobs:
            algorithm = job.get("algorithm", "unknown")
            if algorithm not in algorithm_groups:
                algorithm_groups[algorithm] = []
            algorithm_groups[algorithm].append(job)
        
        # Further group by dataset within each algorithm
        for algorithm, algo_jobs in algorithm_groups.items():
            dataset_groups = {}
            for job in algo_jobs:
                dataset = job.get("network", "unknown")
                if dataset not in dataset_groups:
                    dataset_groups[dataset] = []
                dataset_groups[dataset].append(job)
            
            # Create batches within each dataset group
            for dataset, dataset_jobs in dataset_groups.items():
                for i in range(0, len(dataset_jobs), max_batch_size):
                    batch = dataset_jobs[i:i + max_batch_size]
                    batches.append(batch)
        
        return batches
    
    def estimate_job_resources(self, job: Dict) -> Dict[str, Any]:
        """
        Estimate resource requirements for job.
        
        Used for intelligent DASK worker allocation.
        """
        algorithm = job.get("algorithm", "")
        sample_size = job.get("sample_size", 100)
        network_size = self._estimate_network_complexity(job.get("network", ""))
        
        # Simple heuristics - can be refined with benchmarking data
        memory_mb = max(500, sample_size * network_size * 0.1)
        cpu_time_minutes = max(1, (sample_size * network_size) / 10000)
        
        return {
            "memory_mb": memory_mb,
            "cpu_time_minutes": cpu_time_minutes,
            "io_intensive": algorithm.lower() in ["ges", "gies"],  # Score-based algorithms
            "cross_language": self._requires_cross_language_bridge(algorithm)
        }
```

## Integration with CI Workflow Engine

### Unified Architecture

The matrix strategy implementation is a core component of the unified CI workflow engine, not a separate system:

```python
class CIWorkflowEngine:
    """Unified CI workflow engine with integrated matrix strategy support."""
    
    def __init__(self):
        self.matrix_strategy = CIMatrixStrategy()
        self.template_processor = TemplateProcessor()
        self.action_registry = ActionRegistry()
        self.dask_builder = DaskTaskGraphBuilder()
    
    def execute_workflow(self, workflow_yaml: str) -> WorkflowResult:
        """Execute complete CI workflow with matrix strategy expansion."""
        workflow_def = self.parse_workflow(workflow_yaml)
        
        # Expand matrix strategy if present
        if "strategy" in workflow_def:
            jobs = self.matrix_strategy.expand_matrix_strategy(workflow_def["strategy"])
        else:
            jobs = [{}]  # Single job with empty context
        
        # Build DASK task graph for all jobs
        task_graph = self.dask_builder.build_workflow_graph(jobs, workflow_def)
        
        # Execute with DASK
        return self._execute_dask_graph(task_graph)
```

### Key Design Principles

1. **Unified System**: Matrix strategy is part of CI workflow engine, not separate component
2. **GitHub Actions Compatibility**: Full compatibility with GitHub Actions matrix syntax
3. **DASK Integration**: Matrix jobs convert directly to DASK task graph
4. **Template Support**: Full Jinja2 template substitution with `${{ matrix.variable }}` syntax
5. **Resource Management**: Matrix features like `max_parallel` map to DASK execution controls

This implementation provides the sophisticated matrix capabilities of GitHub Actions while maintaining the unified architecture of the CI workflow system for causal discovery research.