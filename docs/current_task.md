# Code tidy-up

Please draw up a (staged?) plan for the following "Hat-2" refactor / tidy ups
if they remain relevant and sensible to do:

- `has_action_metadata` / `serialise_objects` retirement
- `store_failure_result` → `put_failure`
- splitting the legacy `test_workflow.py` /test_workflow_shell_and_edge_cases.py` suites
- fold `_aggregation_from_pattern` into `_is_aggregation_step`
- rename the "aggregation" vocabulary in `aggregation.py`/`_apply_aggregation`,


## Further work which is out of scope for this task

These are deliberately outside this task:

0. __dry run fails with non-existent input caches__

0a. __more hat2__

- `tests/unit/test_workflow_aggregation.py` is still the last oversize legacy suite (93 tests / ~1800 lines) — same split treatment would apply.

- Legacy `put` remains permissive (`test_legacy_put_accepts_multiple_objects`) and `store_action_result` still accepts `cache=None`; both are candidates for a future contract tidy.

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


