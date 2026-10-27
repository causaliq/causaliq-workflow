# Common Parameters

These parameters are shared across many CausalIQ workflow actions. Individual
action documentation specifies which parameters apply and any action-specific
behaviour.

## Defaults and Omission

Omitting a parameter applies the action's declared default, and it is also
how a parameter that does not apply is expressed. There is no "none" or
"null" value to learn: write neither, and the action evaluates only what
applies.

Where a default has a natural explicit spelling, the action exposes it as a
value so the default can be pinned, compared in a filter, or passed to a
called workflow:

| Parameter | Default value | Meaning |
|-----------|---------------|---------|
| `randomise` | `no-randomise` | apply no randomisation |
| `sample_size` | `all` | use every row |
| `variable_types` | `impute` | infer types from the data |
| `timeout` | `60` | sixty minutes |

A literal `null` in a `with` block is rejected; use omission instead. See
[Core Concepts](core_concepts.md#parameters-and-defaults) for the full
rule and the matrix wildcard exception.

## `input` Parameter

Specifies the source of data for the action.

| Usage | Description |
|-------|-------------|
| **Workflow cache** | Path to `.db` file containing entries to process |
| **Data files** | Path to input files (CSV, GraphML, etc.) |

```yaml
with:
  input: "results/graphs.db"       # Process entries from cache
```

For **aggregate** steps, `input` points to a workflow cache. For **create**
steps, it may point to data files.

### Multiple Inputs

Some actions accept multiple input sources:

```yaml
with:
  input:
    - "results/llm_graphs.db"
    - "results/discovery_graphs.db"
```

## `output` Parameter

Specifies where results should be stored.

| Usage | Description |
|-------|-------------|
| **Workflow cache** | Path to `.db` file for storing results |
| **Directory** | Path to directory for file output |

```yaml
with:
  output: "results/merged.db"      # Store results in cache
```

**Note**: Steps that write a plain file (for example `plot`) also take
`output`; it names the file rather than a workflow cache.

### Output Behaviour by Pattern

| Pattern | Output | Behaviour |
|---------|--------|-----------|
| Create | Required | New entries added to output cache |
| Aggregate | Required | Aggregated entries added to output cache |
| Run once | Required file | One file written, outside matrix expansion |

## `filter` Parameter

Restricts which entries are processed by the action.

```yaml
with:
  input: "results/graphs.db"
  filter: sample_size >= 100 and network in ['asia', 'cancer']
```

### Filter Syntax

Filter expressions use Python syntax with supported operators:

| Category | Operators |
|----------|-----------|
| Comparison | `==`, `!=`, `>`, `<`, `>=`, `<=` |
| Boolean | `and`, `or`, `not` |
| Membership | `in` |
| Grouping | `()` |

### Bare Values in Filters

A bare word on the right of a comparison is a literal value unless it is
a declared parameter or a matrix variable used as a reference:

```yaml
filter: network == asia and f1 > 0.8
```

The expression above is equivalent to
`network == 'asia' and f1 > 0.8`, and both forms are accepted. Quote a
value only when its text collides with a workflow parameter or with a
field name used on the left of a comparison:

```
filter: description == 'description'   # literal text
filter: description == description     # declared parameter or left-hand field
```

The left side of a comparison is always a field reference. See
[Values and Quoting](values_and_types.md) for the full rules.

### Supported Functions

| Function | Description |
|----------|-------------|
| `len()` | Length of string or list |
| `str()` | Convert to string |
| `int()` | Convert to integer |
| `float()` | Convert to float |
| `bool()` | Convert to boolean |
| `abs()` | Absolute value |
| `min()` | Minimum of values |
| `max()` | Maximum of values |

### Random Sampling in Filters

The `random(count, seed)` function selects a reproducible random subset
of values for a variable. Use it with the `in` operator:

```yaml
filter: pdg_seed in random(5, 42)
```

This collects all distinct values of `pdg_seed` across the entries,
then deterministically selects 5 of them using the given seed. Only
entries whose `pdg_seed` is in the selected set pass the filter.

The selection is **deterministic** — the same seed always produces the
same subset, ensuring reproducibility across runs.

```yaml
# Select 3 random seeds and 2 random sample sizes
filter: pdg_seed in random(3, 0) and sample_size in random(2, 1)
```

!!! note
    The total number of distinct values for the variable must be at
    least as large as the requested count. If fewer distinct values
    exist, an error is raised.

### Filter Variables

Filter expressions can reference matrix values, result-object fields and
producer metadata:

```yaml
# Matrix and result-object fields use bare names
filter: network in ['asia', 'cancer', 'alarm'] and f1 > 0.8

# Metadata uses the action qualifier
filter: learn_graph.algorithm == 'pc' and learn_graph.status == 'ok'

# Nested metadata uses the full path
filter: learn_graph.hyperparameters.iss > 10 and sample_size < 10000
```

Bare metadata names such as `status` or `algorithm` are rejected: the
reference must name the producer (`learn_graph.status`,
`evaluate_graph.status`). Use the explicit
`learn_graph.parameters.algorithm` and `learn_graph.result.status` forms
when a name exists in both blocks, and the provider-qualified
`causaliq_discovery.learn_graph.status` form when action names collide.

### Template Variables in Filters

Filter expressions support `{{variable}}` template substitution, resolved
from workflow parameters, supplied parameters and matrix values before
evaluation. This enables parameterised filters that change per matrix
combination:

```yaml
matrix:
  network: [asia, cancer]
  llm_model: [anthropic_claude, gemini_flash]

steps:
  - name: "Merge by Model"
    uses: "causaliq-analysis"
    with:
      action: "merge_graphs"
      input: "results/pdgs.db"
      filter: llm_model == '{{llm_model}}' or sample_size == '1K'
      output: "results/merged.db"
```

For the `{network: asia, llm_model: anthropic_claude}` combination, the
filter resolves to `llm_model == 'anthropic_claude' or sample_size == '1K'`.

### Filter vs Conservative Execution

| Mechanism | Purpose | Result |
|-----------|---------|--------|
| `filter` | Exclude entries from processing | Entry status: IGNORED |
| Conservative execution | Skip already-processed entries | Entry status: SKIPPED |

Filtered entries are **never** processed, even with `--mode=force`.

## `reference` Parameter

For evaluation actions, specifies the ground truth for comparison.

```yaml
with:
  action: "evaluate_graph"
  input: "results/graphs.db"
  reference: "networks/{{network}}/true.graphml"
```

The reference path often uses template variables to match entries with their
corresponding ground truth files.

## `metric` Parameter

Specifies which metrics to compute for evaluation actions.

```yaml
with:
  action: "evaluate_graph"
  input: "results/graphs.db"
  reference: "networks/asia/true.graphml"
  metric:
    - f1
    - precision
    - recall
    - shd
```

Available metrics depend on the specific action. See action documentation for
supported metrics.

## Template Variables in Parameters

Most parameters support template variable substitution:

```yaml
id: "exp-001"

matrix:
  network: [asia, cancer]

steps:
  - name: "Evaluate"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      input: "results/{{id}}/graphs.db"
      reference: "networks/{{network}}/true.graphml"
```

See [Core Concepts](core_concepts.md#template-variables) for variable
resolution order.
