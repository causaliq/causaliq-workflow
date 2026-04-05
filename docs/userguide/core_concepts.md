# Core Concepts

CausalIQ Workflow uses a declarative YAML syntax inspired by GitHub Actions.
This section explains the fundamental building blocks.

## Workflows

A **workflow** is a YAML file defining a sequence of steps to execute. Every
workflow has a `steps:` section containing one or more steps.

```yaml
# workflow.yml
steps:
  - name: "Merge Graphs"
    uses: "causaliq-analysis"
    with:
      action: "merge_graphs"
      input: "results/graphs.db"
      output: "results/merged.db"
```

### Workflow-Level Properties

| Property | Required | Description |
|----------|----------|-------------|
| `id` | No | Unique identifier for the workflow |
| `description` | No | Human-readable description |
| `root_dir` | No | Base directory for relative paths (default: current directory) |
| `steps` | **Yes** | List of steps to execute |
| `matrix` | No | Parameter matrix for expansion (see below) |

Custom properties defined at the workflow level become available as template
variables in step parameters.

## Steps

Each **step** performs a single unit of work. Steps execute sequentially.

```yaml
steps:
  - name: "Evaluate Graphs"
    uses: "causaliq-analysis"
    with:
      action: "evaluate_graph"
      input: "results/graphs.db"
      reference: "networks/asia/true.graphml"
```

### Step Properties

| Property | Required | Description |
|----------|----------|-------------|
| `name` | **Yes** | Human-readable step name |
| `uses` | **Yes** | CausalIQ package providing the action |
| `with` | **Yes** | Action parameters |

The `uses` property specifies which CausalIQ package provides the action
(e.g., `causaliq-analysis`, `causaliq-discovery`, `causaliq-knowledge`).

## Actions

**Actions** are the reusable operations provided by CausalIQ packages. Each
action has specific parameters documented in its package.

The `action` parameter within the `with:` block specifies which action to run:

```yaml
with:
  action: "merge_graphs"    # Required: which action to perform
  input: "results/graphs.db"
  output: "results/merged.db"
```

Actions follow one of three patterns — create, update, or aggregate — which
determine their input/output behaviour. See [Action Patterns](action_patterns.md).

## Matrix Expansion

The **matrix** feature runs steps across multiple parameter combinations,
essential for comparative experiments.

```yaml
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

This creates **6 jobs** (3 networks × 2 sample sizes), each with a unique
combination of `network` and `sample_size`.

### Matrix Behaviour

- Each combination produces a separate execution
- Matrix values are available as template variables
- Results are stored with matrix values as cache keys

### Null Values and Dimension Matching

A `null` value on either side (target or entry) means the dimension is
**not applicable** and is treated as a **wildcard** — it always matches.
A **missing key** on the entry side (dimension absent from the input
cache) is also treated as a wildcard, so that caches with fewer
dimensions can be consumed by broader matrices.

```yaml
matrix:
  network: [asia, cancer]
  llm_model: [null]          # wildcard — match any llm_model
  sample_size: [1K, 10K]
```

| Scenario | Target | Entry | Matches? |
|----------|--------|-------|----------|
| Target wildcard | `null` | any value | Yes |
| Entry wildcard | `"claude"` | `null` | Yes |
| Both null | `null` | `null` | Yes |
| Missing key in entry | `"1K"` | *(absent)* | Yes |
| Concrete match | `"asia"` | `"asia"` | Yes |
| Concrete mismatch | `"asia"` | `"alarm"` | No |

!!! tip "Separate caches for separate sources"
    When aggregating entries from different sources (e.g. FGES and LLM
    PDGs), store them in **separate caches** rather than one shared
    cache with null dimensions. Use the list syntax for `input:` to
    read from multiple caches:

    ```yaml
    input:
      - results/fges-pdgs.db
      - results/llm-pdgs.db
    ```

    This avoids entries from one source unintentionally matching
    targets intended for the other source via null wildcard matching.

## Template Variables

**Template variables** use `{{variable}}` syntax to reference workflow
properties and matrix values within step parameters.

```yaml
matrix:
  network: [asia, cancer]

steps:
  - name: "Learn Structure"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      network: "{{network}}"
      dataset: "data/{{network}}_10k.csv"
      output: "results/graphs.db"
```

### Variable Resolution Order

Variables are resolved in this order:

1. **Workflow properties**: `id`, `description`, custom workflow-level values
2. **Matrix variables**: Values from the current matrix combination
3. **Entry metadata**: For UPDATE pattern steps, values from cache entry
   metadata

### Validation

Template variables are validated at parse time for CREATE and AGGREGATE
patterns. Unknown variables cause a validation error:

```
WorkflowExecutionError: Unknown template variables: unknown_var
Available context: id, description, network
```

For UPDATE patterns, variables not in workflow context are deferred to runtime
resolution from entry metadata.
