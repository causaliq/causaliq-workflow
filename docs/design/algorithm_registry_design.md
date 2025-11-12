# Algorithm Registry Design

## Overview

The algorithm registry implements a **package-level plugin architecture** rather than individual algorithm plugins. This approach provides better maintainability, cross-language bridge management, and automatic algorithm discovery from major causal discovery packages.

## Package-Level Plugin Architecture

### Core Design Principle

Instead of creating individual plugins for each algorithm (PC, GES, LINGAM, etc.), we create plugins for algorithm **packages** (bnlearn, Tetrad, causal-learn). This design provides several advantages:

- **Simplified maintenance**: One plugin per package instead of dozens per algorithm
- **Automatic algorithm discovery**: Packages expose their available algorithms dynamically
- **Better resource management**: Package-level initialisation and cleanup
- **Cross-language bridge efficiency**: Shared R/Java connections across algorithms

### Algorithm Registry Architecture

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import pandas as pd
import networkx as nx

class AlgorithmPackage(ABC):
    """Base class for algorithm package plugins."""
    
    @property
    @abstractmethod
    def package_name(self) -> str:
        """Return package name (e.g., 'bnlearn', 'tetrad', 'causal-learn')."""
        pass
    
    @property
    @abstractmethod
    def supported_algorithms(self) -> List[str]:
        """Return list of supported algorithm names."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if package is available and properly configured."""
        pass
    
    @abstractmethod
    def execute_algorithm(self, algorithm: str, data: pd.DataFrame, 
                         parameters: Dict[str, Any]) -> nx.DiGraph:
        """Execute specified algorithm with given data and parameters."""
        pass
    
    @abstractmethod
    def get_algorithm_info(self, algorithm: str) -> Dict[str, Any]:
        """Get metadata about specific algorithm (parameters, constraints, etc.)."""
        pass
    
    def validate_data(self, data: pd.DataFrame, algorithm: str) -> bool:
        """Validate that data is compatible with algorithm."""
        return True  # Default: accept all data
    
    def preprocess_data(self, data: pd.DataFrame, algorithm: str) -> pd.DataFrame:
        """Package-specific data preprocessing."""
        return data  # Default: no preprocessing

class AlgorithmRegistry:
    """Central registry for algorithm packages."""
    
    def __init__(self):
        self._packages: Dict[str, AlgorithmPackage] = {}
        self._algorithm_map: Dict[str, str] = {}  # algorithm -> package_name
        self._discover_packages()
    
    def register_package(self, package: AlgorithmPackage) -> None:
        """Register an algorithm package."""
        package_name = package.package_name
        
        if not package.is_available():
            raise RuntimeError(f"Package {package_name} is not available")
        
        self._packages[package_name] = package
        
        # Update algorithm mapping
        for algorithm in package.supported_algorithms:
            if algorithm in self._algorithm_map:
                # Handle conflicts - prefer certain packages
                existing_package = self._algorithm_map[algorithm]
                preferred = self._resolve_package_preference(algorithm, existing_package, package_name)
                self._algorithm_map[algorithm] = preferred
            else:
                self._algorithm_map[algorithm] = package_name
    
    def execute_algorithm(self, algorithm: str, data: pd.DataFrame, 
                         parameters: Dict[str, Any] = None, 
                         preferred_package: str = None) -> AlgorithmResult:
        """Execute algorithm using best available package."""
        parameters = parameters or {}
        
        # Determine which package to use
        if preferred_package and preferred_package in self._packages:
            package_name = preferred_package
        elif algorithm in self._algorithm_map:
            package_name = self._algorithm_map[algorithm]
        else:
            raise ValueError(f"Algorithm '{algorithm}' not available in any registered package")
        
        package = self._packages[package_name]
        
        # Validate data compatibility
        if not package.validate_data(data, algorithm):
            raise ValueError(f"Data incompatible with {algorithm} in {package_name}")
        
        # Preprocess data
        processed_data = package.preprocess_data(data, algorithm)
        
        # Execute algorithm
        start_time = time.time()
        try:
            learned_graph = package.execute_algorithm(algorithm, processed_data, parameters)
            execution_time = time.time() - start_time
            
            return AlgorithmResult(
                algorithm=algorithm,
                package=package_name,
                learned_graph=learned_graph,
                execution_time=execution_time,
                parameters=parameters,
                data_info={
                    "num_variables": len(data.columns),
                    "num_samples": len(data),
                    "variable_names": list(data.columns)
                }
            )
            
        except Exception as e:
            raise RuntimeError(f"Algorithm {algorithm} failed in {package_name}: {str(e)}") from e
    
    def get_available_algorithms(self) -> Dict[str, List[str]]:
        """Get all available algorithms grouped by package."""
        result = {}
        for package_name, package in self._packages.items():
            result[package_name] = package.supported_algorithms
        return result
    
    def _discover_packages(self) -> None:
        """Automatically discover and register available packages."""
        # Try to register each known package
        package_classes = [
            BnlearnPackage,
            TetradPackage,
            CausalLearnPackage,
            PcalgorithmPackage  # R pcalgorithm package
        ]
        
        for package_class in package_classes:
            try:
                package = package_class()
                if package.is_available():
                    self.register_package(package)
            except Exception:
                # Package not available or failed to initialise
                continue
