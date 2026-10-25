# Workflows parameters

Status: implemented (24 October 2026). Verified with black, isort,
flake8, mypy, `scripts/check_code_rules.py` (0 breaches) and the full
pytest suite at 100% coverage.

## Agreed behaviour

- Workflow parameters are specified in the `with:` clause of the calling
  workflow, or with `--param NAME=VALUE` on the CLI.
- A parameter name that matches a matrix dimension of the called workflow
  replaces that dimension's values (a scalar becomes `[value]`, a list is
  used as given). Parameters never *add* a dimension.
- A parameter name that matches a declared parameter (a top-level scalar
  key of the called workflow) overrides its default. A `null` default
  declares a required parameter.
- Any other parameter binds as a `{{name}}` template variable.
- A parameter that the called workflow neither declares, nor lists as a
  matrix dimension, nor uses in a step `with:` block is a validation
  error listing the accepted names.
- `with` values are resolved in the caller's context; a value that is a
  single `{{name}}` token binds the native value so a matrix override
  keeps its type. The same rule applies inside a called workflow, so a
  list parameter reaches the action as a list rather than as text.
- Parameters do not enter the cache key. Conservative execution still
  skips existing entries; a parameter change needs `--mode=force`.
- A call step runs once per workflow unless its `with` values reference a
  caller matrix variable, in which case it runs once per combination.
- `id`, `description` and `root_dir` are no longer hardwired. `id` and
  `description` are ordinary declared parameters; `root_dir` was never
  implemented and is removed from the documentation.
- `matrix` and `steps` are reserved. Declaring a name as both a parameter
  and a matrix dimension is a validation error. `action` and `output`
  remain reserved in a call step's `with`.

## Scope of this task

Hat 1 only: caller/CLI parameters, parameter defaults, required
parameters, per-combination call execution, removal of the hardwired
`id`/`description`/`root_dir` names, tests and documentation.

Follow-ups logged by this task:

- Rename the `execute_workflow(..., cli_params=...)` keyword to
  `parameters` (Hat 2, public API).
- Optionally invalidate or key cache entries on parameter values.
- Null/`None`/defaults semantics are deferred: whether `null` means
  "not applicable" (a value) or "required" (absence), and whether a
  parameter default may be a list. Daily use needs neither, because a
  caller can supply a list or an empty list directly.



## Further work which is out of scope for this task

These are deliberately outside this task:

1. __Values audit__

   - For discovery, knowledge and analysis actions, move input-like fields out of `result` into `parameters`.
   - Check completeness and usefulness of each action’s metadata.
   - Update action contract tests and API metadata documentation.
   - This is the step that turns `inputs: {}` into the real effective-parameter record.

2. __Metadata catalogue and generated documentation__

   - Add a central catalogue of each action’s inputs, results and provenance expectations.
   - Generate API documentation and CLI discovery from it.
   - Add contract tests that every registered action is catalogued.

3. __`history` step parameter__

   - Support `standard`, a list of field paths, or `all`.
   - Populate `history` for one-to-one aggregate steps.
   - Add workflow/cache tests and user-guide documentation.

4. __Reporting capabilities__

   - Add `filter` support to the analysis `plot` action.
   - Add categorical group-by support to `summarise`.
   - Reuse the shared reporting view and update analysis/workflow docs and tests.

5. __`merge_graphs` many-to-one metadata__

   - Define action-specific reductions for n:1 merges.
   - Generic history copying is not sufficient for many-to-one actions.
   - Add tests and document the reduction rules.

6. __Hat 2 clean-up__

   - Remove the deprecated `WorkflowCache.update_entry()`.
   - Remove remaining UPDATE-pattern remnants and dead write paths.
   - Consolidate duplicate metadata flatteners.
   - No behavioural change.

7. __Smaller metadata backlog__


- Expand `{{series}}`-style placeholders in workflow step names.
- Improve exported `evaluate_graph` metrics JSON readability with line feeds.
- Clarify metrics for failed/empty input graphs so they are not presented as evaluation failures.

