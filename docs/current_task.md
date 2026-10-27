# Default workflow parameter values

Provide default values for **action** parameter values at the workflow level using the following syntax:

```yaml
   param-name: default-value
```

These default values should be defined before the matrix and steps sections of the workflow. `param-name` must be used as a placeholder in some of the steps of the workflow i.e. `{{param-name}}`. Having specified a default value in this way, workflows calling this workflow do not have to specify a value for `param-name` - the `default-value` will be used. However, if the calling workflow does specify a value for `param-name` this will override the `default-value`. Note that workflows which include default parameter values can still be run standalone - in that case, default parameter values provide a convenient way of defining
values for a parameter that is used in multiple steps.

A special value of `null` is allowed for the `default-value` in the default value declaration, that is:

```yaml
    param-name: null
```

In that case, the effect would be as if the parameter had been omitted as a parameter in the actions. For example, a default declaration of:

```yaml
   reference: null
```

would result in the refernce parameter being **omitted** in an action step which had a parameter specification of 

```yaml
   reference: {{reference}}
```
  
This is useful in the case where actions in called sub-workflows have parameters which need to be omitted in some calls, and specified in others. 

Could you commnt on this, and agree an approach with me

## Further work which is out of scope for this task

These are deliberately outside this task:

0. __Simplify and standardise quote usage for parameter values__

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