```

## Specific Package Implementations

### R bnlearn Package

```python
import warnings
from typing import Dict, List, Any
import pandas as pd
import networkx as nx

class BnlearnPackage(AlgorithmPackage):
    """R bnlearn package integration via rpy2."""
    
    def __init__(self):
        self._r_session = None
        self._initialise_r()
    
    @property
    def package_name(self) -> str:
        return "bnlearn"
    
    @property
    def supported_algorithms(self) -> List[str]:
        return [
            "pc", "iamb", "fast.iamb", "inter.iamb", 
            "gs", "mmpc", "si.hiton.pc", "hpc",
            "chow.liu", "aracne", "hc", "tabu"
        ]
    
    def is_available(self) -> bool:
        """Check R and bnlearn availability."""
        try:
            import rpy2.robjects as ro
            ro.r('library(bnlearn)')
            return True
        except (ImportError, Exception):
            return False
    
    def execute_algorithm(self, algorithm: str, data: pd.DataFrame, 
                         parameters: Dict[str, Any]) -> nx.DiGraph:
        """Execute bnlearn algorithm."""
        import rpy2.robjects as ro
        from rpy2.robjects import pandas2ri
        pandas2ri.activate()
        
        # Transfer data to R
        ro.globalenv['causal_data'] = data
        
        # Build parameter string for R function call
        param_str = self._build_r_parameters(parameters)
        
        # Execute algorithm
        if algorithm in ["pc", "iamb", "fast.iamb", "inter.iamb", "gs", "mmpc"]:
            # Constraint-based algorithms
            ro.r(f"learned_net <- {algorithm}(causal_data{param_str})")
        elif algorithm in ["hc", "tabu"]:
            # Score-based algorithms
            ro.r(f"learned_net <- {algorithm}(causal_data{param_str})")
        else:
            raise ValueError(f"Unknown bnlearn algorithm: {algorithm}")
        
        # Convert bnlearn network to NetworkX
        return self._convert_bnlearn_to_networkx(ro.r('learned_net'))
    
    def get_algorithm_info(self, algorithm: str) -> Dict[str, Any]:
        """Get bnlearn algorithm information."""
        algorithm_info = {
            "pc": {
                "type": "constraint-based",
                "parameters": ["alpha", "test"],
                "data_types": ["mixed", "continuous", "discrete"],
                "default_alpha": 0.05
            },
            "ges": {
                "type": "score-based", 
                "parameters": ["score", "lambda"],
                "data_types": ["continuous"],
                "default_score": "bic-g"
            },
            "hc": {
                "type": "score-based",
                "parameters": ["score", "restart", "perturb"],
                "data_types": ["mixed", "continuous", "discrete"],
                "default_score": "bic"
            }
        }
        
        return algorithm_info.get(algorithm, {"type": "unknown"})
    
    def validate_data(self, data: pd.DataFrame, algorithm: str) -> bool:
        """Validate data for bnlearn algorithms."""
        # Check for missing values
        if data.isnull().any().any():
            return False
        
        # Algorithm-specific validation
        if algorithm == "ges":
            # GES requires continuous data
            return all(pd.api.types.is_numeric_dtype(data[col]) for col in data.columns)
        
        return True
    
    def preprocess_data(self, data: pd.DataFrame, algorithm: str) -> pd.DataFrame:
        """Preprocess data for bnlearn."""
        processed = data.copy()
        
        # Convert categorical strings to factors for R
        for col in processed.columns:
            if processed[col].dtype == 'object':
                processed[col] = processed[col].astype('category')
        
        return processed
    
    def _initialise_r(self) -> None:
        """Initialise R session."""
        try:
            import rpy2.robjects as ro
            ro.r('library(bnlearn)')
            # Set up any global R settings
            ro.r('options(warn=-1)')  # Suppress R warnings
        except Exception as e:
            raise RuntimeError(f"Failed to initialise R session: {e}")
    
    def _build_r_parameters(self, parameters: Dict[str, Any]) -> str:
        """Build R function parameter string."""
        if not parameters:
            return ""
        
        param_parts = []
        for key, value in parameters.items():
            if isinstance(value, str):
                param_parts.append(f'{key}="{value}"')
            else:
                param_parts.append(f'{key}={value}')
        
        return ", " + ", ".join(param_parts)
    
    def _convert_bnlearn_to_networkx(self, bnlearn_net) -> nx.DiGraph:
        """Convert bnlearn network to NetworkX DiGraph."""
        import rpy2.robjects as ro
        
        # Get arc matrix from bnlearn
        ro.r('arc_matrix <- arcs(learned_net)')
        arc_matrix = ro.r('arc_matrix')
        
        # Convert to NetworkX
        graph = nx.DiGraph()
        
        # Add nodes (get node names from bnlearn network)
        ro.r('node_names <- names(learned_net$nodes)')
        nodes = list(ro.r('node_names'))
        graph.add_nodes_from(nodes)
        
        # Add edges from arc matrix
        if arc_matrix is not None:
            for i in range(arc_matrix.nrow):
                from_node = str(arc_matrix.rx(i+1, 1)[0])
                to_node = str(arc_matrix.rx(i+1, 2)[0])
                graph.add_edge(from_node, to_node)
        
        return graph
