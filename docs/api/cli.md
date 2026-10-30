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

# Override a workflow parameter
cqflow run experiment.yml --mode=run --param sample_size=5000

# Set the logging depth
cqflow run experiment.yml --mode=run --log-depth=2
```

Options:

- `--mode` - Execution mode: `dry-run` (default), `run`, or `force`
- `--log-depth` - Maximum workflow nesting depth to report: `0` is
  silent, `1` reports the top-level summary (default), `2` adds the
  top-level steps, `3` also adds first-level sub-workflow steps, and so
  on. `CAUSALIQ_LOG_DEPTH` supplies the default
- `--param NAME=VALUE` / `-p` - Workflow parameter, repeatable. A name
  matching a matrix entry replaces that entry; other names override a
  declared parameter or fill a `{{name}}` placeholder. Values follow the
  workflow value rules, so `--param alpha=0.05` is a number,
  `--param algorithm='[pc, ges]'` is a list and `--param name=no` is
  text. A repeated name is rejected

#### Log Output Status Messages

`--log-depth` controls how much of the execution log is printed. Each
value above `1` adds one more level of workflow nesting:

| Depth | Messages |
|-------|----------|
| `0` | Nothing |
| `1` | Loading, validation, execution and the final summary |
| `2` | Also the top-level steps, including the `CALLING` and `COMPLETED` boundaries of workflows they call |
| `3` | Also the steps of those called workflows, indented by two spaces |
| `3+` | Each further level adds the next level of sub-workflow messages |

When the depth includes step messages, the CLI outputs a status line per
job. Each matrix combination receives its own log line with one of the
following statuses:

| Status | Dry-run Equivalent | Description |
|--------|-------------------|-------------|
| **EXECUTED** | WOULD EXECUTE | Job processed successfully |
| **FORCED** | - | Job processed in force mode (bypasses conservative execution) |
| **SKIPPED** | WOULD SKIP | Conservative skip - entry already exists |
| **IGNORED** | WOULD IGNORE | Job filtered out by `filter` expression (never executes) |
| **FAILED** | - | Action raised an exception for this job |
| **CALLING** | WOULD CALL | A step calls another workflow; the enclosed steps run next |
| **COMPLETED** | WOULD COMPLETE | A called workflow returned, with the cumulative step counts of that call |

Example output with `--log-depth=3`:

```
2026-03-11 14:23:01 [./hc_std.yml] CALLING Run bnlearn hc with standard ordering
2026-03-11 14:23:01   [learn_graph] EXECUTED eval-step [network=asia]
2026-03-11 14:23:02 [./hc_std.yml] COMPLETED Run bnlearn hc with standard ordering (1 steps: 1 executed)
```

The two spaces before a message mark its call depth, so the entry and
exit of each sub-workflow are visible. The `COMPLETED` line counts the
steps performed by the called workflow **and** any workflows it called.

**Note**: The `filter` parameter excludes entries from processing entirely
(IGNORED), whilst conservative execution skips entries that have already been
processed (SKIPPED). Force mode (`--mode=force`) bypasses conservative
execution but does not override filters.

#### Error Summary

A run that fails steps ends with an `ERRORS:` list. Each line names the
failing step together with the matrix values that identify that
combination, and the list stops after ten messages:

```
2026-03-11 14:23:02 [causaliq-workflow] ERRORS:
  Learn graph [series=BNLEARN/HC_STD, network=asia, sample_size=10]: failed
  ... and 5 more errors
```

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
        cqflow run workflows/experiment.yml --mode=run --log-depth=2

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