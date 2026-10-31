# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Predictable workflow values** - workflow YAML now uses a restricted
  scalar schema: `no`, `yes`, `on`, `off`, `01`, `0x10`, `1_000`,
  `10:30` and `2020-01-01` are text, while `true`, `false`, `null`,
  integers and decimal numbers keep their usual meaning
- **Unquoted template tokens** - a whole-value `{{name}}` token no
  longer needs quotes; tokens are protected before YAML parsing
- **Action-typed coercion** - a value quoted or written as text is
  converted to `int`, `float` or `bool` when the action declares that
  parameter type, just before the action runs
- **Bare filter literals** - `status == ok` and
  `network in [asia, cancer]` are accepted; a bare value is quoted only
  when it collides with a workflow parameter or field name
- **Version 2 metadata envelope** - cache entries now carry `provenance`,
  `parameters`, `result` and the reserved `history` block, with
  `schema_version: 2` in exported `_meta.json`
- **Execution provenance** - provider and workflow versions, the local
  action start time, monotonic elapsed seconds, and the runtime environment
  for every entry
- **Shared reporting view** - one projection of matrix values, result-object
  fields and producer metadata used by aggregation filters, `summarise` and
  `plot`
- **Qualified filter names** - metadata is addressed as
  `<action>.<field>` (for example `learn_graph.status`), with explicit
  `action.parameters.*` / `action.result.*` and provider-qualified forms
- `WorkflowCache.list_entry_summaries()` - list each entry's matrix values
  and metadata without decompressing object payloads
- **Sub-workflow completion messages** - a call step logs `COMPLETED`,
  with the cumulative step counts of the called workflow and any
  workflows it calls, when control returns to its caller; step messages
  are indented by call depth

### Changed

- **Workflow value typing** - YAML 1.1 spellings are no longer
  interpreted as booleans, octal integers, sexagesimal numbers or dates.
  A value that changed type (for example a matrix value of `010`) gets a
  new cache key; delete or regenerate obsolete caches
- **CLI `--param` values** - the CLI now follows the same rules as a
  workflow file: `--param name=no` is text, `--param id=001` keeps its
  leading zero, and dates are text
- **Matrix matching** - a number and its text spelling compare equal
  when an input cache is matched, so derived and explicit matrix values
  agree
- **Dependency** - requires `causaliq-core>=0.8.0.dev10` for
  `relax_filter_literals()`
- **Metadata block rename** - the action metadata block `inputs` is now
  `parameters`; explicit filter names use `action.parameters.field`
- **Provenance fields** - `started` (local ISO 8601 time with an offset and
  second precision) and `elapsed` (float seconds) replace `started_at`,
  `finished_at` and `duration_seconds`
- **Metadata standardisation** - actions may return a flat metadata mapping
  during the transition; the executor places it in `result`, records
  provenance, and constructs the envelope once
- **Export/import** - exports write `schema_version: 2`; imports normalise
  version 1 `provider -> action -> fields` metadata to the current schema
- **Aggregation scan performance** - matrix jobs now reuse a memoised
  per-cache index (matrix values and metadata only) instead of re-reading
  and fully decompressing every cache entry for every job; the index is
  invalidated when the cache is written
- **Single validation pass** - `cqflow run` now validates once: the CLI's
  execution call passes `validate=False` (the new default-`True`
  `execute_workflow` flag) so the entry-validation pass is not repeated
- **Workflow parameter defaults** - top-level scalar keys declare default
  values for step parameters; a `null` default now declares a parameter
  with no value, so it is omitted from the action when neither the caller
  nor `--param` supplies one (previously `null` meant required)
- **Parameter declaration validation** - a declared parameter must be used
  as a `{{placeholder}}` in a step, a null-default parameter may only be a
  whole-value placeholder, and an undeclared placeholder is a required
  parameter
- **`--log-depth`** - replaces `--log-level`; the integer value is the
  deepest workflow nesting level that reports messages: `0` silent, `1`
  the top-level summary (default), `2` the top-level steps, `3` also
  first-level sub-workflow steps, and so on
- **Error summary** - `ERRORS:` lines now name the matrix values that
  identify each failing combination; the list stops after ten messages
  and reports `... and N more errors`
- **Workflow engine module split** - `workflow/execution.py` is decomposed
  into `execution` (entry points and the job loop), `step_runner`,
  `step_store` and `job_state`, so every module stays within the code
  limits; public imports are unchanged
- **Single metadata splitter** - the action registry and the provenance
  layer now share `causaliq_workflow.action_metadata.split_action_metadata`
  instead of duplicating the "unwrap `result`, flat is result" rule

### Deprecated

- Nothing yet

### Removed

- `WorkflowCache.update_entry()` - the UPDATE action pattern has been
  removed; write a complete entry with `put_typed()` instead
- `WorkflowCache.get_or_create()` - entries are written as a whole by the
  action that produced them, so there is nothing to get-or-create
- `WorkflowCache.put_from_action()` - use `put_typed()` with a
  `CacheEntry`, which is what `cache.store_action_result()` now does
- The unused `entry_type` argument of `cache.store_action_result()`
- Per-entry `updates` reporting (`entries_updated`, `would_process` and
  `_entries_would_process`/`_entries_would_skip`); a successful step now
  always counts as one new entry
- `created_at` from exported `_meta.json` files and
  `WorkflowCache.list_entries()`; the SQLite column remains internal cache
  bookkeeping for workflow and LLM caches
- `provenance.finished_at` from the metadata envelope
- Empty placeholder objects for failed runs; failures are recorded as
  metadata only

### Fixed

- **Duplicate step names** - a repeated step name is now rejected at
  validation; step results are recorded by name, so a duplicate silently
  overwrote the earlier step's result and made the completion summary
  under-count the steps that ran
