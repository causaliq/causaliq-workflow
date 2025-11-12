# Action-Based Component Architecture

## Overview

The action-based architecture provides reusable, version-controlled workflow components following GitHub Actions patterns. Actions encapsulate common causal discovery operations with standardised inputs, outputs, and error handling.

## Core Action Framework

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

class Action(ABC):
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

### Action Registry and Versioning

```python
import importlib
import pkg_resources
from typing import Dict, List, Optional

class ActionRegistry:
    """Manage registration and execution of workflow actions."""
    
    def __init__(self):
        self._actions: Dict[str, Dict[str, Action]] = {}  # name -> version -> action
        self._load_builtin_actions()
        self._discover_plugin_actions()
    
    def register_action(self, action: Action) -> None:
        """Register action with version management."""
        name = action.name
        version = action.version
        
        if name not in self._actions:
            self._actions[name] = {}
        
        self._actions[name][version] = action
        
        # Validate semantic versioning
        try:
            semantic_version.Version(version)
        except ValueError as e:
            raise ValueError(f"Invalid semantic version '{version}' for action '{name}': {e}")
    
    def get_action(self, action_ref: str) -> Action:
        """
        Get action by reference: 'action-name@v1.2.3' or 'action-name@latest'
        
        Examples:
        - load-network@v1.0.0
        - load-network@latest  
        - causal-discovery@v2.1.0
        """
        if "@" in action_ref:
            name, version_spec = action_ref.split("@", 1)
        else:
            name, version_spec = action_ref, "latest"
        
        if name not in self._actions:
            raise ValueError(f"Unknown action: {name}")
        
        available_versions = self._actions[name]
        
        if version_spec == "latest":
            # Get highest semantic version
            versions = [semantic_version.Version(v) for v in available_versions.keys()]
            latest_version = str(max(versions))
            return available_versions[latest_version]
        
        if version_spec in available_versions:
            return available_versions[version_spec]
        
        # Try semantic version matching (e.g., ^1.0.0 matches 1.x.x)
        spec = semantic_version.Spec(version_spec)
        compatible_versions = []
        
        for version_str in available_versions.keys():
            version = semantic_version.Version(version_str)
            if spec.match(version):
                compatible_versions.append((version, version_str))
        
        if compatible_versions:
            # Get highest compatible version
            latest_compatible = max(compatible_versions)[1]
            return available_versions[latest_compatible]
        
        raise ValueError(f"No compatible version found for {action_ref}")
    
    def execute_action(self, action_ref: str, inputs: Dict[str, Any]) -> Dict[str, ActionOutput]:
        """Execute action with input validation and output formatting."""
        action = self.get_action(action_ref)
        
        # Validate inputs
        validated_inputs = action.validate_inputs(inputs)
        
        try:
            # Execute action
            raw_outputs = action.run(validated_inputs)
            
            # Format outputs
            return action.format_outputs(raw_outputs)
            
        except Exception as e:
            raise RuntimeError(f"Action {action_ref} failed: {str(e)}") from e
```

## Core Causal Discovery Actions

### Data Loading Actions

