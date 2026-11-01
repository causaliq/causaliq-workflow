# Review ActionPattern definitions

Please review the current action patterns: CREATE and AGGREGATE:

- is this the correct distinction to make?
- do we need this concept?
- are existing actions being assigned to the correct pattern?
- even if the distinction is relevant, do we need to expose the end-user to this distinction in the userguide?

I am beginning to think (maybe incorrectly) that the two fundamental patterns are:

- AGGREGATE - where there is a need to aggregate entries from input caches in some way to
get different dimensions in the output (be that a workflow cache matrix definition, or plot or summarisation dimensions) - might also be thought of as a GROUP-BY
  - examples are: `merge_graph`, `plot` and `summarise` 
- NON-AGGREGATE - where there is no need to aggregate input entries: either because there is no
input cache (`learn_graph`, `generate_graph` or `migrate_trace`) or the inputs and the
outputs have the same dimension (`best_graph` and `evaluate_graph`)

We also have a convention that, in some cases at least, it is possible to omit
the matrix definition and the one from the input cache is used silently - for example,
with `evaluate_graph`. Maybe this can apply to all NON-AGGREGATE actions.


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

6. __Smaller metadata backlog__

- Improve exported `evaluate_graph` metrics JSON readability with line feeds.
- Clarify metrics for failed/empty input graphs so they are not presented as evaluation failures.

7. __Hat 2 tasks__

- `has_action_metadata` / `serialise_objects` retirement
- `store_failure_result` → `put_failure`
- splitting the legacy `test_workflow.py` /test_workflow_shell_and_edge_cases.py` suites
