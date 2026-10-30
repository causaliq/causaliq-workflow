# Correct and improve log messages

Please develop a plan to correct and improve the log messages as follows:

1. correct the skipped/executed counts in the final summary completed message in this example:

```text
(py311) PS C:\dev\causaliq\causaliq-research> cqflow run papers/variable-ordering/workflows/var-ordering.yml --log-level all --mode run
2026-10-29 21:11:13 [causaliq-workflow] LOADING workflow from: papers\variable-ordering\workflows\var-ordering.yml
2026-10-29 21:11:13 [causaliq-workflow] VALIDATING workflow syntax and parameters...
2026-10-29 21:11:15 [causaliq-workflow] VALIDATED workflow successfully
2026-10-29 21:11:15 [causaliq-workflow] EXECUTING workflow in run mode...
2026-10-29 21:11:15 [./legacy.yml] CALLING      Migrate legacy results into CausalIQ legacy.db cache
2026-10-29 21:11:15 [migrate_trace] SKIPPED      Migrate legacy graphs for series BNLEARN/HC_STD [series=BNLEARN/HC_STD, network=asia, sample_size=1000]
2026-10-29 21:11:15 [migrate_trace] SKIPPED      Migrate legacy graphs for series BNLEARN/HC_OPT [series=BNLEARN/HC_OPT, network=asia, sample_size=1000]
2026-10-29 21:11:15 [migrate_trace] SKIPPED      Migrate legacy graphs for series BNLEARN/HC_BAD [series=BNLEARN/HC_BAD, network=asia, sample_size=1000]
2026-10-29 21:11:15 [./bnsl.yml] CALLING      Perform BNSL using CausalIQ algorithms putting results in learn.db
2026-10-29 21:11:15 [./bnsl_subflow.yml] CALLING      Run bnlearn hc with standard ordering
2026-10-29 21:11:15 [learn_graph] SKIPPED      Learn graph using bnlearn for BNLEARN/HC_STD [series=BNLEARN/HC_STD, network=asia, sample_size=1000]
2026-10-29 21:11:15 [./bnsl_subflow.yml] CALLING      Run bnlearn hc with optimal ordering
2026-10-29 21:11:15 [learn_graph] SKIPPED      Learn graph using bnlearn for BNLEARN/HC_OPT [series=BNLEARN/HC_OPT, network=asia, sample_size=1000]
2026-10-29 21:11:15 [./bnsl_subflow.yml] CALLING      Run bnlearn hc with worst ordering
2026-10-29 21:11:15 [learn_graph] SKIPPED      Learn graph using bnlearn for BNLEARN/HC_BAD [series=BNLEARN/HC_BAD, network=asia, sample_size=1000]
2026-10-29 21:11:15 [causaliq-workflow] COMPLETED 6 steps: 3 executed, 3 skipped (3 new entries)
```

2. improve the error messages in the final ERRORS: summary message so that they include the matrix parameter values. If it is not already implemented, place a limit on the number of errors reported - perhaps 10, with a message such as "... and xxx more errors" detailing how many more errors there are.

```text
(py311) PS C:\dev\causaliq\causaliq-research> cqflow run papers/variable-ordering/workflows/var-ordering.yml --log-level all --mode run
2026-10-29 21:26:03 [causaliq-workflow] LOADING workflow from: papers\variable-ordering\workflows\var-ordering.yml
2026-10-29 21:26:03 [causaliq-workflow] VALIDATING workflow syntax and parameters...
2026-10-29 21:26:05 [causaliq-workflow] VALIDATED workflow successfully
2026-10-29 21:26:05 [causaliq-workflow] EXECUTING workflow in run mode...
2026-10-29 21:26:05 [./legacy.yml] CALLING      Migrate legacy results into CausalIQ legacy.db cache
2026-10-29 21:26:05 [migrate_trace] SKIPPED      Migrate legacy graphs for series BNLEARN/HC_STD [series=BNLEARN/HC_STD, network=asia, sample_size=10]
2026-10-29 21:26:05 [migrate_trace] SKIPPED      Migrate legacy graphs for series BNLEARN/HC_OPT [series=BNLEARN/HC_OPT, network=asia, sample_size=10]
2026-10-29 21:26:05 [migrate_trace] SKIPPED      Migrate legacy graphs for series BNLEARN/HC_BAD [series=BNLEARN/HC_BAD, network=asia, sample_size=10]
2026-10-29 21:26:05 [./bnsl.yml] CALLING      Perform BNSL using CausalIQ algorithms putting results in learn.db
2026-10-29 21:26:05 [./bnsl_subflow.yml] CALLING      Run bnlearn hc with standard ordering
2026-10-29 21:26:06 [learn_graph] FAILED       Learn graph using bnlearn for BNLEARN/HC_STD [series=BNLEARN/HC_STD, network=asia, sample_size=10]
2026-10-29 21:26:06 [./bnsl_subflow.yml] CALLING      Run bnlearn hc with optimal ordering
2026-10-29 21:26:06 [learn_graph] FAILED       Learn graph using bnlearn for BNLEARN/HC_OPT [series=BNLEARN/HC_OPT, network=asia, sample_size=10]
2026-10-29 21:26:06 [./bnsl_subflow.yml] CALLING      Run bnlearn hc with worst ordering
2026-10-29 21:26:07 [learn_graph] FAILED       Learn graph using bnlearn for BNLEARN/HC_BAD [series=BNLEARN/HC_BAD, network=asia, sample_size=10]
2026-10-29 21:26:07 [causaliq-workflow] COMPLETED 6 steps: 3 skipped, 3 failed
2026-10-29 21:26:07 [causaliq-workflow] ERRORS:
  Run bnlearn hc with standard ordering: Learn graph using bnlearn for BNLEARN/HC_STD: failed
  Run bnlearn hc with optimal ordering: Learn graph using bnlearn for BNLEARN/HC_OPT: failed
  Run bnlearn hc with worst ordering: Learn graph using bnlearn for BNLEARN/HC_BAD: failed
```

3. Each call to a sub-workflow should have a `CALLING` message as now, but additionally a `COMPLETED` message just before it returns control to the calling workflow. This should detail the cummulative numbers of steps skipped, failed and executed  etc. which this workflow and any sub-workflows it calls have performed.


4. Replace the values of the `--log-level` (`all`, `summary`, `none`) with an integer value that
represents the maximum depth at which messages are reported (maybe rename the parameter as `log-depth`?), as follows
  - 0: no message output - equivalent to `none` now
  - 1: summary messages from the top-level workflow are reported only - equivalent to `summary` now for a standalone workflow. This would be the default value.
  - 2: include log messages from the top-level steps - both actions it performs, and calls to sub-workflows but **not** any messages from within sub-workflows - equivalent to `all` for a standalone workflow, but omits messages from any sub-workflows
  - 3: all messages from top-level and next level down sub-workflows but not from any deeper sub-workflows
  - 3+: the pattern continues, including messages at greater depths

5. Delineate the transitions into and out of sub-workflows more clearly visually - perhaps by indenting messages according to call depth

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

