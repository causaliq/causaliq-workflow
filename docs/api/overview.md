# API Reference

The CausalIQ Workflow framework provides a comprehensive API for building, validating, and executing data processing workflows. It is part of the [CausalIQ ecosystem](https://causaliq.org/) for intelligent causal discovery.

The API is organized into several key modules:

## Core Components

### [Action Framework](actions.md)
Base classes and interfaces for creating reusable workflow actions that follow GitHub Actions patterns.

- **BaseActionProvider** - Abstract base class for all workflow actions
- **ActionInput/ActionOutput** - Type-safe input/output specifications  
- **ActionExecutionError/ActionValidationError** - Exception handling

### [Action Registry](registry.md)
Centralized discovery and execution system for workflow actions with plugin architecture support.

- **ActionRegistry** - Dynamic action discovery and management
- **WorkflowContext** - Complete workflow context for actions
- **ActionRegistryError** - Registry-specific exceptions

### [Workflow Engine](workflow.md)
Powerful workflow parsing, validation, and execution engine with matrix expansion and templating.

- **WorkflowExecutor** - Main workflow processing engine
- **WorkflowExecutionError** - Workflow execution exceptions
- **Template system** - Variable substitution and validation

### [Schema Validation](schema.md)
Robust workflow validation against JSON schemas with detailed error reporting.

- **validate_workflow** - Schema-based workflow validation
- **load_schema/load_workflow_file** - File loading utilities
- **WorkflowValidationError** - Validation-specific exceptions

### [Status System](status.md)
Comprehensive task execution status enumeration for workflow logging and monitoring.

- **TaskStatus** - Standardized status reporting for all task execution outcomes
- **Status properties** - Categorization helpers (success, error, execution, dry-run)
- **Status definitions** - Complete coverage of execution, comparison, and error statuses

### [Logging System](logging.md)
Centralized logging infrastructure with multiple output destinations for workflow execution monitoring.

- **WorkflowLogger** - Multi-destination logging with file/terminal output support
- **LogLevel** - Verbosity control (NONE, SUMMARY, ALL)
- **Output configuration** - Flexible logging destination management

### [CLI Interface](cli.md)
Command-line interface for workflow execution and management.

- **Command-line tools** - Direct workflow execution
- **Integration support** - CI/CD pipeline integration

---

## Quick Start

```python
from causaliq_workflow import WorkflowExecutor

# Create executor and run workflow
executor = WorkflowExecutor()
workflow = executor.parse_workflow("my_workflow.yml")
results = executor.execute_workflow(workflow, mode="run")
```

## Next Steps

- **[Usage Examples](examples.md)** - Comprehensive code examples and patterns
- **[Action Framework](actions.md)** - Learn how to create custom actions
- **[CLI Interface](cli.md)** - Command-line usage and CI/CD integration

For detailed examples and usage patterns, see the **[Usage Examples](examples.md)** page.