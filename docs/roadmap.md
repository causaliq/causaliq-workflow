# CausalIQ Workflow - Development Roadmap

**Last updated**: November 20, 2025  
**Current release**: CLI Implementation Complete

## 🎯 Current Status

**✅ COMPLETED: Release 0.3 - Basic CLI

*Latest commit*: `36b16d8 feat: implement CLI with real-time workflow execution feedback`

**Current Capabilities**:

- Complete command-line interface: `causaliq-workflow run [--dry-run] <workflow>`
- Real-time workflow execution with step-by-step feedback  
- Action registry with plugin architecture
- 100% test coverage (471/471 lines) with full quality compliance
- Working end-to-end execution from YAML configuration

**Next Release**: 0.4 Enahnced Workflow  
**Target**: 1.0 Production Workflow

---

## ✅ Completed Implementation

*See Git commit history for detailed implementation progress*

**Key Commits**:

- `ce41487` - Action registry with auto-discovery plugin system
- `302b70a` - WorkflowExecutor with YAML parsing and matrix expansion  
- `a2c01da` - Action framework with dummy structure learner
- `b9c9c81` - Schema validation using JSON Schema
- `36b16d8` - CLI with real-time workflow execution feedback

**Current Architecture**:

- 📋 **CLI**: `causaliq-workflow run [--dry-run] <workflow>`
- 🔌 **Action Registry**: Auto-discovery plugin system
- ⚙️ **WorkflowExecutor**: YAML parsing, matrix expansion, step execution
- 📊 **Schema Validation**: JSON Schema with error reporting
- 🧩 **Testing**: 100% coverage, 201 tests passing


## 🛣️ Upcoming Implementation

### Release 0.3: Enhanced Workflow
**Key Deliverables**: Conservative execution and dry-run capability

**Commit 0.3.1: Basic Task Logging Infrastructure**

- [ ] **log_task() method** - Implement formatted message output with status/runtime/files
- [ ] **Message formatting** - Standardized format: timestamp, action, status, description
- [ ] **Comprehensive testing** - All status types with various input/output scenarios

**Commit 0.3.2: Action Output File Interface**

- [ ] **get_output_files() method** - Add to Action base class for file discovery
- [ ] **Default implementation** - Empty list for actions without specific outputs
- [ ] **Test integration** - Implement in test actions for validation

**Commit 0.3.3: FileManager Foundation**

- [ ] **FileManager class** - File existence and comparison utilities
- [ ] **Traditional file logic** - Basic exists/missing detection for replace-semantics files
- [ ] **Isolated testing** - File operations without workflow integration

**Commit 0.3.4: Skip Logic Implementation**

- [ ] **should_skip_action() method** - Determine if action can skip based on existing outputs
- [ ] **Traditional files only** - Skip logic for replace-semantics files (no append-semantics yet)
- [ ] **Comprehensive scenarios** - Test various file existence and modification patterns

**Commit 0.3.5: ActionExecutor Wrapper**

- [ ] **ActionExecutor class** - Wrapper for action execution with status determination
- [ ] **Status logic** - EXECUTES vs SKIPS for traditional files in run mode
- [ ] **Mock integration** - Test execution wrapper without WorkflowExecutor changes

**Commit 0.3.6: Dry-Run Status Logic**

- [ ] **WOULD_EXECUTE status** - Implement dry-run equivalent of EXECUTES
- [ ] **WOULD_SKIP status** - Implement dry-run equivalent of SKIPS  
- [ ] **Mode differentiation** - Proper status based on run vs dry-run mode

**Commit 0.3.7: WorkflowExecutor Integration**

- [ ] **Logger creation** - WorkflowExecutor creates and configures WorkflowLogger
- [ ] **ActionExecutor usage** - Replace direct action calls with ActionExecutor wrapper
- [ ] **Regression testing** - Ensure all existing workflows continue to pass

### Release 0.4: Progress and Summary
**Key deliverables**: Real-time progress tracking and execution summary

**Commit 0.4.1: Runtime Estimation Interface**

- [ ] **estimate_runtime() method** - Add to Action base class for progress calculation
- [ ] **Default estimation** - 1-second default for actions without specific estimates
- [ ] **Progress foundation** - Basic estimation without user interface

**Commit 0.4.2: Progress Calculation Engine**

- [ ] **Progress calculation** - Aggregate runtime estimates for workflow progress tracking
- [ ] **Background tracking** - Progress computation without user interface display
- [ ] **Accuracy testing** - Validate progress calculation with various workflow scenarios

**Commit 0.4.3: ProgressReporter Foundation**

- [ ] **ProgressReporter class** - Click integration for progress bar display
- [ ] **Basic structure** - Progress bar initialization and configuration
- [ ] **Static progress** - Progress structure without real-time updates yet

**Commit 0.4.4: Live Progress Integration**

