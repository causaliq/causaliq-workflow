# Flush log messages to terminal immediately

Please produce a plan to ensure that log messages appear at the terminal output
immediately that the relevant action has compleleted. This is necessary to provide
assurance that the job is still running and show progress in real time.

I recently ran @causaliq-workflow/papers/variable-ordering/workflows/var-ordering.yml
which executed some slow structure learning steps and it seemed that log messages
appeared only just as the workflow finished.

## Further work which is out of scope for this task

These are deliberately outside this task:

0. __Clarify CREATE and AGGREGATE ActionPattern definitions__

Please review the current action patterns: CREATE and AGGREGATE:

- is this the correct distinction to make?
- are existing actions being assigned to the correct pattern?
- even if the distinction is relevant, do we need to expose the end-user to this distinction in the userguide?

I am beginning to think (maybe incorrectly) that the two fundamental patterns are:

- AGGREGATE - where there is a need to aggregate entries from input caches in some way to
get the required dimensions in the output (be that a cache, plot or summarisation)
  - examples are: `merge_graph`, `plot` and `summarise`
- NON-AGGREGATE - where there is no need to aggregate input entries: either because there is no
input cache (`learn_graph`, `generate_graph` or `migrate_trace`) or the inputs and the
outputs have the same dimension (`best_graph` and `evaluate_graph`)

We also have a convention that, in some cases at least, it is possible to omit
the matrix definition and the one from the input cache is used silently - for example,
with `evaluate_graph`.

- should this be provided on all NON-AGGREGATE actions which allow an input workflow cache?
- a further tweak I would like to add is the ability to use the input cache dimensions
as defualt but be able to add an extra matrix dimension with a fixed value.


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
