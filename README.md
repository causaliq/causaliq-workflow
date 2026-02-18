
# causaliq-workflow

![Python Versions](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

**GitHub Actions-inspired workflow orchestration for causal discovery experiments** within the [CausalIQ ecosystem](https://github.com/causaliq/causaliq). Execute causal discovery workflows using familiar CI/CD patterns with conservative execution and comprehensive action framework.

## Status

🚧 **Active Development** - This repository is currently in active development, which involves:

- migrating functionality from the legacy monolithic [discovery repo](https://github.com/causaliq/discovery) to support legacy experiments and analysis
- ensure CausalIQ development standards are met
- adding new features to provide a comprehensive, open, causal discovery workflow.


## Features

✅ **Implemented Releases**

- **Release v0.1.0 - Workflow Foundations**: Plug-in actions, basic workflow
  and CLI support, 100% test coverage

- **Release v0.2.0 - Knowledge Workflows**: Integrate with causaliq-knowledge
  generate_graph action and write results to workflow caches.

*See Git commit history for detailed implementation progress*

🛣️ Upcoming Releases


- **Release v0.3.0 - Analysis Workflows**: Graph averaging and structural
  analysis workflows.
- **Release v0.4.0 - Enhanced Workflow**: Dry and comparison runs, runtime
  estimation and processing summary
- **Release v0.5.0 - Discovery Workflows**: Structure learning algorithms
  integrated

## causaliq-core Integration

causaliq-workflow builds on causaliq-core for its action framework and caching
infrastructure:

- **CausalIQActionProvider** - Base class for all action providers
- **ActionInput/ActionResult** - Type-safe action interfaces
- **ActionValidationError/ActionExecutionError** - Exception handling
- **TokenCache/JsonCompressor** - SQLite-based caching with JSON tokenisation


## Brief Example Usage

**Example Workflow Definition**, experiment.yml:

```yaml
description: "Causal Discovery Experiment"
id: "experiment-001"
workflow_cache: "results/{{id}}_cache.db"  # All results stored here

matrix:
  network: ["asia", "cancer"]
  algorithm: ["pc", "ges"]
  sample_size: ["100", "1K"]

steps:
  - name: "Structure Learning"
    uses: "causaliq-discovery"
    with:
      algorithm: "{{algorithm}}"
      sample_size: "{{sample_size}}"
      dataset: "data/{{network}}"
      # Results cached with key: {network, algorithm, sample_size}
```

**Execute with modes:**
```bash
cqflow experiment.yml --mode=dry-run    # Validate and preview (default)
cqflow experiment.yml --mode=run        # Execute (skip if outputs exist)
cqflow experiment.yml --mode=compare    # Re-execute and compare outputs
```

Note that **cqflow** is a short synonym for **causaliq-workflow** which can also be used.


## Upcoming Key Innovations

### 🔄 Workflow Orchestration

- Continuous Integration (CI) testing: Workflow specification syntax
- Dask distributed computing: Scalable parallel processing
- Dependency management: Automatic handling of data and processing dependencies
- Error recovery: Robust handling of failures and restarts

### 📊 Experiment Management

- Configuration management: YAML-based experiment specifications
- Parameter sweeps: Systematic exploration of algorithm parameters
- Version control: Git-based tracking of experiments and results
- Reproducibility: Deterministic execution with seed management

## Integration with CausalIQ Ecosystem

- 🔍 **CausalIQ Discovery** is called by this package to perform structure learning.
- 📊 **CausalIQ Analysis** is called by this package to perform results analysis and generate assets for research papers.
- 🔮 **CausalIQ Predict** is called by this package to perform causal prediction.
- 🔄 **Zenodo Synchronisation** is used by this package to download datasets and upload results.
- 🧪 **CausalIQ Papers** are defined in terms of CausalIQ Workflows allowing the reproduction of experiments, results and published paper assets created by the CausalIQ ecosystem.

## LLM Support

The following provides project-specific context for this repo which should be provided after the [personal and ecosystem context](https://github.com/causaliq/causaliq/blob/main/LLM_DEVELOPMENT_GUIDE.md):

```text
tbc
```

### Prerequisites
- Python 3.9-3.13
- Git
- R with bnlearn (optional, for external integration)

### Installation
```bash
git clone https://github.com/causaliq/causaliq-workflow.git
cd causaliq-workflow

# Set up development environment
scripts/setup-env.ps1 -Install
scripts/activate.ps1
```

**Example workflows**: [docs/example_workflows.md](docs/example_workflows.md)



## Research Context

Supporting research for May 2026 paper on LLM integration for intelligent model averaging. The CI workflow architecture enables sophisticated experimental designs while maintaining familiar syntax for the research community.

**Migration target**: Existing workflows from monolithic discovery repo by end 2026.

## Quick Start

```python
# to be completed
```

## Getting started

### Prerequisites

- Git 
- Latest stable versions of Python 3.9, 3.10. 3.11 and 3.12


### Clone the new repo locally and check that it works

Clone the causaliq-analysis repo locally as normal

```bash
git clone https://github.com/causaliq/causaliq-analysis.git
```

Set up the Python virtual environments and activate the default Python virtual environment. You may see
messages from VSCode (if you are using it as your IDE) that new Python environments are being created
as the scripts/setup-env runs - these messages can be safely ignored at this stage.

```text
scripts/setup-env -Install
scripts/activate
```

Check that the causaliq-analysis CLI is working, check that all CI tests pass, and start up the local mkdocs webserver. There should be no errors  reported in any of these.

```text
causaliq-analysis --help
scripts/check_ci
mkdocs serve
```

Enter **http://127.0.0.1:8000/** in a browser and check that the 
causaliq-data documentation is visible.

If all of the above works, this confirms that the code is working successfully on your system.


## Documentation

Full API documentation is available at: **http://127.0.0.1:8000/** (when running `mkdocs serve`)

## Contributing

This repository is part of the CausalIQ ecosystem. For development setup:

1. Clone the repository
2. Run `scripts/setup-env -Install` to set up environments  
3. Run `scripts/check_ci` to verify all tests pass
4. Start documentation server with `mkdocs serve`

---

**Supported Python Versions**: 3.9, 3.10, 3.11, 3.12, 3.13
**Default Python Version**: 3.11  
**License**: MIT
