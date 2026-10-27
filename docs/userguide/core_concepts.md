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
default value. Declare parameters before `matrix` and `steps` so the
intent is clear; the parser itself is order-independent. Declared
parameters are available as template variables in step parameters, and a
caller or the CLI can override them:

```yaml
# workflow.yml
sample_size: 1000      # default 1000
reference: null        # no value: omitted from the action

steps:
  - name: "Learn"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      sample_size: {{sample_size}}
      reference: {{reference}}
```

```bash
cqflow run workflow.yml --param sample_size=5000 \
  --param reference=networks/asia.graphml
```

A declaration binds as follows:

| Declaration | Value used when nothing supplies it |
|-------------|-------------------------------------|
| `sample_size: 1000` | `1000` |
| `reference: null` | none — the parameter is omitted from the action, so the action's own default applies |

Defaults are convenient when several steps need the same value, and they
let a workflow be run standalone without supplying anything.

Three rules keep declarations honest:

- A declared parameter must be used as a `{{placeholder}}` in at least one
  step's `with` block. An unused declaration is a validation error.
- A `null` parameter may only be the **whole value** of a step parameter.
  `"data/{{reference}}.csv"` would substitute `None` and is rejected.
- A placeholder that is not declared is a **required parameter**: a
  caller or the CLI must supply it, otherwise validation reports the
  name as an unknown template variable.

A declaration never adds a matrix dimension, and no parameter value is
part of a cache key, so a changed default does not invalidate existing
entries.

`matrix` and `steps` are reserved. A name may not be declared as both a
parameter and a matrix variable. See
[Reusable Workflows](subworkflows.md#calling-parameters) for parameters
passed to a called workflow.

## Parameters and Defaults

Omitting an action parameter means that its default applies. Omitting it is
also how a parameter that does not apply to the action is expressed — for
example, a score type for a constraint-based structure learning algorithm.
The two cases are deliberately indistinguishable, so a workflow never needs
a null or "none" value:

```yaml
with:
  action: "learn_graph"
  input: "data/asia.csv"
  algorithm: "pc"
  # randomise, sample_size and variable_types omitted: their defaults apply
```

Every default is a value the action could have been given explicitly. The
`learn_graph` action, for instance, accepts `randomise: no-randomise`,
`sample_size: all` and `variable_types: impute` as explicit spellings of
its defaults. That makes a default expressible in a matrix, comparable in a
filter, and passable to a called workflow:

```yaml
matrix:
  randomise: [no-randomise, var_best]
```

A literal `null` in a `with` block is rejected with a message asking you to
omit the parameter instead. A `{{placeholder}}` that resolves to null at run
time is still allowed: that is how a matrix wildcard marks a dimension as
not applicable (see
[Null Values and Dimension Matching](#null-values-and-dimension-matching)),
and how a workflow parameter declared with a `null` default reaches an
action as an omitted parameter.

The metadata recorded for a step follows the same rule: parameters that
were supplied or defaulted are listed, parameters that did not apply are
absent, and no recorded value is null.

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
| `name` | **Yes** | Human-readable step name, unique within the workflow |
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
      network: {{network}}
      sample_size: {{sample_size}}
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
      network: {{network}}
      dataset: data/{{network}}_10k.csv
      output: results/graphs.db
```

### Types

A value that is exactly one `{{name}}` token keeps the variable's native
type: a matrix number stays a number, and a list parameter stays a list.
Text with extra characters is substituted as text.

```yaml
with:
  randomise: {{randomise}}       # a list parameter, passed through
  dataset: data/{{network}}.csv  # text: "data/asia.csv"
```

An action parameter declared as `int`, `float` or `bool` also accepts its
text spelling. The value is converted just before the action runs, so
`seed: "42"` and `seed: 42` are equivalent. A `str` parameter keeps the
text you wrote.

### Quoting

Ordinary values need no quotes. A whole-value template token is written
without quotes:

```yaml
sample_size: {{sample_size}}   # valid: a template token
```

Quote a value only when YAML would otherwise read it as syntax or as a
different type. For example, `version: "1.10"` keeps the trailing zero,
and a value containing `: ` must be quoted. See
[Values and Quoting](values_and_types.md) for the complete rules.

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
'network']. Declare a default value for each missing name as a top-level
workflow key, or supply it with 'with:' in the calling workflow or
--param.
```

A workflow that is called from another workflow also sees the caller's
parameter names, and the CLI passes `--param` names to the parser, so a
template may reference a value that is supplied at run time.

AGGREGATE steps also see the matrix keys derived from their input caches, so
`{{network}}` resolves from a learned graph cache even when the workflow
declares no matrix. When an input cache does not exist yet — it may be
produced by an earlier step — that step's variables are resolved at runtime
instead.
