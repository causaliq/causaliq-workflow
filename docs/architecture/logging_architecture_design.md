# Logging & Task Status Architecture Design

**Design Document Version**: 1.0  
**Date**: 2025-11-18  
**Status**: Draft - Implementation Planned

## Overview

CausalIQ Workflow requires a comprehensive logging and task status system to provide visibility into workflow execution, enable debugging, and support different execution modes (dry-run, run, compare). This document outlines the architecture for task-level logging with standardized status reporting.

## Requirements

### Functional Requirements

#### FR1: Multi-Destination Logging
- **Requirement**: Log messages to file and/or terminal simultaneously
- **Rationale**: Terminal output for interactive use, file output for audit trails and debugging
- **Implementation**: Configurable output destinations via CLI parameters

#### FR2: Test-Capturable Output  
- **Requirement**: Output must be capturable and verifiable in automated tests
- **Rationale**: Essential for testing workflow execution and validating status reporting
- **Implementation**: Structured logging interface that tests can intercept

#### FR3: Task-Level Granularity
- **Requirement**: Messages produced at individual task level (each action execution)
- **Rationale**: Actions may execute multiple internal tasks (e.g., learning hundreds of graphs)
- **Implementation**: Actions control their own message granularity and frequency

#### FR4: Standardized Message Format
- **Requirement**: Consistent, parseable message format across all actions
- **Format**: `YYYY-MM-DD HH:MM:SS [action-name] STATUS task description (details)`
- **Example**: `2025-06-23 12:03:23 [causal-discovery] EXECUTES learn graph in 2.3s`
- **Rationale**: Enables monitoring, parsing, and integration with external tools

