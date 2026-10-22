# Continue standardisation of workflow metadata

Looking at the metadata produced by the `causaliq-discovery`/`learn_graph` 
action and `causaliq-discovery`/`evaluate_graph` actions I see that there is
redundant, misplaced and missing metadata.

In order to limit scope, I want to first tackle the issues which occur across 
all actions and which require work in the core workflow engine.

I would then look at remaining specific metadata issues for each action in separate tasks. Only then will I start to tackle the major roadmap items like metadata history.

## Remove top-level `created_at` entry

Unless it causes major design issues, please remove **`created_at`** which says when the entry is inserted into cache and is not of interest. The important metadata is `provenance>started_at`, when the action started.

## Standardise `provenance` across all actions

My belief is that the `provenance` information should be the **same across all
actions**, and should consist only of:

* `provider` - as now, the package name e.g. `causaliq-analysis`
* `provider_version`, `workflow_version` - as now, e.g. "v0.6.0.dev1"
* `action` - as now, e.g. `evaluate_graph`
* `started_at` - as now but renamed as `started` and fractional seconds not required and should be local time , e.g. "2026-10-22T06:06:16.24+01:00" indicating a local BST time
* `duration_seconds` should be renamed as `elapsed` but continue to be float seconds (6 d.p.) as now
* `environment` structure should be as now

Note:

* `provenance` is not yet been filled for all actions - this can be tackled when
  we go on to look at each action in turn unless changes are needed in the core workflow engine
* `provenance>finished_at` is redundant and should be removed

## Infrastructral work to split `results` into `results` and `parameters`

Perform any work in `causaliq-workflow` and **minimal** work on other packages
 that is needed to support separate `parameters` and `results` metadata sections.

**Note** most of this work may already have been done. However, we should
rename `inputs` section to `parameters` as this is more in line with our user
documentaton terminology.

Any action-specific movement of values from `results` to `parameters` can
be left to subsequent tasks.


## Further work which is out of scope for this task

These are deliberately outside the structural standardisation and remain in `causaliq-workflow` and its actions:


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

