# CausalIQ Pipeline - Development Roadmap & Progress

**Single source of truth for all development planning and progress tracking**

Last updated: 2024-12-30

## Current Status: Phase 1 (Month 1) - CI Workflow Foundation [STRATEGIC PIVOT]

### 🔄 STRATEGIC PIVOT: CI Workflow-Inspired Architecture

**Major Discovery**: During development, we discovered that GitHub Actions workflow patterns provide the perfect model for causal discovery experiments. The matrix strategy, templating system, and action-based steps naturally map to our research requirements while leveraging familiar CI/CD concepts.

**Key Breakthrough**: Rather than inventing new workflow patterns, we adopt proven GitHub Actions syntax with matrix expansion (`${{ matrix.variable }}`), package-level algorithm plugins, and YAML configuration-driven execution.

**Previous Pattern-Driven Work**: The initial pattern-driven configuration system provided valuable insights into external workflow definitions and validation requirements. This foundation work validates our configuration-driven approach and will be evolved into the CI workflow framework.

## Phase 1 Features (Month 1): CI Workflow Foundation 🚧 ~15% Complete

### ✅ Foundation Infrastructure [COMPLETED] 
- [x] **Testing framework** - Comprehensive pytest setup covering unit, functional, integration (45/45 tests passing)
- [x] **CI/CD pipeline** - GitHub Actions workflow with linting, formatting, type checking
- [x] **Code quality** - Black, isort, flake8, MyPy integration 
- [x] **Documentation structure** - MkDocs integration for API documentation
- [x] **Development environment** - Complete workspace setup with proper tooling
- [x] **Configuration foundation** - File loading, validation patterns established

### 🚧 GitHub Actions Schema Integration [IN PROGRESS]
- [x] **Feasibility validation** - Confirmed DASK integration, Jinja2 templating, matrix expansion viability
- [x] **Architecture proof-of-concept** - Demonstrated CI workflow parsing with GitHub Actions syntax
- [ ] **Workflow schema adoption** - Use GitHub Actions JSON schema for workflow validation
  - 🎯 **NEXT**: Replace PatternRegistry with GitHub Actions schema validator
- [ ] **Matrix expansion engine** - Convert `matrix:` configurations into individual experiment jobs
- [ ] **Jinja2 template processing** - Support `${{ matrix.variable }}` substitution throughout workflows

### ⏸️ Package-Level Algorithm Registry [PENDING]
- [ ] **bnlearn plugin** - R package integration with rpy2 bridge
- [ ] **Tetrad plugin** - Java package integration with py4j bridge  
- [ ] **causal-learn plugin** - Python package direct integration
- [ ] **Package discovery** - Automatic detection of available algorithm packages
- [ ] **YAML algorithm configuration** - Replace hard-coded algorithm classes with config-driven approach

### ⏸️ CI-Style Workflow Engine [PENDING]
  - ✅ **Future-ready** - Foundation for templates, inheritance, and composition

### ✅ YAML Configuration System [COMPLETED] 
- [x] **Basic workflow loading** - Parse and validate YAML workflow definitions
  - ✅ ConfigurationManager with pattern-driven validation
  - ✅ WorkflowConfig for structured access with pattern detection
  - ✅ ConfigurationError with comprehensive error context
- [x] **Schema validation** - Pattern-based validation with external schema definitions
  - ✅ Required/optional section validation per pattern
  - ✅ Hierarchical field validation with detailed error reporting
  - ✅ Flexible validation schemas defined in external YAML
- [x] **Flexible workflow patterns** - 5 patterns supporting diverse research needs
  - ✅ Series pattern for comparative research (algorithm comparison across datasets/parameters)
  - ✅ Task pattern for sequential operations (preprocessing → algorithm → analysis)  
  - ✅ Mixed pattern combining multiple approaches
  - ✅ Pipeline pattern for DAG-based workflows with dependencies
  - ✅ Longitudinal_research pattern for temporal causal discovery studies
- [ ] **Configuration inheritance** - Create workflows based on templates with overrides
### ⏸️ CI-Style Workflow Engine [PENDING]
- [ ] **Workflow parser** - Parse GitHub Actions-style YAML workflows
- [ ] **Step execution** - Execute workflow steps with action-based architecture
- [ ] **Environment management** - Handle workflow environment variables and context
- [ ] **Conditional execution** - Support `if:` conditions in workflow steps
- [ ] **Artifact handling** - Manage inputs/outputs between workflow steps

### ⏸️ DASK Task Graph Integration [PENDING]
- [ ] **Matrix job expansion** - Convert matrix configs into DASK task graphs
- [ ] **Dependency management** - Handle job dependencies with DASK
- [ ] **Local cluster management** - Setup and manage local DASK clusters
- [ ] **Progress monitoring** - Track workflow execution with real-time updates
- [ ] **Resource estimation** - Estimate compute requirements for planning

### ⏸️ Configuration Migration [PENDING]
- [ ] **CI workflow validation** - Ensure CI workflows validate correctly
- [ ] **Documentation update** - Update all docs to reflect CI workflow approach

## Phase 2 Features (Month 2): Research Integration [NOT STARTED]

### ⏸️ Algorithm Package Integration
- [ ] **R bnlearn integration** - Execute R bnlearn algorithms via rpy2
  - Matrix-driven algorithm selection: `algorithm: ["pc", "iamb", "gs"]`
