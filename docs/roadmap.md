# CausalIQ Workflow - Development Roadmap

**Last updated**: February 18, 2026

This project roadmap fits into the [overall ecosystem roadmap](https://causaliq.org/projects/ecosystem_roadmap/)

## 🚧  Under development

No release currently under development.

## ✅ Previous Releases

- **v0.1.0 Workflow Foundations** [February 2026]: Framework for plug-in actions, basic workflow and CLI support

- **v0.2.0 Knowledge Workflows** [February 2026]: Include LLM graph generation in workflows and store results in Workflow caches.

## 🛣️ Upcoming Implementation

### Release 0.3.0 - Analysis Workflows

Graph averaging, structural analysis, and cache query capabilities.

**Scope**:

- Cache read/scan functionality:
  - `cache_input` source for workflow steps
  - Entry selection by matrix predicates (indexed lookup)
  - Entry selection by metadata predicates (scan)
  - Metadata update capability for enriching cached entries
- Graph averaging integrated (from causaliq-analysis)
- Structural evaluation integrated (from causaliq-analysis)
- Other analysis integrated

**Dependencies**: Requires causaliq-analysis initial release


### Release 0.4.0: Enhanced workflow

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


### Release 0.5: Discovery Integration

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