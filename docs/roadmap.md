# CausalIQ Workflow - Development Roadmap

**Last updated**: February 1, 2026

This project roadmap fits into the [overall ecosystem roadmap](https://causaliq.org/projects/ecosystem_roadmap/)

## 🚧  Under development

No release currently under development.

## ✅ Previous Releases

### Release v0.1.0 - Workflow Foundations (2026-02-01)

Framework for plug-in actions, basic workflow and CLI support

**Delivered**

- `causaliq-workflow run [--dry-run] <workflow>` CLI command
- `cqflow` short form command alias
- Auto-discovery plugin system with `CausalIQAction` base class
- YAML parsing, matrix expansion, step execution
- JSON Schema validation with clear error reporting
- Template variable validation for workflow files
- Support for Python 3.9, 3.10, 3.11, 3.12, and 3.13
- Comprehensive logging system
- 100% test coverage

*See Git commit history for detailed implementation progress*

## 🛣️ Upcoming Releases (speculative)

### Release v0.2.0 - Knowledge Workflows

Integrate with causaliq-knowledge generate_graph action

**Scope**

- support for causaliq-knowledge generate_graph action
- action always takes place
- available in causaliq-research
- support for lists in workflows

### Release v0.3.0 - Result Caching

Output action results and metadata store to the results cache.

**Scope**:

- caching of result graphs and metadata
- import/export of workflow caches (to .tetrad and .json formats)
- overwrites existing cached results

### Release 0.4.0 - Analysis Workflows

Graph averaging and structural analysis workflows

**Scope**:

- graph averaging integrated
- structural evaluation integrated
- other analysis integrated


### Release 0.5.0: Enhanced workflow

Dry and comparison runs, runtime estimation and processing summary

**Scope**:

- conservative execution skipping if results present
- dry-run capability
- standardise message format
- support skip, would do etc messages
- support comparison (integration test) functionality
- processing summary
- estimate runtime
- progress indicators


### Release 0.6: Discovery Integration

Structure learning algorithms integrated

**Scope**:

- causaliq-discovery algorithms integrated
- timeout supported


## 🚀 Possible Future Features

**External Algorithm Integration** (After robust test infrastructure):

- Multi-language workflows (R bnlearn, Java Tetrad, Python causal-learn)
- External CausalIQ package integration (discovery, analysis)
- Matrix-driven algorithm comparisons across datasets
- Automatic dataset download and preprocessing

**Production Features:****

- 📋 **Workflow queuing** - CI-style runner management
- 📊 **Monitoring dashboard** - Real-time execution tracking  
- 🗺 **Artifacts & caching** - Persistent storage, result reuse
- 🔒 **Security & isolation** - Secrets management, containers
- 📈 **Performance optimization** - Resource limits, scheduling

**Research Platform:**

- 🤖 **LLM integration** - Model averaging, hypothesis generation
- 🌐 **Web interface** - Browser-based workflow designer
- 🚀 **Cloud deployment** - AWS/GCP/Azure runners
- 👥 **Collaboration** - Multi-researcher workflows
- 📚 **Publication workflows** - Reproducible research outputs

**Advanced Capabilities:**

- **Workflow marketplace** - Sharing and discovering research workflow templates
- **Interactive notebooks** - Jupyter integration with workflow execution
- **Multi-machine execution** - Distributed workflows across compute clusters
- **AI-assisted optimization** - Automated hyperparameter and workflow tuning
- **Integration ecosystem** - Plugins for major research tools and platforms

---

*This roadmap leverages Git commit history for completed work, provides detailed
release-based planning for upcoming functionality, and outlines future possibilities.*