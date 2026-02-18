# CLI Interface

The command-line interface provides direct workflow execution and cache
management capabilities.

## Command Overview

causaliq-workflow provides three main commands:

- **cqflow run** - Execute workflow files
- **cqflow export_cache** - Export cache entries to directory or zip file
- **cqflow import_cache** - Import cache entries from directory or zip file

`cqflow` is an alias for `causaliq-workflow`.

## Core Interface

### causaliq_workflow.cli

::: causaliq_workflow.cli
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Command Line Usage

### Run Command

Execute a CausalIQ workflow file:

```bash
# Execute a workflow in dry-run mode (validate and preview - default)
cqflow run experiment.yml

# Execute a workflow in run mode (actually execute actions)
cqflow run experiment.yml --mode=run

# Set logging level
cqflow run experiment.yml --mode=run --log-level=all
```

Options:

- `--mode` - Execution mode: `dry-run` (default) or `run`
- `--log-level` - Logging level: `none`, `summary` (default), or `all`

### Export Cache Command

Export cache entries to a directory or zip file:

```bash
# Export to directory
cqflow export_cache -c results.db -o ./exported

# Export to zip file
cqflow export_cache -c results.db -o results.zip
```

Options:

- `-c, --cache` - Path to WorkflowCache database file (.db)
- `-o, --output` - Output directory or .zip file path

### Import Cache Command

Import cache entries from a previously exported directory or zip:

```bash
# Import from directory
cqflow import_cache -i ./exported -c new_cache.db

# Import from zip file
cqflow import_cache -i results.zip -c new_cache.db
```

Options:

- `-i, --input` - Path to exported directory or .zip file
- `-c, --cache` - Destination WorkflowCache database file (.db)

## CI/CD Integration

### GitHub Actions Integration

```yaml
name: Execute Causal Discovery Workflow

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install causaliq-workflow

    - name: Validate workflows (dry-run)
      run: |
        cqflow run workflows/experiment.yml --mode=dry-run

  execute:
    needs: validate
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install causaliq-workflow

    - name: Execute workflow
      run: |
        cqflow run workflows/experiment.yml --mode=run --log-level=all

    - name: Export results
      run: |
        cqflow export_cache -c results.db -o results.zip

    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: workflow-results
        path: results.zip
```

## Usage Patterns

### Batch Processing

```bash
# Execute multiple workflows sequentially
for workflow in workflows/*.yml; do
    echo "Executing $workflow..."
    cqflow run "$workflow" --mode=run
done
```

### Export and Share Results

```bash
# Export cache to share with collaborators
cqflow export_cache -c experiment.db -o results.zip

# Import shared results into local cache
cqflow import_cache -i results.zip -c local_cache.db
```

## Exit Codes

The CLI uses standard exit codes:

- **0** - Success
- **1** - General error (validation, execution failure)
- **130** - Interrupted by user (Ctrl+C)

---

**[← Previous: Logging System](logging.md)** | **[Back to API Overview](overview.md)** | **[Next: Examples →](examples.md)**