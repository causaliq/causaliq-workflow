# Action Patterns

CausalIQ workflow actions follow one of two patterns, determined by whether
they read a workflow cache: **Create** writes entries without reading a
cache, and **Aggregate** reads entries from a cache and writes new ones.
Actions that write a plain file instead of a cache run **once**, outside
matrix expansion.

## Pattern Summary

| Pattern | Input | Output | Matrix | Purpose |
|---------|-------|--------|--------|---------|
| **Create** | action-specific | required | required | Generate new cache entries |
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
      network: {{network}}
      sample_size: {{sample_size}}
      output: "results/graphs.db"
```

This creates 4 entries (2 networks × 2 sample sizes) in `graphs.db`.

### Conservative Execution

An entry is created only if it does not already exist. If an entry with
matching matrix values exists, the action is skipped for that combination.

## Run-once Steps

**Steps that write a plain file instead of a workflow cache run once.**

| Parameter | Requirement |
|-----------|-------------|
| `input` | Any (data files or a workflow cache) |
| `output` | Required, but not a `.db` cache |
| `matrix` | Not required |

A file output has no cache dimensionality, so the step runs a single time
however many matrix combinations the workflow declares, and it is skipped
on later jobs. Such a step may still read a cache: `plot` reads a metrics
cache and writes one image. A file-output step that also declares a matrix
keeps per-combination granularity; `summarise` relies on this to write one
row per combination.

A step that calls another workflow follows its own rule: it runs once
unless its `with` values vary across the matrix. See
[Reusable Workflows](subworkflows.md#matrix-and-execution).

```yaml
matrix:
  network: [asia, cancer]
  sample_size: [100, 1000]

steps:
  - name: "Plot F1"
    uses: "causaliq-analysis"
    with:
      action: "plot"
      input: "results/metrics.db"
      output: "results/f1.png"
```

## Pattern 2: Aggregate

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

A `null` value on either side (target or entry) is treated as a wildcard
and always matches. A **missing key** on the entry side (dimension absent
from the input cache) is also treated as a wildcard. See
[Null Values and Dimension Matching](core_concepts.md#null-values-and-dimension-matching)
for the full matching rules.

### Filtering Entries

Use the `filter` parameter to restrict which entries are aggregated:

```yaml
steps:
  - name: "Merge Filtered"
    uses: "causaliq-analysis"
    with:
      action: "merge_graphs"
      input: "results/graphs.db"
      filter: learn_graph.edge_count > 5 and sample_size >= 100
      output: "results/merged.db"
```

Matrix and result-object fields use bare names; metadata uses the producer
qualifier (`learn_graph.edge_count`).

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
      input:
        - "results/bnsl-pdgs.db"
        - "results/llm-pdgs.db"
      filter: llm_model == '{{llm_model}}' or sample_size == '{{sample_size}}'
      output: "results/fused.db"
```

Here, for each matrix combination the filter resolves to concrete values,
selecting the matching LLM entry from one cache and the matching BNSL
entry from the other for fusion. Entries from each cache only contain
dimensions relevant to their source, and missing dimensions are treated
as wildcards during matching.

See [Common Parameters](common_parameters.md#filter-parameter) for filter
expression syntax.

### Conservative Execution

An output entry is created only if it does not already exist in the output
cache.

## Choosing the Right Pattern

| You want to... | Use pattern |
|----------------|-------------|
| Generate graphs from data | Create |
| Evaluate graphs and store metrics | Aggregate |
| Merge multiple graphs into one | Aggregate |
| Compute statistics across experiments | Aggregate |
| Convert file formats | Create |
| Plot results to an image | Run once (file output) |

## Force Mode

To bypass conservative execution and re-run actions regardless of existing
results, use `--mode=force`:

```bash
cqflow run workflow.yml --mode=force
```

This re-processes all applicable entries but does not override `filter`
expressions (filtered entries remain excluded).