- `random()` filter resolution now accepts qualified variable names such as
  `learn_graph.seed`
- **Completion summary counts** - a called workflow's steps are now
  counted through every nesting level. A nested call was previously
  counted as an executed step, and steps below it were missed, so the
  `COMPLETED` totals reported executed steps that never ran

### Security

- Nothing yet

### Dependencies

- Requires causaliq-core >= 0.8.0.dev7 (for the shared metadata envelope)

## [0.5.0] Multi-step Workflows - 2026-04-10

### Added

- **Multi-step workflow execution** - Steps execute sequentially within
  each matrix job, with step outputs available to subsequent steps via
  template variables
- **Null values as wildcards** - `null` in matrix variables treated as
  wildcards during matching; missing keys in entry metadata also match
  as wildcards, allowing caches with fewer dimensions to be consumed
  by broader matrices
- **Template variables in filter expressions** - Filter `filter`
  parameter now resolves `{{variable}}` templates before evaluation
- **`random()` function in filters** - Filter expressions support
  `random()` for random sampling of cache entries
- **Relaxed matrix matching** - Case-insensitive numeric suffix
  normalisation (k, M, G, T) and wildcard support in dimension
  matching
- **Improved CLI reporting** - Enhanced summary output for workflow
  execution results

### Dependencies

- Requires causaliq-core >= 0.7.0 (for `random()` in filter expressions)

## [0.4.0] Conservative Execution - 2026-03-26

### Added

- **Action pattern validation** - Creation (output required, matrix required,
  input prohibited), Update (input required, output prohibited, matrix
  prohibited), Aggregation (input required, output required, matrix required)
- **Update action support** - Actions that modify input cache entries by
  adding metadata sections and objects to existing entries
- **Conservative execution** - Skip work if results exist: creation skips
  if entry with matching matrix values exists in output, update skips if
  action metadata section exists in entry, aggregation skips if entry with
  matching matrix values exists in output
- `--mode=force` option to bypass conservative execution checks
- All conservative execution logic implemented in workflow executor
  (actions unaware)

### Dependencies

- Requires causaliq-core >= 0.6.0

## [0.3.0] Aggregation Workflows - 2026-03-01

### Added

- **Aggregation mode detection** - Workflow steps automatically detect
  aggregation mode when matrix is defined and step has `aggregate` parameter
  or `input` parameter pointing to `.db` cache files
- **Implicit aggregation** - Steps with `input: results.db` and a workflow
  matrix automatically aggregate entries grouped by matrix dimensions
- **Explicit aggregation** - `aggregate` parameter for explicit specification
  of input cache paths (single string or list of paths)
- **Filter expressions** - `filter` parameter accepts expressions evaluated
  against flattened entry metadata (e.g., `"algorithm == 'pc' and score > 0.5"`)
- **AggregationConfig dataclass** - Configuration model storing input caches,
  filter expression, and matrix variables
- `_is_aggregation_step()` - Detects whether step should run in aggregation
  mode based on matrix and step parameters
- `_get_aggregation_config()` - Extracts aggregation configuration from step
- `_scan_aggregation_inputs()` - Scans input caches, applies filters, and
  collects entries matching current matrix values
- `_flatten_metadata()` - Flattens nested entry metadata for filter evaluation
- `_aggregation_entries` special parameter passed to actions containing matched
  entries with full metadata and entry objects

### Changed

- Workflow executor now passes matched entries to aggregation actions via the
  `_aggregation_entries` parameter instead of raw cache paths

### Dependencies

- Requires causaliq-core >= 0.5.0 for `evaluate_filter()` function

## [0.2.0] Knowledge Workflows - 2026-02-18

### Added

- `WorkflowCache` class for storing workflow step results in SQLite databases,
  built on causaliq-core's `TokenCache` infrastructure
- `CacheEntry` model with metadata dictionary and named objects list for
  storing action outputs
- `CacheObject` model for typed objects (e.g., graphml, json) within entries
- Matrix key generation using SHA-256 hash of matrix variable values for cache
  lookups
- `MatrixSchemaError` exception for detecting matrix variable name mismatches
- `cqflow export-cache` CLI command to export cache entries to directory or zip
  file
- `cqflow import-cache` CLI command to import cache entries from directory or
  zip file
- Built-in `echo` action for testing workflow execution, cache storage, and
  export/import functionality
- `WorkflowContext.matrix_key` property for computing cache keys from matrix
  values
- Cache support for both file-based and in-memory (`:memory:`) databases

### Changed

- Action providers now inherit from `CausalIQActionProvider` (from
  causaliq-core) instead of local base class
- Action `run()` method now returns `ActionResult` tuple (status, metadata,
  objects) instead of dictionary
- Registry imports `ActionExecutionError` and `CausalIQActionProvider` from
  causaliq-core
- WorkflowCache uses `JsonCompressor` from causaliq-core for tokenised JSON
  storage
- Updated documentation to reflect causaliq-core integration

### Dependencies

- Requires causaliq-core >= 0.4.0

## [0.1.0] Workflow Foundations - 2026-02-01

### Added
- Initial project structure and scaffolding with environment setup, CLI, pytest testing and CI testing on GitHub
- Framework for plug-in actions with auto-discovery system
- YAML workflow parsing with matrix expansion and step execution
- JSON Schema validation with clear error reporting
- Template variable validation for workflow files - automatic validation of `{{variable}}` patterns against available context (workflow properties + matrix variables) with clear error messages for unknown variables
- Support for Python 3.9, 3.10, 3.11, 3.12, and 3.13
- `cqflow` short form command alias for `causaliq-workflow`
- `CausalIQAction` base class for implementing custom actions
- Comprehensive logging system with configurable log levels
- 100% test coverage
