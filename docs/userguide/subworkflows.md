# Reusable Workflows

A CausalIQ workflow can call another workflow file, so a pipeline is
composed from smaller, reusable pieces instead of repeating the same
steps. The syntax mirrors GitHub Actions' local reusable workflows.

## Syntax

Give the `uses` property a path that starts with `./` or `../`:

```yaml
# workflows/benchmark.yml
steps:
  - name: Learn graphs
    uses: ./modules/learn-graphs.yml
    with:
      sample_size: 1000
```

```yaml
# workflows/modules/learn-graphs.yml
matrix:
  algorithm: [pc, ges]

steps:
  - name: Learn
    uses: causaliq-discovery
    with:
      action: learn_structure
      algorithm: {{algorithm}}
      output: results/graphs.db
```

A `uses` value that starts with `./` or `../` is a workflow call. Any
other value names an action provider, exactly as before:

```yaml
- uses: causaliq-analysis      # action provider
- uses: ./workflows/full.yml   # workflow call
```

The target must be a `.yml` or `.yaml` file. A workflow file named
without the relative prefix is reported rather than treated as an
unknown provider.

## Path Resolution

Relative paths resolve against the directory of the workflow file that
declares the call, so sibling modules are addressed as `./module.yml`.

```yaml
# workflows/modules/master.yml
steps:
  - name: Learn
    uses: ./learn-graphs.yml    # workflows/modules/learn-graphs.yml
```

The calling file's directory is the reference point, not the shell's
working directory. Cache paths declared with `output:` still resolve
against the working directory.

## Calling Parameters

The `with` block of a call step carries parameters for the called
workflow. A parameter binds to the child by name:

| Child declares | Behaviour |
|----------------|-----------|
| a matrix dimension (`algorithm`) | replaces that dimension's values (a scalar becomes `[value]`, a list is used as given) |
| a parameter default (`sample_size: 1000`) | overrides the default |
| a `null` parameter (`reference: null`) | supplies the value; omitting it leaves the parameter out of the action |
| a `{{name}}` placeholder in a step | substitutes the value |

Values are resolved in the caller's context, so they may reference the
caller's own matrix and parameters:

```yaml
matrix:
  label: [alpha, beta]

steps:
  - name: Call child
    uses: ./modules/learn-graphs.yml
    with:
      algorithm: {{label}}     # child matrix becomes [alpha] then [beta]
```

A parameter value that is exactly one `{{name}}` token keeps the value's
native type, so a numeric matrix override stays a number and a list stays
a list. That applies inside the child too: `randomise: {{randomise}}`
delivers the caller's list to the action unchanged, so a caller can pass
`randomise: ["var_best"]`.

To pass the child's *default* through a placeholder, use the value that
means the default. A parameter whose default has an explicit spelling can
therefore be driven by a caller matrix:

```yaml
matrix:
  randomise: [no-randomise, var_best]

steps:
  - name: Learn
    uses: ./modules/learn-graphs.yml
    with:
      randomise: {{randomise}}
```

