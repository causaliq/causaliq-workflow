# API Reference

The CausalIQ Workflow framework provides a comprehensive API for building,
validating, and executing data processing workflows. It is part of the
[CausalIQ ecosystem](https://causaliq.org/) for intelligent causal discovery.

## causaliq-core Foundation

causaliq-workflow builds on causaliq-core for its action framework. The
following components are imported from causaliq-core:

- **CausalIQActionProvider** - Abstract base class for all action providers
- **ActionInput** - Type-safe input specification for action parameters
- **ActionResult** - Tuple type for action return values
- **ActionValidationError** - Exception for parameter validation failures
- **ActionExecutionError** - Exception for runtime execution failures
- **TokenCache** - SQLite-based caching infrastructure for workflow results
- **JsonCompressor** - JSON tokenisation for compact cache storage

The API is organised into several key modules:

## Core Components

### [Action Framework](actions.md)

Base classes and interfaces for creating reusable workflow actions that follow
GitHub Actions patterns.

- **CausalIQActionProvider** - Abstract base class for all workflow actions
  (from causaliq-core)
- **ActionInput** - Type-safe input specifications (from causaliq-core)
- **ActionResult** - Standardised return type (from causaliq-core)
- **ActionExecutionError/ActionValidationError** - Exception handling (from
  causaliq-core)

### [Action Registry](registry.md)

Centralised discovery and execution system for workflow actions with plugin
architecture support.

- **ActionRegistry** - Dynamic action discovery via entry points
- **WorkflowContext** - Complete workflow context for actions including cache
- **ActionRegistryError** - Registry-specific exceptions

### [Workflow Engine](workflow.md)

Powerful workflow parsing, validation, and execution engine with matrix
expansion and templating.

- **WorkflowExecutor** - Main workflow processing engine
- **WorkflowExecutionError** - Workflow execution exceptions
- **Template system** - Variable substitution and validation

### [Workflow Cache](cache.md)

SQLite-based caching for workflow step results, built on causaliq-core's
TokenCache.

- **WorkflowCache** - High-level cache for workflow results
- **CacheEntry** - Entry model with metadata and named objects
- **MatrixSchemaError** - Cache consistency exceptions
- **Export/Import** - Convert cache entries to/from open formats

### [Schema Validation](schema.md)

Robust workflow validation against JSON schemas with detailed error reporting.

- **validate_workflow** - Schema-based workflow validation
- **load_schema/load_workflow_file** - File loading utilities
- **WorkflowValidationError** - Validation-specific exceptions

### [Status System](status.md)

Comprehensive task execution status enumeration for workflow logging and
monitoring.

- **TaskStatus** - Standardised status reporting for all task execution
  outcomes
- **Status properties** - Categorisation helpers (success, error, execution,
  dry-run)
- **Status definitions** - Complete coverage of execution, comparison, and
  error statuses

### [Logging System](logging.md)

Centralised logging infrastructure with multiple output destinations for
workflow execution monitoring.

- **WorkflowLogger** - Multi-destination logging with file/terminal output
  support
- **LogLevel** - Verbosity control (NONE, SUMMARY, ALL)
- **Output configuration** - Flexible logging destination management

### [CLI Interface](cli.md)

Command-line interface for workflow execution and management.

- **cqflow run** - Execute workflow files
- **cqflow export_cache** - Export cache entries to directory or zip
- **cqflow import_cache** - Import cache entries from directory or zip

---

## Quick Start

```python
from causaliq_workflow import WorkflowExecutor

# Create executor and run workflow
executor = WorkflowExecutor()
workflow = executor.parse_workflow("my_workflow.yml")
results = executor.execute_workflow(workflow, mode="run")
```

## Using the Cache

```python
from causaliq_workflow.cache import WorkflowCache, CacheEntry

# Store workflow results
with WorkflowCache("results.db") as cache:
    entry = CacheEntry()
    entry.metadata["algorithm"] = "pc"
    entry.add_object("graph", "graphml", "<graphml>...</graphml>")

    key = {"network": "asia", "algorithm": "pc"}
    cache.put(key, entry)

    # Retrieve later
    result = cache.get(key)
```

## Next Steps

- **[Usage Examples](examples.md)** - Comprehensive code examples and patterns
- **[Action Framework](actions.md)** - Learn how to create custom actions
- **[CLI Interface](cli.md)** - Command-line usage and CI/CD integration

For detailed examples and usage patterns, see the **[Usage Examples](examples.md)** page.