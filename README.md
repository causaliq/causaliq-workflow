# causaliq-pipeline

[![Python Support](https://img.shields.io/pypi/pyversions/zenodo-sync.svg)](https://pypi.org/project/zenodo-sync/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**GitHub Actions-inspired workflow orchestration for causal discovery experiments** within the [CausalIQ ecosystem](https://github.com/causaliq/causaliq). Execute causal discovery workflows using familiar CI/CD patterns with comprehensive action framework.

## Current Implementation (v0.1.0)

✅ **Action Framework Foundation Complete** - Robust workflow orchestration with 100% test coverage

```yaml
name: "Causal Discovery Experiment"
id: "experiment-001"
data_root: "/data"
output_root: "/results"

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

## Implementation Status

� **Phase 1: Action Framework Foundation** - ✅ 75% Complete (47/47 tests passing)

**Completed Features**:
- ✅ **Action Framework**: Type-safe action base classes with comprehensive error handling
- ✅ **Schema Validation**: GitHub Actions-inspired workflow syntax with matrix support
- ✅ **GraphML Output**: Standardized causal graph representation format
- ✅ **Test Coverage**: 100% coverage across unit, functional, and integration tests
- ✅ **Reference Implementation**: DummyStructureLearnerAction demonstrating framework

📋 **Complete progress tracking**: [docs/roadmap.md](docs/roadmap.md)

## Key Features

- **🎯 GitHub Actions Syntax**: Familiar workflow patterns adapted for causal discovery
- **📊 Matrix Variables**: Parameterized experiments with `data_root` and `output_root` path construction
- **🔧 Action Components**: Reusable, versioned workflow actions with type-safe interfaces
- **� GraphML Standard**: Consistent causal graph representation (DAGs, PDAGs, CPDAGs, MAGs, PAGs)
- **🧪 Comprehensive Testing**: Unit, functional, and integration tests with tracked test data

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
