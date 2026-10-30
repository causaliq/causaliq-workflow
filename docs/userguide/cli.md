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

### Workflow Parameters

Supply or override workflow parameters with `--param NAME=VALUE`
(repeatable):

```bash
# Override a declared default
cqflow run workflow.yml --mode=run --param sample_size=5000

# Replace a matrix dimension with a single value
cqflow run workflow.yml --mode=run --param network=asia

# Provide a list of values for a matrix dimension
cqflow run workflow.yml --mode=run --param algorithm='[pc, ges]'
```

Values are parsed as YAML, so numbers, booleans and lists keep their
types. A name that matches a matrix dimension replaces that dimension; any
other name overrides a declared parameter or supplies a required
`{{name}}` placeholder. A value supplied for a null-default parameter
replaces the omission. Names the workflow does not use are reported as
validation errors, and repeating a name is rejected. A parameter change
does not invalidate cached entries — use `--mode=force` to re-run.

### Logging Depth

`--log-depth` sets the deepest workflow nesting level that prints
messages. Each level above the default adds one layer:

| Depth | Description |
|-------|-------------|
| `0` | No output |
| `1` | Top-level summary only (default) |
| `2` | Adds the top-level steps and their `CALLING`/`COMPLETED` call boundaries |
| `3` | Adds first-level sub-workflow steps, indented by two spaces |
| `3+` | Each further level adds the next level of sub-workflow messages |

```bash
# Show the top-level steps and the workflows they call
cqflow run workflow.yml --mode=run --log-depth=2
```

### Status Messages

With `--log-depth=2` or higher, each entry displays a status:

| Status | Dry-run Equivalent | Description |
|--------|-------------------|-------------|
| EXECUTED | WOULD EXECUTE | Entry processed successfully |
| FORCED | — | Entry processed (force mode) |
| SKIPPED | WOULD SKIP | Already completed (conservative execution) |
| IGNORED | WOULD IGNORE | Excluded by filter expression |
| FAILED | — | Action raised an exception |
| CALLING | — | A step calls another workflow |
| COMPLETED | — | A called workflow returned, with its cumulative step counts |

Example output:

```
2026-03-15 14:23:01 [./hc_std.yml] CALLING Run bnlearn hc with standard ordering
2026-03-15 14:23:01   [evaluate] EXECUTED eval-step [network=asia]
2026-03-15 14:23:02 [./hc_std.yml] COMPLETED Run bnlearn hc with standard ordering (1 steps: 1 executed)
```

Messages from a sub-workflow are indented by two spaces per call level.
A failed run finishes with an `ERRORS:` list that names each failing step
with the matrix values that identify it, capped at ten entries followed
by `... and N more errors`.

The step name shown is the name expanded for that job, so a
`{{placeholder}}` in a step's `name` appears with its value (see
[Step Names](core_concepts.md#step-names)).

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
| `CAUSALIQ_LOG_DEPTH` | Default logging depth |

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Workflow validation error |
| 2 | Workflow execution error |

## API Reference

For complete CLI details including all options and parameters, see the
[CLI API Reference](../api/cli.md).
