# Logging System API

The Logging System provides centralized logging infrastructure with multiple output destinations for workflow execution monitoring, debugging, and audit trails. It supports configurable verbosity levels and flexible output routing.

## WorkflowLogger Class

::: causaliq_workflow.logger.WorkflowLogger
    options:
        show_root_heading: true
        show_source: false
        heading_level: 3

The `WorkflowLogger` class provides centralized logging with support for multiple output destinations including terminal output, file logging, and test-capturable output.

### Key Features

#### Multi-Destination Output
- **Terminal logging** - Real-time output to stdout for interactive monitoring
- **File logging** - Persistent log files with automatic directory creation
- **Test capture** - Structured output that can be captured and verified in tests

#### Resource Management
- **Context manager support** - Automatic cleanup with `with` statements
- **File stream handling** - Proper opening, writing, and closing of log files
- **Error handling** - Graceful handling of file system errors

#### Flexible Configuration
- **Verbosity control** - Configure logging level at initialization
- **Output selection** - Enable/disable terminal and file output independently
- **Append mode** - Log files opened in append mode for multiple workflow runs

## LogLevel Enum

::: causaliq_workflow.logger.LogLevel
    options:
        show_root_heading: true
        show_source: false
        heading_level: 3

The `LogLevel` enum defines verbosity levels for controlling the amount of logging output during workflow execution.

### Verbosity Levels

#### NONE
Silent execution with no logging output. Useful for automated scripts where output needs to be minimal.

#### SUMMARY
Summary-level logging showing key status information and final results only. Default level providing essential information without overwhelming detail.

#### ALL
Comprehensive logging including all task details and intermediate steps. Useful for debugging and detailed workflow analysis.

## Usage Examples

### Basic Logger Setup

```python
from causaliq_workflow import WorkflowLogger, LogLevel
from pathlib import Path

# Terminal-only logging with default verbosity
logger = WorkflowLogger()

# File-only logging with high verbosity
log_file = Path("workflow_execution.log")
logger = WorkflowLogger(
    terminal=False, 
    log_file=log_file, 
    log_level=LogLevel.ALL
)

# Both terminal and file logging
logger = WorkflowLogger(
    terminal=True,
    log_file=Path("logs/workflow.log"),
    log_level=LogLevel.SUMMARY
)
```

### Context Manager Usage

```python
from pathlib import Path

# Automatic resource cleanup
with WorkflowLogger(log_file=Path("execution.log")) as logger:
    # Logger will automatically close file streams
    pass  # Log workflow execution here
```

### Configuration Examples

```python
# Silent execution for automated environments
silent_logger = WorkflowLogger(
    terminal=False, 
    log_file=None, 
    log_level=LogLevel.NONE
)

# Development setup with verbose output
dev_logger = WorkflowLogger(
    terminal=True,
    log_file=Path("debug.log"),
    log_level=LogLevel.ALL
)

# Production setup with summary logging
prod_logger = WorkflowLogger(
    terminal=True,
    log_file=Path("/var/log/causaliq/workflow.log"),
    log_level=LogLevel.SUMMARY
)
```

### Checking Logger Configuration

```python
logger = WorkflowLogger(
    terminal=True, 
    log_file=Path("workflow.log")
)

# Check configuration
if logger.is_terminal_logging:
    print("Terminal output enabled")

if logger.is_file_logging:
    print(f"File logging to: {logger.log_file}")

if logger.has_output_destinations:
    print("Logger has at least one output destination")
else:
    print("Warning: No output destinations configured")
```

### Integration with Workflow Execution

```python
from causaliq_workflow import WorkflowExecutor, WorkflowLogger, LogLevel
from pathlib import Path

# Configure logging for workflow execution
log_file = Path("experiments/workflow_run.log")

with WorkflowLogger(
    terminal=True, 
    log_file=log_file, 
    log_level=LogLevel.ALL
) as logger:
    
    # Future integration - logger will be passed to workflow executor
    executor = WorkflowExecutor()
    # workflow_results = executor.execute_with_logging(workflow, logger)
```

## Design Principles

### Separation of Concerns
The logging system is designed as a separate module that can be integrated with various components without tight coupling.

### Resource Safety
Proper resource management ensures file streams are always closed, even in error conditions, preventing resource leaks.

### Test-Friendly Design
The logging infrastructure is designed to be easily mocked and tested, with clear interfaces for capturing output in automated tests.

### Future Extensibility
The core structure provides a foundation for adding task-specific logging functionality in subsequent development phases.

## Integration Points

### Workflow Executor Integration
The WorkflowLogger is designed to integrate with the WorkflowExecutor for comprehensive workflow execution logging:

```python
# Future integration pattern
executor = WorkflowExecutor(logger=logger)
results = executor.execute_workflow(workflow, mode="run")
```

### Action Integration
Actions will receive the logger as an optional parameter for task-level logging:

```python
# Action integration pattern
def run(
    self,
    action: str,
    parameters: Dict[str, Any],
    mode: str = "dry-run",
    context=None,
    logger=None,
) -> Dict[str, Any]:
    if logger:
        # Log task execution details
        logger.info(f"Executing action: {action}")
    return results
```

### CLI Integration
The CLI will provide logging configuration options:

```bash
# Future CLI integration
causaliq-workflow run workflow.yml --log-file=execution.log --log-level=all
```

## Error Handling

### File System Errors
The logger handles common file system errors gracefully:

- **Permission errors** - Clear error messages for access denied scenarios
- **Missing directories** - Automatic creation of parent directories
- **Disk space issues** - Proper error reporting for write failures

### Resource Cleanup
Context manager support ensures proper cleanup even when exceptions occur:

```python
try:
    with WorkflowLogger(log_file=Path("workflow.log")) as logger:
        # Workflow execution that might raise exceptions
        pass
except Exception as e:
    # Logger file streams are automatically closed
    print(f"Workflow failed: {e}")
```

---

**[← Previous: Status System](status.md)** | **[Back to API Overview](overview.md)** | **[Next: CLI Interface →](cli.md)**