#### FR5: Comprehensive Status System
- **Requirement**: Task execution status covers all workflow execution modes
- **Statuses**: See [Task Status Definitions](#task-status-definitions)
- **Rationale**: Provides complete visibility into workflow execution state

#### FR6: Summary Reporting
- **Requirement**: Aggregate status counts and resource consumption
- **Includes**: Task counts per status, total runtime, estimated resource usage
- **Rationale**: High-level workflow execution overview for monitoring

#### FR7: Progress Indication
- **Requirement**: Real-time progress feedback during execution
- **Implementation**: Click-based progress bars with estimated completion
- **Rationale**: User experience during long-running workflows

### Non-Functional Requirements

#### NFR1: Performance
- **Requirement**: Logging overhead < 5% of total execution time
- **Implementation**: Efficient logging with minimal I/O blocking

#### NFR2: Flexibility
- **Requirement**: Actions have complete control over message frequency/content
- **Implementation**: Optional logger interface, actions decide granularity

#### NFR3: Backward Compatibility
- **Requirement**: Existing actions work without modification
- **Implementation**: Logger parameter is optional, graceful degradation

## Task Status Definitions

### Core Execution Statuses

#### EXECUTES
- **Mode**: run, compare
- **Condition**: Task executed successfully, output files created/updated
- **Message**: Includes actual runtime, input/output file sizes
- **Example**: `EXECUTES learn graph in 2.3s → inputs: /data/asia.csv (1.2MB) → outputs: /results/graph.xml (0.8MB)`

#### WOULD_EXECUTE  
- **Mode**: dry-run
- **Condition**: Task would execute successfully if run, output files absent
- **Message**: Includes estimated runtime from action
- **Example**: `WOULD_EXECUTE learn graph in ~2.1s → inputs: /data/asia.csv (1.2MB) → outputs: /results/graph.xml (estimated)`

#### SKIPS
- **Mode**: run
- **Condition**: Task skipped because output files exist and are current
- **Message**: Includes existing file information
- **Example**: `SKIPS learn graph → outputs: /results/graph.xml (exists, 0.8MB)`
- **Special Case**: For append-semantics files (e.g., metadata.json), only skips if action's expected contribution already exists

#### WOULD_SKIP
- **Mode**: dry-run  
- **Condition**: Task would be skipped because output files exist
- **Message**: Includes existing file information
- **Example**: `WOULD_SKIP learn graph → outputs: /results/graph.xml (exists, 0.8MB)`
- **Special Case**: For append-semantics files, evaluates whether action's contribution would be added

### Compare Mode Statuses

#### IDENTICAL
- **Mode**: compare
- **Condition**: Task re-executed, outputs identical to previous run
- **Message**: Includes comparison details
- **Example**: `IDENTICAL learn graph in 2.4s → outputs: /results/graph.xml (unchanged)`
- **Special Case**: For append-semantics files, compares only the action's specific contribution

#### DIFFERENT
- **Mode**: compare
- **Condition**: Task re-executed, outputs differ from previous run
- **Message**: Includes difference summary
- **Example**: `DIFFERENT learn graph in 2.3s → outputs: /results/graph.xml (5 edge changes)`
- **Special Case**: For append-semantics files, reports differences in the action's contribution

### Error Statuses

#### INVALID_USES
- **Mode**: All
- **Condition**: Action package specified in `uses:` not found
- **Message**: Available actions listed
- **Example**: `INVALID_USES unknown-action → Available: [causal-discovery, visualization]`

#### INVALID_PARAMETER
- **Mode**: All (detected in dry-run)
- **Condition**: Parameters in `with:` block are invalid for action
- **Message**: Specific parameter validation errors
- **Example**: `INVALID_PARAMETER learn graph → missing required: data_path, invalid: alpha=-0.1`

#### FAILED
- **Mode**: run, compare
- **Condition**: Task execution threw unexpected exception
- **Message**: Exception details with traceback reference
- **Example**: `FAILED learn graph after 1.2s → FileNotFoundError: /data/missing.csv (see log line 1234)`

#### TIMED_OUT
- **Mode**: run, compare  
- **Condition**: Task exceeded configured timeout
- **Message**: Timeout duration and partial results
- **Example**: `TIMED_OUT learn graph after 300s → timeout: 300s, partial outputs may exist`

## Architecture Design

### Component Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  WorkflowExecutor │───→│  ActionExecutor  │───→│     Action      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  WorkflowLogger  │←───│   StatusTracker  │    │   FileManager   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       
         ▼                       ▼                       
┌─────────────────┐    ┌─────────────────┐              
│ProgressReporter  │    │  Summary Report  │              
└─────────────────┘    └─────────────────┘              
```

### Core Classes

#### WorkflowLogger
```python
class WorkflowLogger:
    """Centralized logging with multiple output destinations."""
    
    def __init__(self, 
                 terminal: bool = True,
                 log_file: Optional[Path] = None,
                 log_level: LogLevel = LogLevel.SUMMARY):
        
    def log_task(self, 
                action_name: str, 
                status: TaskStatus,
                message: str,
                runtime: Optional[float] = None,
                inputs: Optional[Dict[str, Any]] = None,
                outputs: Optional[str] = None,
                job_info: Optional[str] = None) -> None:
                
    def start_progress(self, total_jobs: int, estimated_runtime: float) -> None:
    def update_progress(self, completed: int, current_job: str) -> None:
    def finish_progress(self) -> None:
```

#### TaskStatus  
```python
class TaskStatus(Enum):
    """Enumeration of all possible task execution statuses."""
    EXECUTES = "EXECUTES"
    WOULD_EXECUTE = "WOULD_EXECUTE"
    SKIPS = "SKIPS"
    WOULD_SKIP = "WOULD_SKIP"
    IDENTICAL = "IDENTICAL"
    DIFFERENT = "DIFFERENT"
    INVALID_USES = "INVALID_USES"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
```

#### ActionExecutor
```python
class ActionExecutor:
    """Handles action execution with logging and status determination."""
    
    def __init__(self, logger: WorkflowLogger, file_manager: FileManager):
        
    def execute_action(self, 
                      action_name: str,
                      action_class: Type[Action], 
                      inputs: Dict[str, Any],
                      mode: str,
                      context: WorkflowContext) -> Dict[str, Any]:
        """Execute action with comprehensive status logging."""
        
    def should_skip(self, action_class: Type[Action], inputs: Dict[str, Any]) -> bool:
        """Determine if action should be skipped based on existing outputs."""
        
    def estimate_runtime(self, action_class: Type[Action], inputs: Dict[str, Any]) -> float:
        """Get runtime estimate from action for progress calculation."""
```

#### Modified Action Interface
```python
class Action(ABC):
    """Base class with optional logging support."""
    
    @abstractmethod
    def run(self, 
           inputs: Dict[str, Any], 
           mode: str = "dry-run",
           context: Optional[WorkflowContext] = None,
           logger: Optional[WorkflowLogger] = None) -> Dict[str, Any]:
        """Execute with optional logging capability."""
        
    def estimate_runtime(self, inputs: Dict[str, Any]) -> float:
        """Provide runtime estimate for progress calculation."""
        return 1.0  # Default: 1 second estimate
        
    def get_output_files(self, inputs: Dict[str, Any]) -> List[str]:
        """Return list of output files this action will create."""
        return []  # Default: no specific outputs
        
    def get_output_contribution_key(self, inputs: Dict[str, Any]) -> Optional[str]:
        """Return key identifying this action's contribution in append-semantics files.
        
        Used for files like metadata.json where multiple actions append content
        rather than replacing the entire file. Return None for traditional files.
        """
        return None  # Default: traditional replace-semantics
        
    def has_existing_contribution(self, file_path: str, inputs: Dict[str, Any]) -> bool:
        """Check if this action's contribution already exists in append-semantics file.
        
        Only called when get_output_contribution_key() returns non-None.
        Used to determine if action can skip execution.
        """
        return False  # Default: not applicable
```

## Implementation Phases

### Phase 1: Core Logging Infrastructure
**Target**: Basic logging working with actions

**Components**:
- `TaskStatus` enum with all status definitions
- `WorkflowLogger` class with file/terminal output
- Modified `Action.run()` signature with optional logger parameter
- Basic status logging from within actions

**Benefits**:
- Actions can immediately start logging task-level messages
- Foundation for all subsequent logging features
- No breaking changes (logger parameter optional)

**Example Usage**:
```python
# Inside action.run()
if logger:
    logger.log_task(
        action_name=self.name,
        status=TaskStatus.EXECUTES,
        message="learn graph",
        runtime=2.3,
        inputs={"dataset": "/data/asia.csv"},
        outputs="/results/graph.xml"
    )
```

### Phase 2: Smart Execution Logic  
**Target**: Add output detection and skip logic

**Components**:
- `FileManager` class for output file detection
- `ActionExecutor` class with skip logic
- Runtime estimation interface
- SKIP/WOULD_SKIP status implementation

**Benefits**:
- Intelligent workflow execution avoiding duplicate work
- Progress estimation foundation
- Proper dry-run vs run mode differentiation

### Phase 3: CLI Integration
**Target**: Complete user interface with logging

**Components**:
- CLI parameters: `--log-file`, `--log-level`
- `ProgressReporter` with Click integration
- Summary reports with status counts
- User-friendly error display

**Benefits**:
- Real-world testing of logging design
- Complete user experience
- Feedback for design refinement

### Phase 4: Advanced Features
**Target**: Compare mode and monitoring

**Components**:
- File comparison for IDENTICAL/DIFFERENT
- Resource monitoring (memory, CPU)
- Timeout handling with TIMED_OUT
- Enhanced progress displays

## Design Decisions

### Append-Semantics Output Files

#### The Metadata Challenge
Structure learning experiments often produce a `metadata.json` file that has **append semantics** rather than **replace semantics**:

- **Initial Creation**: Structure learning action creates metadata with algorithm details, runtime, parameters
- **Subsequent Additions**: Analysis actions add scores, metrics, validation results to the same file
- **Incremental Growth**: File grows over workflow execution rather than being replaced

#### Impact on Task Status Determination

**Traditional Files** (e.g., `graph.xml`):
- File exists → task can skip
- File missing → task must execute
- Compare mode: entire file comparison

**Append-Semantics Files** (e.g., `metadata.json`):
- File exists → check if *this action's contribution* already present
- Action's section missing → must execute (even if file exists)
- Compare mode: compare only this action's contribution

#### Implementation Strategy

**Action Interface Extension**:
```python
class Action(ABC):
    def get_output_contribution_key(self, inputs: Dict[str, Any]) -> Optional[str]:
        """Return key identifying this action's contribution in append-semantics files."""
        return None  # Most actions don't use append semantics
        
    def has_existing_contribution(self, file_path: str, inputs: Dict[str, Any]) -> bool:
        """Check if this action's contribution already exists in append-semantics file."""
        return False  # Default: not applicable
```

**FileManager Enhancement**:
```python
class FileManager:
    def should_skip_action(self, action: Action, inputs: Dict[str, Any]) -> bool:
        output_files = action.get_output_files(inputs)
        for file_path in output_files:
            if not os.path.exists(file_path):
                return False  # Missing file, must execute
            
            # Check append-semantics files
            contrib_key = action.get_output_contribution_key(inputs)
            if contrib_key and not action.has_existing_contribution(file_path, inputs):
                return False  # Action's contribution missing
        
        return True  # All outputs present (traditional or append-semantics)
```

**Comparison Logic**:
```python
class FileManager:
    def compare_outputs(self, action: Action, inputs: Dict[str, Any], 
                       old_run_dir: str, new_run_dir: str) -> ComparisonResult:
        """Compare outputs, handling append-semantics files appropriately."""
        
        output_files = action.get_output_files(inputs)
        for file_path in output_files:
            contrib_key = action.get_output_contribution_key(inputs)
            if contrib_key:
                # Compare only this action's contribution
                return self._compare_contribution(old_run_dir, new_run_dir, 
                                                file_path, contrib_key)
            else:
                # Traditional full-file comparison
                return self._compare_full_file(old_run_dir, new_run_dir, file_path)
```

#### Example: Structure Learning + Analysis Pipeline

**Workflow**:
```yaml
jobs:
  structure_learning:
    uses: causal-discovery
    with: 
      algorithm: pc
      data: data/asia.csv
      
  analysis:
    uses: graph-analysis  
    with:
      graph: ${{ jobs.structure_learning.outputs.graph }}
```

**Execution Sequence**:

1. **Structure Learning** (first run):
   - Creates: `/results/graph.xml`, `/results/metadata.json`
   - `metadata.json`: `{"structure_learning": {"algorithm": "pc", "runtime": 2.3, ...}}`
   - Status: `EXECUTES`

2. **Analysis** (first run):
   - Reads: `/results/graph.xml`
   - Appends to: `/results/metadata.json` 
   - `metadata.json`: `{"structure_learning": {...}, "analysis": {"scores": {...}, "metrics": {...}}}`
   - Status: `EXECUTES`

3. **Structure Learning** (second run):
   - `metadata.json` exists but missing `structure_learning` section (analysis cleared it)
   - Status: `EXECUTES` (recreates structure learning contribution)

4. **Analysis** (second run):
   - `metadata.json` exists with `structure_learning` but missing `analysis` section
   - Status: `EXECUTES` (adds analysis contribution)

5. **Structure Learning** (third run):
   - `metadata.json` exists with `structure_learning` section present
   - Status: `SKIPS` (contribution already exists)

#### Design Benefits

- **Precise Skip Logic**: Actions only skip when their specific contribution exists
- **Accurate Comparison**: Compare mode focuses on action's actual output changes
- **Incremental Execution**: Workflows can build up metadata files progressively
- **Clear Status Reporting**: Users understand exactly what each action contributed

### Why Task-Level Logging?
- **Actions control granularity**: Each action knows its internal complexity
- **Flexible reporting**: Single chart vs. hundreds of graphs handled appropriately  
- **Real-time feedback**: Users see progress as work happens
- **Debugging capability**: Specific task failures easily identified

### Why Status-Based Execution?
- **Mode-aware behavior**: Same action behaves correctly in dry-run vs run
- **Smart skipping**: Avoid duplicate work, enable incremental execution
- **Compare mode support**: Foundation for regression testing workflows
- **Clear error categorization**: Different error types handled appropriately

### Why Optional Logger Parameter?
- **Backward compatibility**: Existing actions continue working unchanged
- **Gradual adoption**: Actions can add logging over time
- **Testing simplicity**: Tests can inject mock loggers easily
- **Performance**: No overhead for actions that don't use logging

## Integration Points

### WorkflowExecutor Integration
- WorkflowExecutor creates WorkflowLogger based on CLI parameters
- Passes logger to ActionExecutor for all action executions
- Coordinates progress reporting across matrix jobs
- Handles summary report generation

### ActionRegistry Integration
- Validates actions support logging interface during discovery
- Provides action metadata for runtime estimation
- Enables error status reporting for INVALID_USES

### Exception Handling Integration
- All action exceptions caught by ActionExecutor
- Converted to appropriate FAILED status messages
- Stack traces logged with reference line numbers
- Graceful workflow continuation after failures

## Testing Strategy

### Unit Testing
- Mock logger captures for status verification
- FileManager testing with temporary directories
- ActionExecutor testing with mock actions
- Status transition testing for all scenarios

### Integration Testing  
- End-to-end logging through WorkflowExecutor
- CLI parameter integration testing
- File output format validation
- Progress reporter integration testing

### Performance Testing
- Logging overhead measurement
- Large matrix workflow testing
- Memory usage monitoring
- File I/O performance validation

## Future Extensions

### Advanced Features
- **Log parsing tools**: Analysis scripts for workflow execution logs
- **Monitoring integration**: Prometheus/Grafana metrics export
- **Notification system**: Slack/email alerts for workflow completion
- **Dashboard integration**: Web UI for workflow execution monitoring

### Action Enhancements
- **Detailed progress**: Sub-task progress reporting within actions
- **Resource prediction**: More sophisticated runtime/memory estimation
- **Parallel logging**: Thread-safe logging for parallel action execution
- **Custom status types**: Action-specific status extensions

## Conclusion

This logging architecture provides:
- **Complete visibility** into workflow execution at appropriate granularity
- **User-friendly experience** with progress indication and clear error reporting  
- **Developer-friendly integration** with optional, backward-compatible interface
- **Foundation for advanced features** like compare mode and monitoring
- **Testing-ready design** with mockable interfaces and captured output

The phased implementation approach allows for incremental development with real-world feedback at each stage, ensuring the final design meets actual user needs while maintaining system reliability and performance.