```python
import pandas as pd
import numpy as np
from pathlib import Path

class LoadNetworkAction(Action):
    """Load causal network dataset from various sources."""
    
    name = "load-network"
    version = "1.0.0"
    description = "Load causal network dataset with optional transformations"
    
    inputs = {
        "network_name": ActionInput("network_name", "Name of the network to load", required=True),
        "source": ActionInput("source", "Data source", default="zenodo"),
        "sample_size": ActionInput("sample_size", "Number of samples to generate", type_hint="int"),
        "random_seed": ActionInput("random_seed", "Random seed for reproducibility", default=42),
        "add_noise": ActionInput("add_noise", "Add Gaussian noise to continuous variables", default=False),
        "noise_level": ActionInput("noise_level", "Standard deviation of noise", default=0.1)
    }
    
    outputs = {
        "dataset": "Pandas DataFrame with network data",
        "true_graph": "NetworkX DiGraph representing true causal structure",
        "metadata": "Dataset metadata including source, transformations applied"
    }
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Load network data with optional transformations."""
        network_name = inputs["network_name"]
        source = inputs["source"]
        sample_size = inputs.get("sample_size")
        random_seed = inputs["random_seed"]
        
        # Set random seed for reproducibility
        np.random.seed(random_seed)
        
        # Load network from source
        if source == "zenodo":
            dataset, true_graph = self._load_from_zenodo(network_name)
        elif source == "bnlearn":
            dataset, true_graph = self._load_from_bnlearn(network_name)
        elif source == "local":
            dataset, true_graph = self._load_from_local(network_name)
        else:
            raise ValueError(f"Unsupported data source: {source}")
        
        # Apply transformations
        if sample_size and sample_size != len(dataset):
            dataset = self._resample_dataset(dataset, sample_size)
        
        if inputs.get("add_noise", False):
            dataset = self._add_noise(dataset, inputs["noise_level"])
        
        metadata = {
            "network_name": network_name,
            "source": source,
            "original_size": len(dataset),
            "sample_size": sample_size or len(dataset),
            "noise_added": inputs.get("add_noise", False),
            "random_seed": random_seed
        }
        
        return {
            "dataset": dataset,
            "true_graph": true_graph,
            "metadata": metadata
        }
    
    def _load_from_zenodo(self, network_name: str) -> tuple:
        """Load network from Zenodo repository."""
        # Implementation would use zenodo API or cached files
        # For now, placeholder that loads from local cache
        return self._load_from_local(network_name)
    
    def _load_from_bnlearn(self, network_name: str) -> tuple:
        """Load network using R bnlearn package."""
        try:
            import rpy2.robjects as ro
            from rpy2.robjects import pandas2ri
            pandas2ri.activate()
            
            # Load bnlearn
            ro.r('library(bnlearn)')
            
            # Load network structure and data
            ro.r(f'data({network_name})')
            data_r = ro.r(network_name)
            dataset = pandas2ri.rpy2py(data_r)
            
            # Load true graph if available
            try:
                ro.r(f'net <- {network_name}.net')
                # Convert bnlearn network to NetworkX
                true_graph = self._convert_bnlearn_to_networkx(ro.r('net'))
            except:
                true_graph = None
            
            return dataset, true_graph
            
        except ImportError:
            raise RuntimeError("rpy2 not available - cannot load from bnlearn")
    
    def _load_from_local(self, network_name: str) -> tuple:
        """Load network from local files."""
        # Implementation would load from data directory
        # Placeholder for now
        raise NotImplementedError(f"Local loading for {network_name} not implemented")

class RandomiseDataAction(Action):
    """Apply randomisation strategies to dataset."""
    
    name = "randomise-data"
    version = "1.0.0"
    description = "Apply various randomisation strategies to causal data"
    
    inputs = {
        "dataset": ActionInput("dataset", "Input dataset", required=True),
        "strategy": ActionInput("strategy", "Randomisation strategy", required=True),
        "random_seed": ActionInput("random_seed", "Random seed", default=42)
    }
    
    outputs = {
        "randomised_dataset": "Dataset with randomisation applied",
        "transformation_log": "Log of transformations applied"
    }
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Apply randomisation strategy."""
        dataset = inputs["dataset"]
        strategy = inputs["strategy"]
        np.random.seed(inputs["random_seed"])
        
        transformation_log = []
        
        if strategy == "row_shuffle":
            randomised = dataset.sample(frac=1.0).reset_index(drop=True)
            transformation_log.append("Shuffled row order")
            
        elif strategy == "column_shuffle":
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

class CausalDiscoveryAction(Action):
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
            pandas2ri.activate()
            
            # Transfer data to R
            ro.r('library(bnlearn)')
            ro.globalenv['data'] = data
            
            # Build parameter string
            param_str = self._build_bnlearn_params(parameters)
            
            # Execute algorithm
            cmd = f"learned_net <- {algorithm}(data{param_str})"
            ro.r(cmd)
            
            # Convert result to NetworkX
            learned_graph = self._convert_bnlearn_to_networkx(ro.r('learned_net'))
            
            algo_info = {
                "package": "bnlearn",
                "algorithm": algorithm,
                "parameters": parameters,
                "command": cmd
            }
            
            return learned_graph, algo_info
            
        except Exception as e:
            raise RuntimeError(f"bnlearn execution failed: {str(e)}") from e
```

### Evaluation and Comparison Actions

```python
class EvaluateGraphAction(Action):
    """Evaluate learned graph against true graph."""
    
    name = "evaluate-graph"
    version = "1.0.0"
    description = "Compute accuracy metrics for learned causal graph"
    
    inputs = {
        "learned_graph": ActionInput("learned_graph", "Learned causal graph", required=True),
        "true_graph": ActionInput("true_graph", "True causal graph", required=True),
        "metrics": ActionInput("metrics", "Metrics to compute", default=["shd", "precision", "recall", "f1"])
    }
    
    outputs = {
        "metrics": "Dictionary of computed metrics",
        "confusion_matrix": "Edge-level confusion matrix",
        "edge_analysis": "Detailed edge-by-edge comparison"
    }
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Compute evaluation metrics."""
        learned = inputs["learned_graph"]
        true = inputs["true_graph"]
        metric_names = inputs["metrics"]
        
        # Compute confusion matrix at edge level
        confusion = self._compute_edge_confusion_matrix(learned, true)
        
        # Compute requested metrics
        metrics = {}
        
        if "shd" in metric_names:
            metrics["shd"] = self._compute_shd(learned, true)
        
        if "precision" in metric_names:
            metrics["precision"] = confusion["tp"] / (confusion["tp"] + confusion["fp"]) if confusion["tp"] + confusion["fp"] > 0 else 0.0
        
        if "recall" in metric_names:
            metrics["recall"] = confusion["tp"] / (confusion["tp"] + confusion["fn"]) if confusion["tp"] + confusion["fn"] > 0 else 0.0
        
        if "f1" in metric_names:
            p, r = metrics.get("precision", 0), metrics.get("recall", 0)
            metrics["f1"] = 2 * p * r / (p + r) if p + r > 0 else 0.0
        
        # Detailed edge analysis
        edge_analysis = self._analyse_edge_differences(learned, true)
        
        return {
            "metrics": metrics,
            "confusion_matrix": confusion,
            "edge_analysis": edge_analysis
        }
```

This action-based architecture provides a flexible, version-controlled foundation for building complex causal discovery workflows with reusable components and standardised interfaces.