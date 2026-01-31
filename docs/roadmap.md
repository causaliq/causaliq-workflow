# CausalIQ Workflow - Development Roadmap

**Last updated**: January 30, 2026

This project roadmap fits into the [overall ecosystem roadmap](https://causaliq.org/projects/ecosystem_roadmap/)

## 🚧  Under development

### Release v0.1.0 - Foundation Actions

Framework for plug-in actions, basic workflow and CLI support

**Scope**

- `causaliq-workflow run [--dry-run] <workflow>`
- Auto-discovery plugin system
- YAML parsing, matrix expansion, step execution
- JSON Schema with error reporting
- support Python v3.13

**Implementation Plan**

*Commit 1: support Python v3.13* ✅

- add v3.13 venv and CI testing

*Commit 2: cqflow short form command supported* ✅

- support cqflow short command
- update license specification

*Commit 3: refactor so base action class is named CausalIQAction. ✅

- refactor base interface class name from Action to CausalIQAction
- rename 

*Commit 4: documentation ready for release*

- include copilot instructions
- ensure documentation up to date

*See Git commit history for detailed implementation progress*

## ✅ Previous Releases

None

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