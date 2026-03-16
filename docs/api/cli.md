# CLI Interface

The command-line interface provides direct workflow execution and cache
management capabilities.

## Command Overview

causaliq-workflow provides three main commands:

- **cqflow run** - Execute workflow files
- **cqflow export-cache** - Export cache entries to directory or zip file
- **cqflow import-cache** - Import cache entries from directory or zip file

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

- `--mode` - Execution mode: `dry-run` (default), `run`, or `force`
- `--log-level` - Logging level: `none`, `summary` (default), or `all`

#### Log Output Status Messages

When `--log-level=all`, the CLI outputs per-entry status messages for UPDATE
pattern steps. Each entry in the cache receives its own log line with one of
the following statuses:

| Status | Dry-run Equivalent | Description |
|--------|-------------------|-------------|
| **EXECUTED** | WOULD EXECUTE | Entry processed successfully |
| **FORCED** | - | Entry processed in force mode (bypasses conservative execution) |
| **SKIPPED** | WOULD SKIP | Conservative skip - action already applied to this entry |
| **IGNORED** | WOULD IGNORE | Entry filtered out by `filter` expression (never executes) |
| **FAILED** | - | Action raised an exception for this entry |

Example output with `--log-level=all`:

```
2026-03-11 14:23:01 [evaluate] EXECUTED     eval-step [network=asia]
2026-03-11 14:23:02 [evaluate] EXECUTED     eval-step [network=cancer]
2026-03-11 14:23:02 [evaluate] SKIPPED      eval-step [network=alarm]
2026-03-11 14:23:02 [evaluate] IGNORED      eval-step [network=sachs]
```

**Note**: The `filter` parameter excludes entries from processing entirely
(IGNORED), whilst conservative execution skips entries that have already been
processed (SKIPPED). Force mode (`--mode=force`) bypasses conservative
execution but does not override filters.

### Export Cache Command

Export cache entries to a directory or zip file:

```bash
# Export to directory
cqflow export-cache -i results.db -o ./exported

# Export to zip file
cqflow export-cache -i results.db -o results.zip
```

Options:

- `-i, --input` - Path to WorkflowCache database file (.db)
- `-o, --output` - Output directory or .zip file path

### Import Cache Command

Import cache entries from a previously exported directory or zip:

```bash
# Import from directory
cqflow import-cache -i ./exported -o new_cache.db

# Import from zip file
cqflow import-cache -i results.zip -o new_cache.db
```

Options:

- `-i, --input` - Path to exported directory or .zip file
- `-o, --output` - Destination WorkflowCache database file (.db)

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
cqflow export-cache -i experiment.db -o results.zip

# Import shared results into local cache
cqflow import-cache -i results.zip -o local_cache.db
```

## Exit Codes

The CLI uses standard exit codes:

- **0** - Success
- **1** - General error (validation, execution failure)
- **130** - Interrupted by user (Ctrl+C)

---

**[← Previous: Logging System](logging.md)** | **[Back to API Overview](overview.md)** | **[Next: Examples →](examples.md)**