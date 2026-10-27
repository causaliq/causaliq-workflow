# CausalIQ Workflow - Development Roadmap

**Last updated**: October 24, 2026

This project roadmap fits into the [overall ecosystem roadmap](https://causaliq.org/projects/ecosystem_roadmap/)

## 🚧  Under development

### v0.6.0 Failure Handling & Optimisation [October 2026]

1. ✅ Failure statuses recorded in workflow caches
1. ✅ Output-driven run-once rule for file input/output steps (replaces NOCACHES)
1. ✅ Refactor to meet development guidelines
1. ✅ analyse and fix slow performance e.g. on `summarise`
1. ✅ remove redundant validation pass
1. ✅ Simplification of Workflow Caches and Action Patterns
1. ✅ Version 2 metadata envelope and shared reporting view
1. ✅ Standardise and reduce metadata fields
1. ✅ Workflows can invoke other workflows
1. ✅ Workflows accept input parameters
1. ✅ Default parameter values
1. ✅ Default workflow parameter values
1. 🛣️ Simplify and standardise quoting and typing rules
1. 🛣️ Metadata propagation, values audit and reporting capabilities
1. 🛣️ Action metadata catalogue with generated documentation and CLI discovery
1. 🛣️ Support Python 3.10-14, with 3.12 as default, and badge as [![SPEC 0 — Minimum Supported Dependencies](https://img.shields.io/badge/SPEC-0-green?labelColor=%23004811&color=%235CA038)](https://scientific-python.org/specs/spec-0000/)

## ✅ Previous Releases

### v0.5.0 Multi-step Workflows [April 2026]
- **Multi-step workflows**
- **matrix nulls** as wildcards

### v0.4.0 Conservative Execution [March 2026]

- **Formalised action patterns**: creation, update, aggregation
- **Conservative execution** to skip work if results exist.

### v0.3.0 Aggregation Workflows [March 2026]

- **Matrix-driven aggregation** processing for multi-source workflows.

### v0.2.0 Knowledge Workflows [February 2026]

- **LLM graph generation** in workflows
- **Workflow caches** for storing results

### v0.1.0 Workflow Foundations [February 2026]

- **plug-in actions frameaork**
- **basic workflow**
- **CLI support**


## 🛣️ Upcoming Implementation


### Release 0.8.0 - Step Output Chaining

Enable workflow steps to consume outputs from previous steps.

**Scope**:

- **Step output references** - Template syntax `{{steps.<name>.outputs.<key>}}`
  - Extend `_resolve_template_variables()` to handle step output references
  - Track step outputs in WorkflowContext (add `step_outputs: Dict[str, Any]`)
  - Deserialise GraphML strings back to graph objects when consumed

- **Cache restoration** - Resume workflows from cached results
  - Check cache before executing step
  - Support forced re-execution flag


### Release 0.9.0: Enhanced Workflow

Dry and comparison runs, runtime estimation and processing summary

**Scope**:

- dry-run capability
- standardise message format
- support skip, would do etc messages
- support comparison (integration test) functionality
- processing summary
- estimate runtime
- progress indicators




## 🚀 Possible Future Features


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