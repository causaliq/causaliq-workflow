# Common Parameters

These parameters are shared across many CausalIQ workflow actions. Individual
action documentation specifies which parameters apply and any action-specific
behaviour.

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

For **update** and **aggregate** patterns, `input` typically points to a
workflow cache. For **create** patterns, it may point to data files.

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

**Note**: Update pattern actions do not use `output` — they modify entries
in the input cache directly.

### Output Behaviour by Pattern

| Pattern | Output | Behaviour |
|---------|--------|-----------|
| Create | Required | New entries added to output cache |
| Update | Prohibited | Results added to input cache entries |
| Aggregate | Required | Aggregated entries added to output cache |

## `filter` Parameter

Restricts which entries are processed by the action.

```yaml
with:
  input: "results/graphs.db"
  filter: "sample_size >= 100 and network in ['asia', 'cancer']"
```

### Filter Syntax

Filter expressions use Python syntax with supported operators:

| Category | Operators |
|----------|-----------|
| Comparison | `==`, `!=`, `>`, `<`, `>=`, `<=` |
| Boolean | `and`, `or`, `not` |
| Membership | `in` |
| Grouping | `()` |

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

### Filter Variables

Filter expressions can reference any metadata variable from cache entries:

```yaml
# Filter by algorithm and score
filter: "algorithm == 'pc' and f1_score > 0.8"

# Filter by multiple networks
filter: "network in ['asia', 'cancer', 'alarm']"

# Complex conditions
filter: "(sample_size >= 1000 or seed == 0) and status == 'success'"
```

### Template Variables in Filters

Filter expressions support `{{variable}}` template substitution, resolved
from workflow properties and matrix values before evaluation. This enables
parameterised filters that change per matrix combination:

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
      filter: "llm_model == '{{llm_model}}' or sample_size == '1K'"
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
