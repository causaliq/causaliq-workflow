# Reusable Workflow Design

## Decision

A step invokes another workflow when its `uses` value is a relative path
beginning `./` or `../`. This is the GitHub Actions convention for
local reusable workflows and keeps workflow calls disjoint from action
provider names without a new step key or schema change.

## Grammar

| `uses` value | Meaning |
|---|---|
| `causaliq-discovery` | Action provider resolved by `ActionRegistry` |
| `./modules/learn.yml` | Workflow call, relative to the declaring file |
| `../shared/base.yaml` | Workflow call in a parent directory |

The target must use a `.yml` or `.yaml` suffix. `with` supplies
parameters for the called workflow.

## Alternatives

| Option | Assessment |
|---|---|
| `call: ./x.yml` | Explicit, but adds a third step kind plus schema, pre-validation and dispatch changes |
| `uses: causaliq-workflow` with `with.workflow:` | Collides with the built-in provider and reserves a parameter name |
| `uses: ./x.yml` | Chosen: standard CI convention, no schema change, reuses `uses` and `with` |

## Call Stack

`WorkflowFrame` records the canonical path and directory of each active
workflow. `execute_workflow` seeds the stack from the parsed workflow
path, and the `source_path` argument overrides it. Each call extends the
stack.

- Relative targets resolve against the innermost frame's `source_dir`.
- A target already on the stack is a recursive call and is rejected.
- `os.path.normcase` makes path comparison case-insensitive on Windows.
- Two sibling calls to the same child are allowed: the stack is a chain,
  not a visited set.

When no source path is known, relative targets resolve against the
working directory and the root workflow cannot be detected as a cycle.

## Execution Model

A call step delegates to `_execute_jobs` with the child workflow, the
caller's mode, an empty `cli_params` and the extended stack. The child
therefore expands its own matrix and writes its own caches.

`_runs_once` treats a call step as single-run because it has no cache
output and parameters are not forwarded, so a repeated call would be
identical. When parameters land, a call whose resolved parameters differ
per matrix combination must run per combination.

## Validation

`_load_child_workflow` loads and validates each called workflow:
`validate_workflow`, `_validate_template_variables` and
`_validate_workflow_actions`. The validation pass then recurses through
`_validate_all_entries`, so `--mode=validate` covers the whole tree.

Call steps are excluded from action-provider, action-pattern and filter
validation. `with.action` and `with.output` are rejected because the
executor owns those keys.

## Reporting

The call step records a summary:

```python
{
    "status": "success",       # error / would_execute / would_skip
    "workflow": "<canonical path>",
    "jobs": 2,
    "steps": [
        {"name": "Child record", "status": "success"},
        {"name": "Child record", "status": "success"},
    ],
}
```

Called step failures are folded into `status: error` plus an `errors`
list, so the CLI report treats a failing call like an ordinary failing
step.

The CLI report counts a call step's nested step results in place of the
call itself, so a parent that calls one twelve-step workflow reports
twelve steps, not one.

Call steps are announced through the step logger (`CALLING`) before the
called workflow's own step messages, so the log reads as a call followed
by its work.

## Deferred

- Workflow parameters, defaults and precedence over matrix and step
  parameters.
- Step output chaining from a called workflow to its caller.
- Rolling child step counts into the CLI summary.
- Memoising loaded child workflows across parent jobs.
- Relative `root_dir` semantics, which the user guide describes but the
  executor does not yet implement.