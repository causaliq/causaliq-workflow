# Default action parameter values

I would like to standardise and simplify how default action parameter values work including deciding whether it is necessary/desirable to expose a "null/none" type value to users.

The key aim
is **clarity and simplicity** for the end user, and a secondary aim is workflows continue to work as before as parameters or defaults ar changed as the code evolves.

My preferred approach is, if it is logically coherent:

- we do not expose the end-user to any distinction between leaving out a
  parameter to indicate a default value should be used or because the
  parameter is not applicable given other parameter values (for example,
  specifying a score type for a constraint-based BNSL algorithm);
- therefore, the end-user does not need to use a "null/none" type in
  workflows - the user just omits parameters where the default is required
  or the parameter is not relevant
- where an action parameter does have a default value, then that default
  value must be exposed as a possible value. For example, we would modify
  the `learn_graph` `randomise` action to have an explicit `no-randomise` value which would be the default. This approach hopefully solves the problem of passing default values from calling workflows to sub-workflows. Is it possible to mandate this in the code infrastructure somehow?
- the parameter section of the metadata should list the values of all
  parameters that were explicitly specified **and** those given default values, **but not** those which were not relevant
- if necessary, we can define an explicit "NotRelevant" type (clearer than null or none?) to be used **internally** in the code.

Could you commnt on this, and agree an approach with me

## Further work which is out of scope for this task

These are deliberately outside this task:

0. __Simplify and standardise quote usage for parameter values__

0. __Declaration of default values in workflows__

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

