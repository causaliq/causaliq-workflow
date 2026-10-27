# Reducing and standardising quotes usage in workflows

Please could you consider these suggestions and suggest a viable plan for reducing and standardising quote usage.

Even as the author of CausalIQ I find it confusing when and where
quotes are needed in workflow matrix and parameter values. My aim is to reduce friction for users, whilst being absolutely clear how the system works.

I think some of the issues may be because we are using off-the-shelf YAML and expression parsers. I think we should continue to use off-the-shelf capablities, but maybe we need to preprocess input to them to shield the end-user from their
pecuilarities.

For example, can we dispense with requiring quotes for parameter values - for most of their lifetime they could be handled as strings, but coerced to int or float 'near' the action. Workflow code would attempt to understand strings as parameters first, before assuming they are values.  One remaining need for quotes would be to differentiate a parameter name from a value of the same name i.e. description == "description"

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

