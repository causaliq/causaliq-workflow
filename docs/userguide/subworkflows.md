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
      algorithm: "{{algorithm}}"
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

The `with` block carries parameters for the called workflow. Template
variables are resolved in the caller's context, so typos are reported
during validation.

!!! warning "Parameters are not yet forwarded"
    Workflow parameters are not supported yet. Values in `with` are
    accepted and validated but ignored, and the called workflow cannot
    read them. Until then, keep called workflows self-contained: do not
    rely on values from the caller, and do not declare required
    (`null`) workflow-level variables in a called workflow.

`action` and `output` are reserved by the executor and are rejected in
a call step's `with` block.

## Matrix and Execution

A called workflow is a complete run: it expands its own `matrix` and
writes its own caches.

- The call step has no cache output of its own, so it runs once per
  workflow. In a workflow with a matrix, the call executes on the first
  job and is skipped on later jobs.
- Conservative execution still applies inside the called workflow, so
  repeating a call is cheap.
- The caller's matrix values and CLI parameters are not forwarded.

```yaml
matrix:
  network: [asia, cancer]

steps:
  - name: Learn graphs      # runs once, not twice
    uses: ./modules/learn-graphs.yml
```

## Execution Modes

| Mode | Behaviour |
|------|-----------|
| `validate` | Every called workflow is loaded and validated recursively; nothing executes |
| `dry-run` | Called steps are previewed as `WOULD EXECUTE` / `WOULD SKIP` |
| `run` | Called steps execute with conservative skipping |
| `force` | Called steps execute regardless of existing entries |

## Logging

With `--log-level=all`, a call is announced before the called
workflow's own step messages:

```
[.../hc_std.yml] CALLING      Run bnlearn hc with standard ordering
[learn_graph] WOULD SKIP      Learn graph using bnlearn ...
```

The final `COMPLETED` summary counts the called workflow's steps rather
than the call step, so the totals match the work that actually ran.

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

## Limitations

- Workflow parameters and defaults are a follow-up task; see the
  [roadmap](../roadmap.md).
- Called step outputs are not yet available to the caller.