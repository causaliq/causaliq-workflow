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
caller's mode, the bound parameters and the extended stack. The child
therefore expands its own matrix and writes its own caches.

### Parameter binding

`with` values are resolved in the caller's context and then bound by
`_bind_parameters` (`workflow/matrix.py`):

- a name that matches a child matrix dimension replaces that dimension's
  values (a scalar becomes `[value]`, a list is used as given);
- every other name becomes a template variable of the child.

A value that is exactly one `{{name}}` token is bound natively, so an
integer matrix override stays an integer. Matrix overrides are removed
from the variable map, so a list-valued override cannot leak into
`{{name}}` substitution. Binding is pure: the parsed child is never
mutated, which matters when the same parent job runs a call twice.

Parameters never add a matrix dimension, so they are not part of a cache
key. Conservative execution therefore still skips an entry when only a
parameter value changed; `--mode=force` re-runs it. Authors who need a
parameter to distinguish cache entries declare it as a matrix dimension
(for example `alpha: [null]`) and let the caller override it.

Top-level keys other than `matrix` and `steps` are declared parameters
with defaults. A default is a scalar, a list of scalars or `null`. A list
default is a single value: `_resolve_template_variables` returns the list
itself for a whole-value `{{name}}` token, and `_bind_parameters` uses it
as the override values when the called workflow declares the same name as
a matrix dimension. That is how a caller-level list fans out inside a
callee's matrix while the call step itself still runs once.

A `null` default declares a parameter with no value: binding it to a step
template yields `None`, which the action boundary drops, so the parameter
reaches the action as omitted. A placeholder that is not declared is
required, so a caller or the CLI must supply it;
`_validate_template_variables` (and `_missing_variable_errors` for
dict-based execution) reports it when it is missing. Unknown names are
reported by `_call_parameter_errors` with the accepted names. Ineffective
declarations — an unused parameter, a null-default parameter used as part
of a value, or a list-default parameter used anywhere other than as a
whole step parameter value — are reported by
`_parameter_declaration_errors`. A step's `name` counts as a use, because
the executor expands its `{{placeholder}}` tokens for each job.

Validation resolves a call step's `with` values in the caller's context
before binding them to the called workflow, so a forwarded matrix value
or declared parameter reaches the child as a value. Without that step the
child would receive the literal `{{placeholder}}` text and reject it as
an invalid action parameter. A call whose parameters vary across the
caller's matrix is validated once, for the caller's first job.

### Run-once rule

`_runs_once(step, matrix)` treats a call step as single-run unless its
`with` values reference a matrix variable of the calling workflow. A
constant call would do identical work on every job, so it runs once and
is skipped later; a call whose parameters vary resolves to different
parameters per combination, so it runs once per combination.

## Validation

`_load_child_workflow` loads and validates each called workflow:
`validate_workflow`, `_validate_template_variables` (with the caller's
parameter names available), and `_validate_workflow_actions`. The
validation pass then binds the caller's parameters and recurses through
`_validate_all_entries`, so `execute_workflow(mode="validate")` covers the
whole tree.

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
    "parameters": {"variant": "two"},   # omitted when none
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

- Parameter values invalidating or keying cache entries.
- Step output chaining from a called workflow to its caller.
- Rolling child step counts into the CLI summary.
- Memoising loaded child workflows across parent jobs.