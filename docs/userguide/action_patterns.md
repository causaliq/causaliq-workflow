# Action Patterns

CausalIQ workflow actions follow one of three patterns, determined by their
`input` and `output` parameter usage. Understanding these patterns is key to
building correct workflows.

## Pattern Summary

| Pattern | Input | Output | Matrix | Purpose |
|---------|-------|--------|--------|---------|
| **Create** | action-specific | required | required | Generate new cache entries |
| **Update** | required | prohibited | prohibited | Add analysis to existing entries |
| **Aggregate** | required | required | required | Combine entries into summaries |

## Pattern 1: Create

**Create actions generate new entries in an output cache.**

| Parameter | Requirement |
|-----------|-------------|
| `input` | Not used (or refers to data files, not caches) |
| `output` | Required (workflow cache path) |
| `matrix` | Required |

The `matrix` defines the combinations for which entries are created. Each
matrix combination produces one entry in the output cache.

```yaml
matrix:
  network: [asia, cancer]
  sample_size: [100, 1000]

steps:
  - name: "Learn Graphs"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      network: "{{network}}"
      sample_size: "{{sample_size}}"
      output: "results/graphs.db"
```

This creates 4 entries (2 networks × 2 sample sizes) in `graphs.db`.

### Conservative Execution

An entry is created only if it does not already exist. If an entry with
matching matrix values exists, the action is skipped for that combination.

## Pattern 2: Update

**Update actions add analysis results to existing cache entries.**

| Parameter | Requirement |
|-----------|-------------|
| `input` | Required (workflow cache path) |
| `output` | Prohibited |
| `matrix` | Prohibited |

The action processes **all** entries in the input cache (subject to any
`filter`), adding results to each entry's metadata and objects. This ensures
analysis is applied consistently without risk of matrix mismatch.

```yaml
steps:
  - name: "Evaluate Graphs"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      input: "results/graphs.db"
      reference: "networks/{{network}}/true.graphml"
```

Note: The `{{network}}` variable is resolved from each entry's metadata at
runtime.

### Conservative Execution

An action is applied only if the entry exists **and** the action has not yet
been performed on it:

| Entry exists? | Action metadata exists? | Behaviour |
|--------------|------------------------|-----------|
| No | — | Skip |
| Yes | No | **Run** |
| Yes | Yes | Skip |

### Template Resolution for Updates

Update actions can use template variables that resolve from entry metadata:

```yaml
steps:
  - name: "Evaluate"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      input: "results/graphs.db"
      reference: "networks/{{network}}/true.graphml"  # From entry metadata
```

If an entry has `network: "asia"` in its metadata, the reference path becomes
`networks/asia/true.graphml` for that entry.

## Pattern 3: Aggregate

**Aggregate actions combine multiple entries into summary entries.**

| Parameter | Requirement |
|-----------|-------------|
| `input` | Required (workflow cache path) |
| `output` | Required (workflow cache path) |
| `matrix` | Required |

The `matrix` controls the **output dimensionality** — input entries are grouped
by matrix values and aggregated into new entries in the output cache.

```yaml
matrix:
  network: [asia, cancer]

steps:
  - name: "Merge by Network"
    uses: "causaliq-analysis"
    with:
      action: "merge_graphs"
      input: "results/graphs.db"
      output: "results/merged.db"
```

If `graphs.db` contains entries for multiple sample sizes per network, this
produces 2 entries in `merged.db` — one merged result per network.

### Entry Grouping

Entries from the input cache are automatically grouped by current matrix
values. For each matrix combination, all matching entries are passed to the
action for aggregation.

A `null` value in either the matrix target or the cache entry is treated as
a **wildcard** (N/A dimension) and always matches. This allows entries with
different dimensionality to be aggregated together. For example, an entry
with `llm_model: null` matches any target `llm_model` value, and vice versa.

### Filtering Entries

Use the `filter` parameter to restrict which entries are aggregated:

```yaml
steps:
  - name: "Merge Filtered"
    uses: "causaliq-analysis"
    with:
      action: "merge_graphs"
      input: "results/graphs.db"
      filter: "edge_count > 5 and sample_size >= 100"
      output: "results/merged.db"
```

Filter expressions support **template variables**, so you can parameterise
the filter per matrix combination:

```yaml
matrix:
  network: [asia, cancer]
  llm_model: [anthropic_claude, gemini_flash]
  sample_size: [1K, 10K]

steps:
  - name: "Fuse LLM and BNSL PDGs"
    uses: "causaliq-analysis"
    with:
      action: "merge_graphs"
      input: "results/pdgs.db"
      filter: "llm_model == '{{llm_model}}' or sample_size == '{{sample_size}}'"
      output: "results/fused.db"
```

Here, for each matrix combination the filter resolves to concrete values,
selecting the matching LLM entry and the matching BNSL entry for fusion.
Combined with null wildcard matching, entries whose `llm_model` or
`sample_size` is `null` can match across dimensions.

See [Common Parameters](common_parameters.md#filter-parameter) for filter
expression syntax.

### Conservative Execution

An output entry is created only if it does not already exist in the output
cache.

## Choosing the Right Pattern

| You want to... | Use pattern |
|----------------|-------------|
| Generate graphs from data | Create |
| Add metrics to existing graphs | Update |
| Merge multiple graphs into one | Aggregate |
| Compute statistics across experiments | Aggregate |
| Convert file formats | Create |

## Force Mode

To bypass conservative execution and re-run actions regardless of existing
results, use `--mode=force`:

```bash
cqflow run workflow.yml --mode=force
```

This re-processes all applicable entries but does not override `filter`
expressions (filtered entries remain excluded).
