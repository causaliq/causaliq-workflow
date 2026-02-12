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
- Auto-discovery plugin system with `BaseActionProvider` base class
- YAML parsing, matrix expansion, step execution
- JSON Schema validation with clear error reporting
- Template variable validation for workflow files
- Support for Python 3.9, 3.10, 3.11, 3.12, and 3.13
- Comprehensive logging system
- 100% test coverage

*See Git commit history for detailed implementation progress*

## 🛣️ Upcoming Releases (speculative)

### Release v0.2.0 - Knowledge Workflows

Include LLM graph generation in workflows and store results in Workflow caches.

**Background**

CausalIQ "caches" (not sure that this is the best term) provide persistent
stores of intermediate and final results. Their main purpose is to avoid
redoing (expensive) computation work and support the reproducubility of
results over many years. Key design goals are:

- have light footprint on the filesystem - that is, be comparatively compact, 
and not require unwieldy numbers of files or folders
- access to check whether an entry already exists (and so avoid unnecessary
re-computataion) is quite quick
- they are sql-lite based, using blobs to store entries - CausalIQ objects
  (e.g. LLM Request or SDG graph) that are stored in caches provide
  encode/decode methods to convert from/to Python objects to the
  compact representations used in cached blobs - e.g. tokenised JSON, or
  compact edge lists for graphs.
- while the "live" version of caches are an internal CausalIQ format, import/export
  facilities are provided to convert them to directories containing open
  standard representations of their contents e.g. JSON, GraphML, CSV files.
- flexible in that they can hold multiple entry types, and don't assume a
particular workflow hierarchy (e.g. don't assume experiments-->networks-->sample size)

The first concrete implementation of caching has already been created in
causaliq-knowledge which caches LLM Request/Responses to reduce costs and
allow replication of LLM responses.

This release extends this work to causaliq-workflow
so that results from steps in workflows are cached, supporting conservative
and reproducible excution of workflows. What constitutes a "result" will
grow as functionality grows, but the initial target is store graphs and
edge confidences produces by the LLM generate_graph action.

This release will require coordinated work and refactoring across three CausalIQ
packages - see scope below - and so will require the use of Test PyPI dev packages as we proceed.

**Scope**:

causaliq-workflow (v0.2.0 Knowledge Workflows):

- support for causaliq-knowledge generate_graph action ✅
- available in causaliq-research ✅
- support for lists in workflows
- caching of result graphs and metadata
- import/export of Workflow Caches (to GraphML and JSON formats)
- overwrites existing cached results

causaliq-knowledge (v0.5.0 Workflow Cache Integration):

- `generate_graph` writes entries into a Workflow Cache rather than individual files
- common caching elements (`TokenCache`, `JsonEncoder`) migrated to causaliq-core

causaliq-core (v0.4.0 GraphML and Caching Infrastructure):

- common caching elements (abstract interface, JSON tokeniser) moved here
- SDG class supports import/export to GraphML format
- SDG class supports `encode()`/`decode()` for compact blob representation

**Architecture Decisions**

See [Workflow Cache Design](architecture/workflow_cache_design.md) for full details.

| Decision | Choice |
|----------|--------|
| Cache entry structure | Single entries table with `entry_type`, separate data and metadata blobs |
| SDG changes | Minimal: add `encode()`/`decode()` and GraphML I/O only |
| Edge confidences | Stored in metadata JSON, not as SDG edge attributes |
| Cache key | Hash of workflow matrix variable values |
| Schema binding | Cache bound to matrix variable structure, values can change freely |

**Deferred to v0.3.0**: Cache read/scan functionality (selecting entries by
matrix or metadata predicates) will be implemented alongside causaliq-analysis
capabilities that consume cached results.

**Commit Sequence**

*Commit 1: WorkflowCache class* ✅

- `WorkflowCache` class wrapping `TokenCache` from causaliq-core
- `put()`, `get()`, `exists()` methods with entry type dispatch
- Unit tests

*Commit 2: Matrix key generation* ✅

- `WorkflowContext.matrix_key` property
- SHA-256 hash of matrix variable values
- Used as cache key for step results
- Unit tests

*Commit 3: Workflow executor cache integration* ✅

- Pass `WorkflowCache` to actions via context
- Actions write results to cache
- Unit and functional tests

*Commit 4: Cache export CLI command* ✅

- `cqflow cache export <cache.db> --output <dir>`
- Export entries to `<hash>/graph.graphml` + `<hash>/metadata.json`
- Generate `manifest.json` index
- Functional tests

*Commit 5: Cache import CLI command* ✅

- `cqflow cache import <dir> --into <cache.db>`
- Round-trip test with export
- Functional tests

*Commit 6: Documentation*

- User guide for Workflow Caches
- CLI reference for cache commands
- Update architecture docs

**Dependencies**: Requires causaliq-core v0.4.0, causaliq-knowledge v0.5.0

**Implementation Order**

```
causaliq-core v0.4.0      causaliq-knowledge v0.5.0    causaliq-workflow v0.2.0
─────────────────────     ────────────────────────     ────────────────────────
1. GraphML read           
2. GraphML write          
3. SDG encode/decode      
4. Migrate TokenCache ───→ 1. Update imports
5. Migrate encoders ─────→ 2. GraphEntryEncoder
   [publish dev2]            3. Cache param
                             4. Write to cache ───────→ 1. WorkflowCache class
                             [publish dev1]              2. Matrix key
                                                         3. Executor integration
                                                         4. Export CLI (json only)
                                                         5. Import CLI (json only)
                                                         6. Documentation
```

Note: Graph entry export/import is handled by causaliq-knowledge CLI commands
(`causaliq-knowledge export_cache`, `causaliq-knowledge import_cache`).


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