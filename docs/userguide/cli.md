# CLI Usage

CausalIQ Workflow provides the `cqflow` command (alias for `causaliq-workflow`)
for executing workflows and managing caches.

## Commands

| Command | Description |
|---------|-------------|
| `cqflow run` | Execute a workflow file |
| `cqflow export-cache` | Export cache to directory or zip |
| `cqflow import-cache` | Import cache from export |

## Running Workflows

### Basic Execution

```bash
# Dry-run (validate and preview) - default
cqflow run workflow.yml

# Actually execute the workflow
cqflow run workflow.yml --mode=run
```

### Execution Modes

| Mode | Description |
|------|-------------|
| `dry-run` | Validate workflow and preview what would be done (default) |
| `run` | Execute workflow with conservative execution |
| `force` | Execute workflow, bypassing conservative execution |

```bash
# Preview what would happen
cqflow run workflow.yml --mode=dry-run

# Execute with conservative execution (skip completed work)
cqflow run workflow.yml --mode=run

# Force re-execution of all steps
cqflow run workflow.yml --mode=force
```

### Logging Levels

| Level | Description |
|-------|-------------|
| `none` | No output |
| `summary` | Summary of execution (default) |
| `all` | Detailed per-entry status messages |

```bash
# Detailed output showing each entry
cqflow run workflow.yml --mode=run --log-level=all
```

### Status Messages

With `--log-level=all`, each entry displays a status:

| Status | Dry-run Equivalent | Description |
|--------|-------------------|-------------|
| EXECUTED | WOULD EXECUTE | Entry processed successfully |
| FORCED | — | Entry processed (force mode) |
| SKIPPED | WOULD SKIP | Already completed (conservative execution) |
| IGNORED | WOULD IGNORE | Excluded by filter expression |
| FAILED | — | Action raised an exception |

Example output:

```
2026-03-15 14:23:01 [evaluate] EXECUTED  eval-step [network=asia]
2026-03-15 14:23:02 [evaluate] EXECUTED  eval-step [network=cancer]
2026-03-15 14:23:02 [evaluate] SKIPPED   eval-step [network=alarm]
```

## Cache Management

### Export Cache

Export cache entries to a directory or zip file for sharing or archival:

```bash
# Export to directory
cqflow export-cache -i results/graphs.db -o ./exported

# Export to zip file
cqflow export-cache -i results/graphs.db -o results.zip
```

### Import Cache

Restore cache entries from a previous export:

```bash
# Import from directory
cqflow import-cache -i ./exported -o results/restored.db

# Import from zip file
cqflow import-cache -i results.zip -o results/restored.db
```

## Workflow File Conventions

Workflow files typically use `.yml` or `.yaml` extension:

```
workflows/
├── learn_graphs.yml
├── evaluate_all.yml
└── generate_tables.yml
```

Organise related workflows in a directory structure that matches your project.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CAUSALIQ_ROOT` | Default root directory for workflows |
| `CAUSALIQ_LOG_LEVEL` | Default logging level |

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Workflow validation error |
| 2 | Workflow execution error |

## API Reference

For complete CLI details including all options and parameters, see the
[CLI API Reference](../api/cli.md).
