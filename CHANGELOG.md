# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Nothing yet

### Changed

- Nothing yet

### Deprecated

- Nothing yet

### Removed

- Nothing yet

### Fixed

- Nothing yet

### Security

- Nothing yet

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
