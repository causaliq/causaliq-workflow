# Action Patterns

A workflow step reads from and writes to the workflow cache in one of three
ways. The pattern decides whether the workflow `matrix` is required, whether
matrix values template parameters or group entries, and how many cache entries
the action receives.

| Pattern | Reads from the cache | Writes | `matrix` |
|---------|----------------------|--------|----------|
| **Produce** | nothing | a cache entry per combination | required |
| **Map** | one entry per job | one cache entry per job | optional |
| **Aggregate** | one or more entries per job | a cache entry, or a report file | required (grouping) |

Steps that write a plain file instead of a cache run **once**, outside matrix
expansion.

The action declares its own pattern, so you rarely need to name it. Refer to
the action's own documentation for which case it follows; the sections below
explain what each case requires of your workflow.

## Pattern 1: Produce

**Produce actions generate new entries in an output cache without reading a
cache.**

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

## Pattern 2: Map

**Map actions read one cache entry and write one cache entry.**

| Parameter | Requirement |
|-----------|-------------|
| `input` | Required (workflow cache path) |
| `output` | Required (workflow cache path) |
| `matrix` | Optional — taken from the input cache |

Each job receives exactly one input entry and produces the output entry with
the same matrix values, so the two caches share their dimensions. A job that
matches more than one input entry is an error: add a matrix key to tell the
entries apart.

A job that matches **no** input entry is skipped, with the reason recorded in
the step results. A cache may legitimately lack a combination — for example
when one learning run failed for a network — and the rest of the sweep should
still finish. This applies to every cache-reading step, so a merge that finds
nothing for a combination is skipped too, rather than aborting the run. If the
input cache itself is missing, the job is an error instead, because that
points at a step that did not run.

```yaml
steps:
  - name: "Evaluate Graphs"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      input: "results/graphs.db"          # one entry per job
      reference: "networks/{{network}}/true.graphml"
      output: "results/metrics.db"
```

### Inheriting the Matrix

Because the output dimensions equal the input dimensions, a map step does not
need the workflow to declare a matrix: the keys of the input cache are used
instead, and their values become available to the step's templates. The
example above relies on this — `{{network}}` comes from `graphs.db`.

Declare a matrix when you want to fix a dimension to a constant, as in a
daughter workflow, or to narrow the run to a subset of the cache's entries.

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

## Pattern 3: Aggregate

**Aggregate actions group entries into a summary entry or a report.**

| Parameter | Requirement |
|-----------|-------------|
| `input` | Required (workflow cache path) |
| `output` | Required (workflow cache path or report file) |
| `matrix` | Required (the grouping dimensions) |

The `matrix` controls the **output dimensionality** — input entries are
grouped by matrix values and written to new entries in the output cache.

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

The matrix is **never inherited** for a grouping step: grouping by the input
cache's own keys would match one entry per group and copy the input rather
than summarise it. State the dimensions you want to keep.

### Entry Grouping

Entries from the input cache are automatically matched against the current
matrix values. For each matrix combination, all matching entries are passed to
the action.

A `null` value on either side (target or entry) is treated as a wildcard
and always matches. A **missing key** on the entry side (dimension absent
from the input cache) is also treated as a wildcard. See
[Null Values and Dimension Matching](core_concepts.md#null-values-and-dimension-matching)
for the full matching rules.

### Filtering Entries

Use the `filter` parameter to restrict which entries a step reads:

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

## Which Case Is My Step?

| You want to... | Pattern | Example action |
|----------------|---------|----------------|
| Generate graphs from data | Produce | `learn_graph`, `generate_graph` |
| Convert file formats into a cache | Produce | `migrate_trace` |
| Evaluate or transform each entry on its own | Map | `evaluate_graph`, `best_graph` |
| Merge multiple graphs into one | Aggregate | `merge_graphs` |
| Compute statistics across experiments | Aggregate | `summarise` |
| Plot results to an image | Run once (file output) | `plot` |

## Force Mode

To bypass conservative execution and re-run actions regardless of existing
results, use `--mode=force`:

```bash
cqflow run workflow.yml --mode=force
```

This re-processes all applicable entries but does not override `filter`
expressions (filtered entries remain excluded).
