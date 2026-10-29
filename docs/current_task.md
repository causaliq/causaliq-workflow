# Workflow parameter support list type

Please develop a plan (or pushback if you don't think it is a good idea
or it is very difficult) to declare default workflow parameters with list values
with either of the following two syntaxes:

```yaml
network: [asia, sports]
```

or 
```yaml
network:
  - asia
  - sport
```

The ```{{network}}``` placeholder can then be used to pass these lists to sub-workflows
- please see @causaliq-research/papers/variable-ordering/workflows/bnsl.yml
as an example.

## Substitute placeholders in step names

Currently placeholders such as `{{series}}` in the example below are not being 
substituted when they appear in the `name` element of a workflow step.

Please devise a plan for fixing this.

```yaml
steps:
  - name: "Learn graph using bnlearn for {{series}}"
```


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

