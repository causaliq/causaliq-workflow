# CausalIQ Pipeline - Development Roadmap & Progress

**Single source of truth for all development planning and progress tracking**

Last updated: 2025-11-13

## Current Status: Phase 1 (Month 1) - Action Framework Foundation [75% COMPLETE]

### 🎯 Major Achievement: Action Framework Implementation

**Key Breakthrough**: We've successfully implemented a robust action framework that serves as the foundation for all causal discovery workflows. The framework provides type-safe action composition, comprehensive error handling, and proven patterns for workflow orchestration.

**Key Breakthrough**: We've successfully implemented a robust action framework that serves as the foundation for all causal discovery workflows. The framework provides type-safe action composition, comprehensive error handling, and proven patterns for workflow orchestration.

**Implementation Highlights**:
- ✅ **Action framework foundation** - Abstract base classes with type-safe input/output specifications
- ✅ **GraphML format adoption** - Design decision for causal graph representation (DAGs, PDAGs, CPDAGs, MAGs, PAGs)
- ✅ **Matrix variable architecture** - Schema support for parameterized experiments
- ✅ **GitHub Actions-inspired syntax** - Familiar workflow patterns with schema validation

## Phase 1 Features (Month 1): Action Framework Foundation ✅ 75% Complete

### ✅ Foundation Infrastructure [COMPLETED] 
- [x] **Testing framework** - Comprehensive pytest setup covering unit, functional, integration (47/47 tests passing)
- [x] **CI/CD pipeline** - GitHub Actions workflow with linting, formatting, type checking
- [x] **Code quality** - Black, isort, flake8, MyPy integration with 100% compliance
- [x] **Documentation structure** - MkDocs integration for API documentation
- [x] **Development environment** - Complete workspace setup with proper tooling
- [x] **Configuration foundation** - JSON Schema-based workflow validation established

### ✅ Action Framework [COMPLETED]
- [x] **Action base classes** - Abstract Action class with type-safe input/output specifications
- [x] **Error handling** - ActionExecutionError and ActionValidationError with comprehensive context
- [x] **Input/output specification** - ActionInput dataclass for type hints and validation
- [x] **Reference implementation** - DummyStructureLearnerAction demonstrating framework patterns
- [x] **GraphML format decision** - Adopted GraphML as standard for causal graph representation
- [x] **Matrix variable support** - Actions receive dataset, algorithm, and parameter inputs

### ✅ Workflow Schema Integration [COMPLETED]
- [x] **GitHub Actions-inspired syntax** - Familiar workflow patterns adapted for causal discovery
- [x] **Matrix strategy support** - Parameterized experiments with matrix variable expansion
- [x] **Path construction fields** - data_root, output_root, id fields for organizing experiment outputs  
- [x] **Action parameters** - with blocks for passing parameters to actions
- [x] **Schema validation** - JSON Schema validation with comprehensive error reporting

## Phase 2 Features (Next): Workflow Execution Engine [NOT STARTED]

### 🔄 Workflow Executor Implementation [PLANNED]
- [ ] **WorkflowExecutor class** - Parse YAML workflows and coordinate action execution
- [ ] **Matrix expansion** - Convert matrix variables into individual experiment jobs
- [ ] **Path construction logic** - Dynamic file path generation from matrix variables
- [ ] **Action orchestration** - Execute workflow steps with proper dependency handling
- [ ] **Error propagation** - Comprehensive error handling across workflow execution

### ⏸️ Algorithm Integration [FUTURE]
- [ ] **Real structure learning** - PC, GES, and other causal discovery algorithms
- [ ] **Package plugins** - bnlearn (R), Tetrad (Java), causal-learn (Python) integration
- [ ] **Algorithm registry** - Automatic discovery and configuration of available algorithms
- [ ] **Cross-language bridges** - rpy2, py4j integration for R/Java algorithm access

## Success Metrics - Phase 1 ✅

- ✅ **Framework Foundation**: Action framework with type-safe interfaces implemented
- ✅ **Schema Architecture**: GitHub Actions-inspired workflow syntax with matrix support  
- ✅ **Reference Implementation**: DummyStructureLearnerAction proving framework viability
- ✅ **Format Decision**: GraphML adopted as standard for causal graph representation

## Next Milestone: Workflow Execution

**Target**: Implement WorkflowExecutor to parse and execute complete workflows
**Success Criteria**: 
- Parse workflow YAML files
- Execute multi-step workflows with matrix expansion
- Generate organized output directories with matrix variable paths
- Maintain 100% test coverage and CI compliance
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