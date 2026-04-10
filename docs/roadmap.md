# CausalIQ Workflow - Development Roadmap

**Last updated**: April 10, 2026

This project roadmap fits into the [overall ecosystem roadmap](https://causaliq.org/projects/ecosystem_roadmap/)

## ✅ Previous Releases

- **v0.1.0 Workflow Foundations** [February 2026]: Framework for plug-in actions, basic workflow and CLI support

- **v0.2.0 Knowledge Workflows** [February 2026]: Include LLM graph generation in workflows and store results in Workflow caches.

- **v0.3.0 Aggregation Workflows** [March 2026]: Matrix-driven aggregation processing for multi-source workflows.

- **v0.4.0 Conservative Execution** [March 2026]: Formalised action patterns (creation, update, aggregation) and conservative execution to skip work if results exist.

- **v0.5.0 Multi-step Workflows** [April 2026]: Multi-step workflows and matrix nulls as wildcards.


## 🛣️ Upcoming Implementation


### Release 0.6.0 - Step Output Chaining

Enable workflow steps to consume outputs from previous steps.

**Scope**:

- **Step output references** - Template syntax `{{steps.<name>.outputs.<key>}}`
  - Extend `_resolve_template_variables()` to handle step output references
  - Track step outputs in WorkflowContext (add `step_outputs: Dict[str, Any]`)
  - Deserialise GraphML strings back to graph objects when consumed

- **Cache restoration** - Resume workflows from cached results
  - Check cache before executing step
  - Support forced re-execution flag


### Release 0.7.0: Enhanced Workflow

Dry and comparison runs, runtime estimation and processing summary

**Scope**:

- dry-run capability
- standardise message format
- support skip, would do etc messages
- support comparison (integration test) functionality
- processing summary
- estimate runtime
- progress indicators


### Release 0.8.0: Discovery Integration

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