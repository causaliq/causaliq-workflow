# Values and Quoting

A workflow file is YAML, but CausalIQ reads values with its own rules so
that ordinary text does not need quoting. This page is the single source
of truth for values, types and quoting in workflow files.

## The Three Layers

There are three distinct layers, and a quote in one layer does not mean
the same as a quote in another:

| Layer | What it controls |
|-------|------------------|
| YAML structure | `matrix`, `steps`, `with`, lists, indentation and commas |
| CausalIQ values | How a scalar is read: text, number, boolean or null |
| Action types | How an action parameter is validated and used |

## Writing Values

Write plain text without quotes. CausalIQ's loader treats the following
as text, even though YAML 1.1 would read them as other types:

| Written | Read as |
|---------|---------|
| `no`, `yes`, `on`, `off` | text |
| `01`, `00` | text |
| `0x10`, `1_000`, `10:30` | text |
| `2020-01-01` | text |
| `1e3` | text |
| `1000`, `-1` | integer |
| `1.5`, `.5` | number |
| `true`, `false` | boolean |
| `null`, `~`, an empty value | no value |

A number written with a decimal point keeps its numeric value, so
`1.10` is the number `1.1`. Quote it when the spelling matters:

```yaml
version: "1.10"    # the text 1.10
```

## When to Quote

Quote a value only when YAML would otherwise read it as syntax or as a
different type.

| You want | Write | Why |
|----------|-------|-----|
| ordinary text | `description: draft` | no quotes needed |
| a whole template token | `sample_size: {{sample_size}}` | CausalIQ protects tokens |
| text containing `: ` or ` #` | `output: "results: v1"` | YAML syntax |
| text starting with `[`, `{`, `&`, `*`, `!`, `|`, `>`, `%`, `@` or a backtick | quote it | YAML syntax |
| a numeric spelling to stay text | `version: "1.10"` | preserves the text |
| literal `null`, `true` or `false` | `flag: "true"` | protects the text |
| a list | `metric: [f1, precision]` | YAML structure |
| a matrix wildcard | `llm_model: [null]` | explicit null |

Template tokens may also be quoted. Both forms are equivalent:

```yaml
sample_size: {{sample_size}}
sample_size: "{{sample_size}}"
```

## Action Parameter Types

An action declares whether a parameter is text, a number or a boolean.
CausalIQ converts an unambiguous text value just before the action runs.

| Parameter type | Accepted values |
|----------------|-----------------|
| `int` | `42`, `"42"` |
| `float` | `0.5`, `"0.5"` |
| `bool` | `true`, `"true"`, `yes`, `on`, `1`, `false`, `no`, `off`, `0` |
| `list[int]` | `[500, 1000]`, `["500", "1000"]` |
| `str` | text exactly as written |

Quoting therefore never changes the meaning of a number or a boolean for
an action. A `str` parameter keeps the text you wrote, which is why a
numeric spelling that must stay text still needs quotes.

A parameter the action does not declare, or one whose type is ambiguous
(such as `int or str`), is passed through unchanged and validated by the
action itself.

## Filters

Filter expressions use Python syntax.

- A field or parameter reference is a bare name.
- A literal value is text. Bare words on the right of a comparison are
  read as literals unless they are a declared parameter, a matrix
  variable, or a name used as a field reference on the left.
- The left side of a comparison is always a field reference.
- Quote a literal only when its text collides with a parameter or field
  name.

```yaml
filter: network == asia and f1 > 0.8
filter: network in [asia, cancer]
filter: description == 'description'   # literal
filter: description == description     # declared parameter or left-hand field
```

The whole filter value usually needs no YAML quotes. A template token
inside a filter needs expression quotes:

```yaml
filter: llm_model == '{{llm_model}}'
```

## CLI Parameters

`--param NAME=VALUE` uses the same value rules as a workflow file, with
one extra layer: the shell decides how the argument reaches the CLI.

```bash
cqflow run workflow.yml --param sample_size=5000 \
  --param name=no \
  --param reference=networks/asia.graphml
```

`sample_size=5000` is an integer, `name=no` is text and the path is text.
Quote the whole shell argument when it contains spaces:

```bash
cqflow run workflow.yml --param "metric=[f1, precision]"
```

## Cache Keys

Matrix values are part of a cache key. A value written as `1000` and one
written as `"1000"` are the same dimension value for matching, but they
do not necessarily select the same existing entry. When a workflow's
value rules change, delete or regenerate obsolete caches; they are
internal, disposable artefacts.

## Where to Go Next

- [Core Concepts](core_concepts.md) for workflows, matrix expansion and
  template variables.
- [Common Parameters](common_parameters.md) for `filter`, `input`,
  `output`, `reference` and `metric`.
- [Reusable Workflows](subworkflows.md) for passing values to a called
  workflow.
