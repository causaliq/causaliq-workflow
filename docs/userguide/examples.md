# Workflow Examples

This page provides concise examples illustrating the workflow concepts
documented in the [User Guide](index.md).

## Minimal Workflow

A single-step workflow with no matrix:

```yaml
# simple.yml
steps:
  - name: "Evaluate Graphs"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      input: "results/graphs.db"
      reference: "networks/asia/true.graphml"
```

## Workflow with Properties

Add workflow-level properties for identification and path management:

```yaml
# with_properties.yml
id: "experiment-001"
description: "Evaluate learned graphs"
root_dir: "/experiments/project"

steps:
  - name: "Evaluate Graphs"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      input: "results/graphs.db"
      reference: "networks/asia/true.graphml"
```

## Matrix Expansion

Run steps across multiple parameter combinations:

```yaml
# matrix_example.yml
id: "comparison"

matrix:
  network: [asia, cancer, alarm]
  sample_size: [100, 1000]

steps:
  - name: "Learn Structure"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      network: "{{network}}"
      sample_size: "{{sample_size}}"
      output: "results/graphs.db"
```

This creates 6 cache entries (3 networks × 2 sample sizes).

## Template Variables

Reference workflow and matrix values in parameters:

```yaml
# templates.yml
id: "exp-001"

matrix:
  network: [asia, cancer]

steps:
  - name: "Learn"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      network: "{{network}}"
      dataset: "data/{{network}}_10k.csv"
      output: "results/{{id}}/graphs.db"
```

## Create Pattern

Generate new cache entries (requires matrix and output):

```yaml
# create_pattern.yml
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

## Update Pattern

Add analysis to existing entries (requires input, no matrix or output):

```yaml
# update_pattern.yml
steps:
  - name: "Evaluate Graphs"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      input: "results/graphs.db"
      reference: "networks/{{network}}/true.graphml"
```

The `{{network}}` variable resolves from each entry's metadata at runtime.

## Aggregate Pattern

Combine entries into summaries (requires input, output, and matrix):

```yaml
# aggregate_pattern.yml
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

Entries are grouped by matrix values; one output entry per network.

## Multi-Step Workflow

Chain multiple steps sequentially:

```yaml
# multi_step.yml
id: "full-pipeline"

matrix:
  network: [asia, cancer]
  sample_size: [100, 1000]

steps:
  - name: "Learn Structure"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      network: "{{network}}"
      sample_size: "{{sample_size}}"
      output: "results/graphs.db"

  - name: "Evaluate Graphs"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      input: "results/graphs.db"
      reference: "networks/{{network}}/true.graphml"
```

## Filtering Entries

Restrict which entries are processed:

```yaml
# with_filter.yml
steps:
  - name: "Evaluate High-Quality"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      input: "results/graphs.db"
      filter: "edge_count > 5 and sample_size >= 100"
      reference: "networks/{{network}}/true.graphml"
```

## Running Workflows

```bash
# Validate and preview (default)
cqflow run workflow.yml

# Execute with conservative execution
cqflow run workflow.yml --mode=run

# Force re-execution of all steps
cqflow run workflow.yml --mode=force

# Detailed per-entry logging
cqflow run workflow.yml --mode=run --log-level=all
```

## Further Reading

- [Core Concepts](core_concepts.md) — Workflows, steps, matrix
- [Action Patterns](action_patterns.md) — Create, update, aggregate
- [Workflow Caching](caching.md) — Result storage
- [Common Parameters](common_parameters.md) — Shared parameters
- [CLI Usage](cli.md) — Command-line interface