- [ ] **Real-time updates** - Connect progress reporter to workflow execution
- [ ] **Action completion** - Update progress as actions complete
- [ ] **Optional display** - Toggle progress bars based on CLI parameters

**Commit 0.4.5: Status Aggregation & Summary**

- [ ] **Status aggregation** - Count tasks by status type (EXECUTES, SKIPS, etc.)
- [ ] **Summary formatting** - Clear report with counts, runtime, resource usage
- [ ] **Report accuracy** - Comprehensive testing for summary calculation

**Commit 0.4.6: Enhanced Error Reporting**

- [ ] **FAILED status formatting** - User-friendly error messages with actionable suggestions
- [ ] **INVALID_* status details** - Clear parameter validation error reporting
- [ ] **Error summary** - Aggregate error information for debugging

**Commit 0.4.7: CLI Enhancement & Testing**

- [ ] **Enhanced CLI options** - Improve CLI based on real-world testing feedback
- [ ] **Better error messages** - Refine error handling discovered during external package testing
- [ ] **Path resolution improvements** - Handle edge cases found during real usage
- [ ] **Complete CLI testing** - All logging features with file output verification
- [ ] **Performance validation** - Logging overhead measurement and optimization

### Release 0.5: Advanced Features
**Key deliverables**: Metadata, compare mode, timeouts, estimated completion.

**Commit 0.5.1: Append-Semantics File Support**

- [ ] **get_output_contribution_key()** - Action method for append-semantics identification
- [ ] **has_existing_contribution()** - Check if action's section exists in append-semantics files
- [ ] **FileManager enhancement** - Handle metadata.json style files with action-specific sections

**Commit 0.5.2: File Comparison Foundation**

- [ ] **Comparison utilities** - Basic file diff and comparison logic in FileManager
- [ ] **Text file diffs** - Generate meaningful comparisons for various file types
- [ ] **Isolated testing** - File comparison without execution integration

**Commit 0.5.3: Compare Mode Status Logic**

- [ ] **IDENTICAL status** - Implement when re-execution produces same outputs
- [ ] **DIFFERENT status** - Implement when re-execution produces changed outputs
- [ ] **Compare mode execution** - New execution path for output comparison

**Commit 0.5.4: Resource Monitoring Infrastructure**

- [ ] **Memory monitoring** - Track memory usage during action execution
- [ ] **CPU monitoring** - Track CPU utilization and report in log messages
- [ ] **Resource reporting** - Include resource usage in status messages

**Commit 0.5.5: Timeout Handling**

- [ ] **Timeout configuration** - Per-action timeout settings and monitoring
- [ ] **TIMED_OUT status** - Graceful termination with timeout status reporting
- [ ] **Cleanup logic** - Proper resource cleanup when actions exceed timeout

**Commit 0.5.6: Advanced Progress Features**

- [ ] **Estimated completion** - Real-time estimates based on action progress
- [ ] **Resource display** - Memory/CPU usage in progress indicators
- [ ] **Smart updates** - Adaptive progress update frequency based on action complexity

**Commit 0.5.7: Integration Testing & Optimization**

- [ ] **End-to-end validation** - Complete logging system integration testing
- [ ] **Matrix workflows** - Multi-action workflow testing with all status types
- [ ] **100% coverage** - Maintain comprehensive test coverage for all logging features
- [ ] **Compare mode testing** - Complete integration testing for output comparison
- [ ] **Resource monitoring validation** - Accuracy testing for memory/CPU tracking
- [ ] **Performance optimization** - Final performance tuning for large workflows
- [ ] **Documentation updates** - Complete documentation for all advanced logging features

### Release 0.5: Algorithm Integration Foundation
**Target**: Robust testing infrastructure with concrete action implementations

**Commit 0.5.1: Test Action Fixtures**

- [ ] **Concrete test actions** - Real algorithm implementations in tests/functional/fixtures
- [ ] **PC algorithm test action** - Simple structure learning with actual causal discovery logic
- [ ] **Multiple test algorithms** - Different algorithms to test various scenarios (GES, constraint-based)
- [ ] **Data processing** - Handle real CSV data and generate actual GraphML outputs

**Commit 0.5.2: Algorithm Testing Infrastructure**

- [ ] **Output standardization** - GraphML files with proper causal graph representation
- [ ] **Parameter validation** - Algorithm-specific parameter handling and validation
- [ ] **Data fixtures** - Test datasets for consistent algorithm validation
- [ ] **Results validation** - Verify GraphML output structure and content

**Commit 0.5.3: End-to-End Validation**

- [ ] **Complete workflow testing** - CLI → ActionRegistry → Test actions → Results
- [ ] **Matrix workflow validation** - Multi-algorithm, multi-dataset test scenarios
- [ ] **Performance benchmarking** - Execution time and resource usage with real algorithms
- [ ] **Documentation examples** - Complete usage examples using test action fixtures

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