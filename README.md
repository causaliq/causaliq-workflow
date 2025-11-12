# causaliq-pipeline

[![Python Support](https://img.shields.io/pypi/pyversions/zenodo-sync.svg)](https://pypi.org/project/zenodo-sync/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**CI workflow-inspired orchestration for causal discovery experiments** within the [CausalIQ ecosystem](https://github.com/causaliq/causaliq). Coordinates causal discovery algorithms using GitHub Actions-style workflows executed via DASK.

## Revolutionary CI Workflow Architecture

� **Breakthrough Discovery**: We've adopted **GitHub Actions workflow patterns** for causal discovery experiments, transforming complex research workflows into familiar CI/CD syntax.

```yaml
name: "Algorithm Comparison"
strategy:
  matrix:
    algorithm: ["PC", "GES", "LINGAM"]
    network: ["asia", "sachs"]
    sample_size: [100, 500, 1000]
  exclude:
    - algorithm: "LINGAM"
      network: "alarm"
steps:
  - uses: "load-network@v1"
    with:
      network_name: "${{ matrix.network }}"
  - uses: "causal-discovery@v1"
    with:
      algorithm: "${{ matrix.algorithm }}"
```

## Status

🚧 **Phase 1 Development** - CI Workflow Foundation (~15% complete)

**Current Focus**: Implementing unified CI workflow engine with GitHub Actions schema integration, package-level algorithm registry, and action-based component library.

📋 **Complete roadmap and delivery specifications**: [docs/roadmap.md](docs/roadmap.md)

## Key Features

- **🎯 GitHub Actions Syntax**: Familiar CI/CD workflow patterns for causal discovery
- **📊 Matrix Strategy**: Advanced experiment combinations with exclude/include logic
- **🔧 Action Components**: Reusable, versioned workflow actions (`load-network@v1`, `causal-discovery@v1`)
- **🔌 Package Plugins**: Algorithm integration (bnlearn, Tetrad, causal-learn) via package-level plugins
- **⚡ DASK Execution**: Parallel execution with intelligent resource management

**See detailed architecture**: [docs/technical_architecture.md](docs/technical_architecture.md)

## Quick Start

### Prerequisites
- Python 3.9-3.12
- Git
- R with bnlearn (optional, for external integration)

### Installation
```bash
git clone https://github.com/causaliq/causaliq-pipeline.git
cd causaliq-pipeline

# Set up development environment
scripts/setup-env.ps1 -Install
scripts/activate.ps1 311
```

### Basic Usage
```bash
# Validate CI workflow configuration  
causaliq-pipeline validate algorithm_comparison.yaml

# Execute workflow (when implemented)
causaliq-pipeline run algorithm_comparison.yaml

# Monitor matrix job progress
causaliq-pipeline status workflow-123
```

**Example workflows**: [docs/example_workflows.md](docs/example_workflows.md)

## Documentation

- **[📋 Development Roadmap](docs/roadmap.md)** - Complete roadmap and delivery specifications
- **[🏗️ Technical Architecture](docs/technical_architecture.md)** - CI workflow engine design and core components
- **[⚙️ CI Workflow Implementation](docs/design/ci_workflow_implementation.md)** - Strategic design decisions and implementation approach
- **[📊 Matrix Strategy Design](docs/design/matrix_expansion_design.md)** - GitHub Actions matrix implementation details
- **[🔧 Action Architecture](docs/design/action_architecture_design.md)** - Versioned action component system
- **[🔌 Algorithm Registry](docs/design/algorithm_registry_design.md)** - Package-level plugin architecture

## CausalIQ Ecosystem Integration

Coordinates with:
- **causaliq-discovery**: Core algorithms (integrated as package plugins)
- **causaliq-llm**: LLM integration via action-based architecture
- **causaliq-analysis**: Statistical analysis actions and post-processing  
- **causaliq-experiments**: Configuration and result storage with CI workflow metadata

## Research Context

Supporting research for May 2026 paper on LLM integration for intelligent model averaging. The CI workflow architecture enables sophisticated experimental designs while maintaining familiar syntax for the research community.

**Migration target**: Existing workflows from monolithic discovery repo by end 2026.

## License

MIT License - see [LICENSE](LICENSE) file.

---

**Supported Python Versions**: 3.9, 3.10, 3.11, 3.12  
**Default Python Version**: 3.11