- [ ] **Java Tetrad integration** - Integration with Java-based Tetrad via py4j
  - Cross-language workflow steps with data serialization
- [ ] **Python causal-learn** - Direct integration with Python algorithms
  - Native Python execution within workflow steps
- [ ] **Package discovery** - Automatic detection of available packages
- [ ] **Dependency validation** - Check required packages before workflow execution

### ⏸️ Dataset Management with CI Patterns
- [ ] **Zenodo integration** - Dataset download as workflow action
  - `uses: zenodo-download@v1` action pattern
- [ ] **Dataset caching** - Local storage and reuse with cache actions
- [ ] **Matrix dataset expansion** - Multiple datasets in workflow matrix
  - `matrix: {dataset: ["asia", "sachs"], sample_size: [100, 1000]}`
- [ ] **Dataset transformations** - Preprocessing steps as workflow actions

### ⏸️ Advanced Matrix Workflows
- [ ] **Cross-product expansion** - Full matrix combinations with intelligent batching
- [ ] **Conditional matrices** - Include/exclude matrix combinations based on conditions
- [ ] **Matrix job dependencies** - Sequential and parallel matrix job orchestration
- [ ] **Result aggregation** - Collect and combine results across matrix jobs

### ⏸️ LLM Integration as Actions
- [ ] **Model averaging action** - LLM-guided model averaging as reusable action
- [ ] **Hypothesis generation** - LLM analysis steps in workflow
- [ ] **Result interpretation** - LLM post-processing actions
- [ ] **Research workflow templates** - Pre-built workflows for common research patterns

## Phase 3 Features (Month 3): Production CI Features [NOT STARTED]

### ⏸️ Advanced Workflow Management
- [ ] **Workflow queuing** - Manage multiple concurrent workflows like CI runners
- [ ] **Pause/resume** - Interrupt and restart workflows with state preservation
- [ ] **Workflow artifacts** - Persistent storage and retrieval of workflow outputs
- [ ] **Workflow caching** - Cache intermediate results for faster re-runs
- [ ] **Branch/PR workflows** - Different workflows for different experiment branches

### ⏸️ Enterprise CI Features
- [ ] **Secrets management** - Secure handling of API keys and credentials
- [ ] **Environment isolation** - Containerized execution environments
- [ ] **Resource limits** - CPU, memory, and time limits per workflow/job
- [ ] **Approval workflows** - Human approval steps for expensive experiments
- [ ] **Scheduled workflows** - Cron-style scheduled execution

### ⏸️ Monitoring and Observability  
- [ ] **Workflow status dashboard** - Real-time workflow execution monitoring
- [ ] **Job logs and traces** - Detailed logging with searchable history
- [ ] **Performance metrics** - Resource usage, timing, and efficiency tracking
- [ ] **Alert integration** - Notifications for workflow success/failure
- [ ] **Audit trail** - Complete execution history for reproducibility

### ⏸️ Results and Artifacts
- [ ] **Standardized outputs** - Replace pickle files with structured formats
- [ ] **Version tracking** - Track algorithm versions and parameter changes
- [ ] **Result comparison** - Compare outputs across workflow runs
- [ ] **Export capabilities** - Multiple output formats (CSV, JSON, HDF5)
- [ ] **Reproducibility metadata** - Complete metadata for result reproduction

## Success Criteria by Phase

### Phase 1 Success Metrics  
- [ ] Execute GitHub Actions-style YAML workflows locally
- [ ] Matrix expansion generates individual causal discovery jobs
- [ ] Package-level algorithm integration (bnlearn, Tetrad, causal-learn)
- [ ] DASK task graph execution with progress monitoring
- [ ] Jinja2 template processing for workflow variables

### Phase 2 Success Metrics
- [ ] Multi-language workflows (R, Java, Python) in single configuration
- [ ] Automatic dataset download and matrix expansion across datasets
- [ ] LLM integration actions for model averaging and analysis
- [ ] Advanced matrix workflows with conditional execution
- [ ] Research workflow templates for common causal discovery patterns

### Phase 3 Success Metrics  
- [ ] Production-grade workflow queue management
- [ ] Enterprise features: secrets, isolation, limits, approvals
- [ ] Comprehensive monitoring dashboard with real-time status
- [ ] Standardized result formats with complete reproducibility metadata
- [ ] Foundation ready for large-scale research deployment

## Post Three-Month Features (Research Phase)

### Q2 2026: Advanced Research Features
- **Workflow marketplace** - Sharing and discovering research workflow templates
- **Interactive notebooks** - Jupyter integration with workflow execution
- **Publication workflows** - Generate reproducible research outputs automatically
- **Domain knowledge integration** - Expert knowledge as workflow conditions

### Q3-Q4 2026: Migration and Scale
- **Multi-machine execution** - Distributed workflows across compute clusters
- **Cloud provider integration** - AWS, GCP, Azure workflow runners
- **GPU acceleration** - Support for GPU-accelerated algorithms
- **Web interface** - Browser-based workflow designer and monitor

### Beyond 2026: Advanced Capabilities
- **Workflow orchestration** - Complex multi-stage research pipelines
- **Real-time collaboration** - Multiple researchers on shared workflows
- **AI-assisted optimization** - Automated hyperparameter and workflow tuning
- **Integration ecosystem** - Plugins for major research tools and platforms

This roadmap leverages the familiar GitHub Actions paradigm while building a powerful platform specifically designed for causal discovery research workflows.