# Status System API

The Status System provides standardized task execution status reporting for workflow logging, monitoring, and debugging. It supports all execution modes (run, dry-run, compare) with comprehensive error categorization.

## TaskStatus Enum

::: causaliq_workflow.status.TaskStatus
    options:
        show_root_heading: true
        show_source: false
        heading_level: 3

The `TaskStatus` enum defines all possible task execution outcomes with standardized string values and helpful categorization properties.

### Status Categories

#### Core Execution Statuses
- **EXECUTES** - Task executed successfully, output files created/updated
- **WOULD_EXECUTE** - Task would execute successfully if run (dry-run mode)
- **SKIPS** - Task skipped because output files exist and are current
- **WOULD_SKIP** - Task would be skipped because output files exist (dry-run mode)

#### Compare Mode Statuses
- **IDENTICAL** - Task re-executed, outputs identical to previous run
- **DIFFERENT** - Task re-executed, outputs differ from previous run

#### Error Statuses
- **INVALID_USES** - Action package specified in `uses:` not found
- **INVALID_PARAMETER** - Parameters in `with:` block are invalid for action
- **FAILED** - Task execution threw unexpected exception
- **TIMED_OUT** - Task exceeded configured timeout

### Properties

#### is_success
Returns `True` if status indicates successful execution:
- `EXECUTES`, `WOULD_EXECUTE`, `SKIPS`, `WOULD_SKIP`, `IDENTICAL`, `DIFFERENT`

#### is_error  
Returns `True` if status indicates an error condition:
- `INVALID_USES`, `INVALID_PARAMETER`, `FAILED`, `TIMED_OUT`

#### is_execution
Returns `True` if status indicates actual execution occurred:
- `EXECUTES`, `IDENTICAL`, `DIFFERENT`

#### is_dry_run
Returns `True` if status is for dry-run mode:
- `WOULD_EXECUTE`, `WOULD_SKIP`

## Usage Examples

### Basic Status Checking

```python
from causaliq_workflow import TaskStatus

# Check if a task completed successfully
if status == TaskStatus.EXECUTES:
    print("Task executed successfully")

# Categorize status
if status.is_success:
    print("Task completed successfully")
elif status.is_error:
    print(f"Task failed with error: {status.value}")
```

### Status-Based Control Flow

```python
# Handle different execution outcomes
match status:
    case TaskStatus.EXECUTES | TaskStatus.IDENTICAL:
        log_successful_execution(task_name, runtime)
    case TaskStatus.SKIPS | TaskStatus.WOULD_SKIP:
        log_skipped_task(task_name, reason="outputs exist")
    case TaskStatus.DIFFERENT:
        log_output_changes(task_name, diff_summary)
    case TaskStatus.FAILED:
        log_task_failure(task_name, exception_info)
    case _:
        log_other_status(task_name, status)
```

### Filtering and Aggregation

```python
# Count successful vs failed tasks
successful_tasks = [s for s in task_statuses if s.is_success]
failed_tasks = [s for s in task_statuses if s.is_error]

print(f"Success rate: {len(successful_tasks)/len(task_statuses):.1%}")

# Find tasks that actually executed
executed_tasks = [s for s in task_statuses if s.is_execution]
print(f"Executed {len(executed_tasks)} tasks")
```

### Dry-Run vs Run Mode

```python
def analyze_workflow_plan(statuses):
    """Analyze what a workflow would do in dry-run mode."""
    would_execute = [s for s in statuses if s == TaskStatus.WOULD_EXECUTE]
    would_skip = [s for s in statuses if s == TaskStatus.WOULD_SKIP]
    
    print(f"Would execute: {len(would_execute)} tasks")
    print(f"Would skip: {len(would_skip)} tasks")
    
    return len(would_execute) > 0  # True if work needed
```

## Integration Points

### Workflow Logger Integration

The TaskStatus enum is designed for integration with the upcoming WorkflowLogger system:

```python
# Future logging integration example
logger.log_task(
    action_name="causal-discovery",
    status=TaskStatus.EXECUTES,
    message="learn graph",
    runtime=2.3,
    outputs="/results/graph.xml"
)
```

### Action Development

Actions will report their execution status using TaskStatus values:

```python
# Action integration example
def run(
    self,
    action: str,
    parameters: Dict[str, Any],
    mode: str = "dry-run",
    context=None,
    logger=None,
) -> Dict[str, Any]:
    if mode == "dry-run":
        if self._outputs_exist(parameters):
            return {"status": TaskStatus.WOULD_SKIP}
        else:
            return {"status": TaskStatus.WOULD_EXECUTE}
    
    # Actual execution logic...
    return {"status": TaskStatus.EXECUTES, "outputs": results}
```

## Design Principles

### Status Completeness
The enum covers all possible task execution outcomes across different modes, ensuring comprehensive status reporting without gaps.

### Categorization Properties
Helper properties (`is_success`, `is_error`, etc.) enable easy filtering and aggregation without hardcoding status lists.

### String Values
All enum values use string representations matching their names, ensuring clear, readable log output.

### Mode Awareness
Distinct statuses for dry-run vs run modes enable accurate workflow planning and execution reporting.

---

**[← Previous: Schema Validation](schema.md)** | **[Back to API Overview](overview.md)** | **[Next: Logging System →](logging.md)**