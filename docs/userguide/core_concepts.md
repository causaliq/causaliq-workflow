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

### Workflow Structure

| Property | Required | Description |
|----------|----------|-------------|
| `steps` | **Yes** | List of steps to execute |
| `matrix` | No | Parameter matrix for expansion (see below) |

### Workflow Parameters

Any other top-level scalar key declares a workflow parameter and its
default value. Declared parameters are available as template variables in
step parameters, and a caller or the CLI can override them:

```yaml
# workflow.yml
sample_size: 1000      # optional parameter, default 1000
seed: null             # required parameter, no default
```

```bash
cqflow run workflow.yml --param sample_size=5000 --param seed=42
```

`matrix` and `steps` are reserved. A name may not be declared as both a
parameter and a matrix variable. See
[Reusable Workflows](subworkflows.md#calling-parameters) for parameters
passed to a called workflow.

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
| `uses` | **Yes** | Action provider, or a relative path to another workflow |
| `with` | **Yes** | Action parameters, or a called workflow's parameters |

The `uses` property specifies which CausalIQ package provides the action
(e.g., `causaliq-analysis`, `causaliq-discovery`, `causaliq-knowledge`).
A value that starts with `./` or `../` calls another workflow instead of
an action; see [Reusable Workflows](subworkflows.md).

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

Actions follow one of two patterns — create or aggregate — determined by
whether the step reads a workflow cache. Steps that write plain files run
once. See [Action Patterns](action_patterns.md).

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
parameters and matrix values within step parameters.

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

### Types

A value that is exactly one `{{name}}` token keeps the variable's native
type: a matrix number stays a number, and a list parameter stays a list.
Text with extra characters is substituted as text.

```yaml
with:
  randomise: "{{randomise}}"      # a list parameter, passed through
  dataset: "data/{{network}}.csv" # text: "data/asia.csv"
```

### Quoting

A token must be quoted when it is the whole value:

```yaml
sample_size: "{{sample_size}}"   # correct
sample_size: {{sample_size}}     # invalid YAML: a nested mapping
```

An unquoted token is reported as `Invalid YAML syntax: ... found
unhashable key`, with a hint to quote it.

### Variable Resolution Order

Variables are resolved in this order, with later entries winning:

1. **Workflow parameters**: declared defaults
2. **Matrix variables**: values from the current matrix combination
3. **Supplied parameters**: values from the caller's `with` or `--param`

### Validation

Template variables are validated at parse time. Unknown variables cause a
validation error, which is also how a missing required parameter is
reported:

```
Unknown template variables: ['seed']. Available variables: ['dataset',
'network']. Declare the name as a workflow parameter, or supply it with
'with:' in the calling workflow or --param.
```

A workflow that is called from another workflow also sees the caller's
parameter names, and the CLI passes `--param` names to the parser, so a
template may reference a value that is supplied at run time.

AGGREGATE steps also see the matrix keys derived from their input caches, so
`{{network}}` resolves from a learned graph cache even when the workflow
declares no matrix. When an input cache does not exist yet — it may be
produced by an earlier step — that step's variables are resolved at runtime
instead.