`no-randomise` is the default of `randomise`, so the first combination runs
exactly as if the caller had omitted the parameter. To forward a value
only when the caller's own caller set it, declare the forwarding
parameter with a `null` default; see
[Declaring parameters](#declaring-parameters).

### Declaring parameters

Top-level scalar keys of a workflow declare its parameters. They are
available as `{{name}}` placeholders and may be overridden by a caller:

```yaml
# modules/learn-graphs.yml
sample_size: 1000     # default 1000
reference: null       # no value: omitted from the action
```

A caller that supplies neither value runs the child exactly as its
declarations describe: `sample_size` is `1000`, and `reference` is left
out of every action that would otherwise receive it. A caller that
supplies either value overrides the declaration:

```yaml
steps:
  - name: Learn graphs
    uses: ./modules/learn-graphs.yml
    with:
      sample_size: 5000
      reference: networks/asia/true.graphml
```

A null-default parameter may only be used as the whole value of a step
parameter (`reference: {{reference}}`), because there is no text to
substitute when no value is supplied. A declared parameter must also be
used as a placeholder in at least one step; an unused declaration is a
validation error.

A placeholder the child uses but does not declare is a **required
parameter**. The caller must supply it, and validation reports it when it
is missing:

```
Step 'Call child' (workflow 'hc_bad.yml'): Unknown template variables:
['randomise']. Available variables: ['network', 'sample_size', 'series'].
Declare a default value for each missing name as a top-level workflow
key, or supply it with 'with:' in the calling workflow or --param.
```

A list default is not supported yet, so a list value is supplied by the
caller (for example `randomise: ["var_best"]`).

Because a null default forwards an omission, a module can pass a value on
only when its own caller set it:

```yaml
# modules/base.yml
reference: null

steps:
  - name: Learn graphs
    uses: ./learn-graphs.yml
    with:
      reference: {{reference}}
```

If the caller of `base.yml` omits `reference`, the inner call omits it
too. If the caller supplies it, the value flows through both calls.

### Unknown parameters

A parameter that the child neither declares, nor lists as a matrix
dimension, nor uses in a step is rejected with the accepted names:

```
Step 'Call child': Parameter 'sampl_size' is not used by workflow
'learn-graphs.yml'. Accepted: ['algorithm', 'reference', 'sample_size']
```

`action` and `output` are reserved by the executor and are rejected in a
call step's `with` block. A name may not be declared as both a parameter
and a matrix dimension.

A token the child uses but the caller does not supply is reported the
same way, so a required parameter is never silently left blank (see
above).

Tokens may be written without quotes, for example
`randomise: {{randomise}}`. See
[Values and Quoting](values_and_types.md) for the quoting rules.

### Parameters and cache keys

Parameters that are not matrix dimensions are **not** part of a cache
key. Conservative execution therefore still skips an entry when only a
parameter value has changed — use `--mode=force` to re-run. Declare the
name as a child matrix dimension when its value must distinguish cache
entries.

## Matrix and Execution

A called workflow is a complete run: it expands its own `matrix`, applies
the caller's overrides, and writes its own caches.

- A call step has no cache output of its own, so it runs once per
  workflow and is skipped on later jobs.
- When the call's `with` values reference a caller matrix variable, the
  parameters differ per combination, so the call runs once per
  combination instead.
- Conservative execution still applies inside the called workflow.

```yaml
matrix:
  network: [asia, cancer]

steps:
  - name: Learn graphs      # constant parameters: runs once
    uses: ./modules/learn-graphs.yml

  - name: Learn by label    # varies per combination: runs twice
    uses: ./modules/learn-graphs.yml
    with:
      algorithm: {{network}}
```

## Execution Modes

| Mode | Behaviour |
|------|-----------|
| `validate` (API) | Every called workflow is loaded and validated recursively; nothing executes |
| `dry-run` | Called steps are previewed as `WOULD EXECUTE` / `WOULD SKIP` |
| `run` | Called steps execute with conservative skipping |
| `force` | Called steps execute regardless of existing entries |

`cqflow run` validates automatically before it executes, so the `validate`
mode itself is reached through `execute_workflow(mode="validate")`.

## Logging

With `--log-level=all`, a call is announced before the called
workflow's own step messages:

```
[.../hc_std.yml] CALLING      Run bnlearn hc with standard ordering
[learn_graph] WOULD SKIP      Learn graph using bnlearn ...
```

The final `COMPLETED` summary counts the called workflow's steps rather
than the call step, so the totals match the work that actually ran. The
call step's result also records the parameters that were applied.

## Recursion

Recursive calls are rejected. A workflow may not call itself, directly
or through a chain:

```
Step 'Call parent': recursive workflow call detected:
parent.yml -> child.yml -> parent.yml
```

Diamond composition is allowed: two different workflows may call the
same third workflow.

## Validation and Failures

Called workflows are validated when the caller is validated: JSON
Schema, template variables, action providers, action patterns and
filters. A problem is reported against the calling step:

```
Step 'Call module' (workflow 'learn-graphs.yml'): Unknown provider 'x'
```

A called step that records an `error` status makes the call step report
`error`, and the CLI lists the child messages.

## Calling from the CLI

The same parameters can be supplied to a top-level workflow on the
command line:

```bash
cqflow run benchmark.yml --mode=run --param sample_size=5000 \
  --param reference=networks/asia/true.graphml
```

A name that matches a top-level matrix dimension replaces it, so
`--param network=asia` runs a single combination. A name that matches a
declared parameter overrides its default; the value replaces a `null`
default, so a null-default parameter is no longer omitted. Unknown names
are reported as validation errors.

## Limitations

- Parameters do not invalidate cache entries; use `--mode=force` after a
  parameter change.
- `{{...}}` placeholders in step names are not expanded.
- A parameter with a concrete default cannot be forwarded only when the
  caller sets it. Declare the forwarding parameter with a `null` default
  so that an omission stays an omission (see
  [Declaring parameters](#declaring-parameters)).
- Called step outputs are not yet available to the caller.