```

### Python causal-learn Package

```python
class CausalLearnPackage(AlgorithmPackage):
    """Python causal-learn package direct integration."""
    
    @property
    def package_name(self) -> str:
        return "causal-learn"
    
    @property  
    def supported_algorithms(self) -> List[str]:
        return [
            "pc", "ges", "lingam", "direct-lingam", "ica-lingam",
            "fci", "rfci", "gfci", "cdnod", "gds"
        ]
    
    def is_available(self) -> bool:
        """Check causal-learn availability."""
        try:
            import causallearn
            return True
        except ImportError:
            return False
    
    def execute_algorithm(self, algorithm: str, data: pd.DataFrame, 
                         parameters: Dict[str, Any]) -> nx.DiGraph:
        """Execute causal-learn algorithm."""
        import numpy as np
        
        # Convert to numpy for causal-learn
        data_array = data.values
        
        if algorithm == "pc":
            from causallearn.search.ConstraintBased.PC import pc
            alpha = parameters.get("alpha", 0.05)
            cg = pc(data_array, alpha=alpha)
            return self._convert_causallearn_to_networkx(cg.G, data.columns)
            
        elif algorithm == "ges":
            from causallearn.search.ScoreBased.GES import ges
            score_func = parameters.get("score_func", "local_score_BIC")
            record = ges(data_array, score_func=score_func)
            return self._convert_causallearn_to_networkx(record['G'], data.columns)
            
        elif algorithm == "lingam":
            from causallearn.search.FCMBased import lingam
            model = lingam.DirectLiNGAM()
            model.fit(data_array)
            return self._convert_adjacency_to_networkx(model.adjacency_matrix_, data.columns)
            
        else:
            raise ValueError(f"Algorithm {algorithm} not implemented in causal-learn package")
    
    def validate_data(self, data: pd.DataFrame, algorithm: str) -> bool:
        """Validate data for causal-learn algorithms."""
        # Check for missing values
        if data.isnull().any().any():
            return False
        
        # Most causal-learn algorithms require numeric data
        if not all(pd.api.types.is_numeric_dtype(data[col]) for col in data.columns):
            return False
        
        return True
    
    def _convert_causallearn_to_networkx(self, causal_matrix, variable_names) -> nx.DiGraph:
        """Convert causal-learn result to NetworkX."""
        graph = nx.DiGraph()
        graph.add_nodes_from(variable_names)
        
        # causal-learn uses different matrix formats
        for i in range(len(variable_names)):
            for j in range(len(variable_names)):
                if causal_matrix[i, j] == 1:  # Directed edge
                    graph.add_edge(variable_names[i], variable_names[j])
                    
        return graph
