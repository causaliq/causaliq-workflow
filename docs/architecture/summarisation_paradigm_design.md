# Summarisation Paradigm Design

## Overview

The Summarisation Paradigm enables workflows to aggregate results from
multiple matrix combinations into summary outputs. This is essential for
causal discovery research where experiments are run across many parameter
combinations (networks, sample sizes, algorithms) and results need to be
combined for analysis, model averaging, or comparison.

## Motivation

### Research Workflow Pattern

A typical causal discovery workflow generates many individual results:

```yaml
matrix:
  network: [asia, alarm, sachs]
  sample_size: [100, 500, 1000]
  seed: [1, 2, 3, 4, 5]

steps:
  - name: Generate Graph
    uses: causaliq/research
    with:
      action: generate_graph
      output: results/graphs.db
```

This produces 45 individual graphs (3 × 3 × 5). Researchers then need to:

1. **Aggregate by network**: Combine all graphs for each network
2. **Filter by quality**: Only include successful runs
3. **Compute summaries**: Average structures, consensus edges, etc.

The Summarisation Paradigm provides first-class support for this pattern.

## Architecture

### Aggregation Mode Detection

Aggregation mode is automatically activated when a step has:

1. A workflow `matrix` definition
2. An `aggregate` parameter specifying input cache(s)

```python
def _is_aggregation_step(
    self,
    step: Dict[str, Any],
    matrix: Dict[str, List[Any]],
) -> bool:
    """Check if a step should execute in aggregation mode."""
    if not matrix:
        return False
    step_inputs = step.get("with", {})
    return "aggregate" in step_inputs
```

### Aggregation Configuration

The `AggregationConfig` dataclass captures all aggregation parameters:

```python
@dataclass
class AggregationConfig:
    input_caches: List[str]     # Cache paths to scan
    filter_expr: Optional[str]  # Filter expression
    matrix_vars: List[str]      # Grouping dimensions
```

### Execution Phases

Aggregation execution has two phases:

#### Phase 1: Scan

The scan phase reads input caches, applies filters, and groups entries:

```python
def _scan_aggregation_inputs(
    self,
    config: AggregationConfig,
    matrix_values: Dict[str, Any],
    logger: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, Any]]:
    """Scan input caches and collect entries matching matrix values."""
```

**Scan Process:**

1. Open each input cache
2. Iterate all entries
3. Skip entries missing required matrix variables
4. Flatten metadata for filter evaluation
5. Apply filter expression (if present)
6. Match entries to current matrix combination
7. Return matching entries with provenance

#### Phase 2: Execute

The execute phase passes grouped entries to the action:

```python
# In _execute_job:
agg_config = self._get_aggregation_config(step, matrix)
if agg_config is not None:
    matching_entries = self._scan_aggregation_inputs(
        agg_config,
        job,  # Current matrix values
    )
    resolved_inputs["_aggregation_entries"] = matching_entries
```

Actions receive entries via `_aggregation_entries` parameter.

## Workflow Syntax

### Basic Aggregation

```yaml
matrix:
  network: [asia, alarm]

steps:
  # First step: generate individual graphs
  - name: Generate
    uses: causaliq/research
    with:
      action: generate_graph
      output: graphs.db

  # Second step: aggregate by network
  - name: Summarise
    uses: causaliq/analysis
    with:
      action: model_average
      aggregate: graphs.db
      output: summaries.db
```

### With Filter Expression

Filter entries before aggregation using metadata fields:

```yaml
- name: Summarise Successful
  uses: causaliq/analysis
  with:
    action: model_average
    aggregate: graphs.db
    filter: "status == 'completed' and edge_count > 0"
    output: summaries.db
```

### Multiple Input Caches

Combine results from multiple caches:

```yaml
- name: Merge Results
  uses: causaliq/analysis
  with:
    action: merge_graphs
    aggregate:
      - pc_results.db
      - ges_results.db
    output: merged.db
```

## Filter Expression Syntax

Filter expressions use a safe subset of Python syntax via `simpleeval`:

### Supported Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `==` | `status == 'completed'` | Equality |
| `!=` | `algo != 'pc'` | Inequality |
| `>`, `<` | `edge_count > 5` | Comparison |
| `>=`, `<=` | `sample_size >= 100` | Comparison |
| `and` | `a > 5 and b < 10` | Logical AND |
| `or` | `a > 5 or b > 10` | Logical OR |
| `not` | `not failed` | Logical NOT |
| `in` | `algo in ['pc', 'ges']` | Membership |

### Available Variables

Filter expressions can access:

1. **Matrix values**: `network`, `sample_size`, etc.
2. **Flattened metadata**: `status`, `edge_count`, etc.
3. **Qualified metadata**: `provider.action.field`

```yaml
# Filter by matrix variable
filter: "sample_size >= 500"

# Filter by metadata field
filter: "status == 'completed'"

# Filter by qualified path
filter: "causaliq-research.generate_graph.node_count > 5"
```

## Metadata Flattening

Nested metadata is flattened for filter evaluation:

```python
# Original metadata structure
{
    "causaliq-research": {
        "generate_graph": {
            "node_count": 5,
            "edge_count": 8
        }
    }
}

# Flattened for filter access
{
    "node_count": 5,
    "edge_count": 8,
    "causaliq-research.generate_graph.node_count": 5,
    "causaliq-research.generate_graph.edge_count": 8
}
```

Simple keys are available directly; qualified keys handle conflicts.

## Entry Structure

Actions receive entries as dictionaries:

```python
{
    "matrix_values": {"network": "asia", "sample_size": 100},
    "metadata": {...},      # Original nested metadata
    "cache_path": "graphs.db",
    "entry_hash": "abc123...",
    "entry": CacheEntry(...)  # Full entry object
}
```

## Logging

Aggregation operations log statistics:

```
Aggregation scan: scanned=45, filtered=3, matched=15
```

- `scanned`: Total entries examined
- `filtered`: Entries rejected by filter
- `matched`: Entries matching current matrix values

## Error Handling

### Missing Caches

Non-existent caches are skipped with warning:

```
Warning: Cache does not exist: missing.db
```

### Filter Errors

Filter evaluation errors cause entry to be filtered:

```python
try:
    if not evaluate_filter(filter_expr, flat_meta):
        total_filtered += 1
        continue
except Exception:
    total_filtered += 1
    continue
```

### Cache Read Errors

Cache read failures are logged and skipped:

```
Warning: Failed to read cache graphs.db: database is locked
```

## Integration with causaliq-core

The filter expression evaluation uses `causaliq_core.utils`:

```python
from causaliq_core.utils import evaluate_filter

if config.filter_expr:
    if not evaluate_filter(config.filter_expr, flat_meta):
        continue
```

This provides consistent filter syntax across the CausalIQ ecosystem.

## Future Enhancements

### Weight-Based Aggregation

Support weighted combinations using `compute_weight`:

```yaml
- name: Weighted Average
  uses: causaliq/analysis
  with:
    action: model_average
    aggregate: graphs.db
    weight: "1.0 / sample_size"  # Weight by inverse sample size
```

### Hierarchical Aggregation

Multi-level aggregation for complex analyses:

```yaml
- name: Per-Network Summary
  with:
    aggregate: graphs.db
    group_by: [network]

- name: Global Summary
  with:
    aggregate: network_summaries.db
    group_by: []  # Aggregate all
```

## See Also

- [Matrix Strategy Design](matrix_expansion_design.md)
- [Workflow Cache Design](workflow_cache_design.md)
- [Workflow Executor Design](workflow_executor_design.md)
