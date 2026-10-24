# Workflows can call other workflows

Please propose a syntax for one CausalIQ YAML workflow calling another YAML workflow (used in place of the
uses-with-action structure employed to invoke a package action). The syntax should
be modelled on/inspired by standard CI YAML syntax. The `with` keyword can be used
to specify parameters for the called sub-workflow.

At this stage, parameters are not (fully) supported for causaliq workflows - this
will be tackled in a subsequent task. For this task it is sufficient if the
invoked workflows ignores any parameters specified for it.

Recursive calling of workflows is not allowed and should be checked for

## Further work which is out of scope for this task

These are deliberately outside this task:

0. __Workflow parameters__

   - should we declare parameters in a workflow, or can we just adopt a 
     `tolerant` paradigm that any parameters specified just overwrite valu
     in the called workflow, and any irrelevant parameters are silently ignored?
   - workflow parameters overwrite those with the same name in matrix and
     step parameters
   - workflow paramaters can be defined in the called workflow - these effectively
     act as defaults
   - should it be possible to specify parameters when a workflow is invoked from
     the CLI? - it would complicate validation of command line parameters

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