```

### Java Tetrad Package

```python
class TetradPackage(AlgorithmPackage):
    """Java Tetrad package integration via py4j."""
    
    def __init__(self):
        self._gateway = None
        self._initialise_java()
    
    @property
    def package_name(self) -> str:
        return "tetrad"
    
    @property
    def supported_algorithms(self) -> List[str]:
        return [
            "pc", "cpc", "ges", "fges", "gfci", 
            "fas", "rfci", "cfci", "svarfci"
        ]
    
    def is_available(self) -> bool:
        """Check Java and Tetrad availability."""
        try:
            import subprocess
            result = subprocess.run(['java', '-version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def execute_algorithm(self, algorithm: str, data: pd.DataFrame, 
                         parameters: Dict[str, Any]) -> nx.DiGraph:
        """Execute Tetrad algorithm via Java bridge."""
        if self._gateway is None:
            raise RuntimeError("Java gateway not initialised")
        
        # Convert pandas to Java data structure
        tetrad_data = self._convert_to_tetrad_data(data)
        
        # Execute algorithm
        if algorithm == "pc":
            alpha = parameters.get("alpha", 0.05)
            search = self._gateway.jvm.edu.cmu.tetrad.search.Pc(tetrad_data)
            search.setAlpha(alpha)
            result_graph = search.search()
            
        elif algorithm == "ges":
            score = self._gateway.jvm.edu.cmu.tetrad.search.score.BicScore(tetrad_data)
            search = self._gateway.jvm.edu.cmu.tetrad.search.Ges(score)
            result_graph = search.search()
            
        else:
            raise ValueError(f"Algorithm {algorithm} not implemented in Tetrad package")
        
        # Convert result back to NetworkX
        return self._convert_tetrad_to_networkx(result_graph, data.columns)
    
    def _initialise_java(self) -> None:
        """Initialise Java gateway for Tetrad."""
        try:
            from py4j.java_gateway import JavaGateway
            self._gateway = JavaGateway()
            # Test connection
            self._gateway.jvm.System.currentTimeMillis()
        except Exception as e:
            raise RuntimeError(f"Failed to initialise Java gateway: {e}")
```

## Algorithm Resolution Strategy

### Package Preference Order

When multiple packages support the same algorithm, the registry uses preference rules:

```python
def _resolve_package_preference(self, algorithm: str, existing_package: str, new_package: str) -> str:
    """Resolve conflicts when multiple packages support same algorithm."""
    
    # Define preference order for common algorithms
    preferences = {
        "pc": ["bnlearn", "causal-learn", "tetrad"],  # Prefer bnlearn for PC
        "ges": ["causal-learn", "tetrad", "bnlearn"], # Prefer causal-learn for GES
        "lingam": ["causal-learn"],                   # Only causal-learn supports LiNGAM
        "hc": ["bnlearn"],                            # Only bnlearn supports HC
    }
    
    if algorithm in preferences:
        preference_order = preferences[algorithm]
        
        existing_idx = preference_order.index(existing_package) if existing_package in preference_order else 999
        new_idx = preference_order.index(new_package) if new_package in preference_order else 999
        
        return existing_package if existing_idx < new_idx else new_package
    
    # Default: keep existing
    return existing_package
```

This package-level approach provides a clean, maintainable foundation for supporting the diverse ecosystem of causal discovery algorithms while handling cross-language integration complexities efficiently.