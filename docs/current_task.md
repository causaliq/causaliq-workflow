# Simplification of Workflow Caches and Action Patterns

The workflow cache model and the action patterns declared by analysis actions
were simplified so that caches hold typed results rather than mixed metadata,
and so that only two patterns remain. The goal is simpler code and a simpler
interface for workflow authors.

## Simpler cache model

- Each cache holds a single object type, pinned by the first write.
- Each entry holds provenance metadata plus exactly one object of that type.
- Metrics are typed objects in their own cache, not extra metadata on the
  graph entry that produced them.
- A failed run records provenance (status and failure reason) and no object,
  so a failure can never be mistaken for a result or scored. Failures still
  appear in downstream caches: evaluation writes a provenance-only entry to
  the metrics cache for each failed input, so failure cases can be analysed.
- An action writes at most one object per key; entries are never lumped
  together under generated names such as `dag_0`, `dag_1`.
- A workflow file can write to several typed caches, so the number of caches
  scales with object types rather than pipeline stages.
- Entries are distinguished by ordinary matrix keys; there is no special
  reserved key or per-step pinning.

## Two action patterns

| Pattern | Reads a workflow cache | Requirements |
|---------|------------------------|--------------|
| CREATE | No | Output cache and matrix |
| AGGREGATE | Yes | Input cache(s) and output cache |

A step that writes a plain file instead of a cache runs **once**, outside
matrix expansion, because a file output has no cache dimensionality.

`UPDATE` and `NOCACHES` were removed. `UPDATE` is unnecessary now that
analysis results are written as objects to their own caches, and `NOCACHES`
is redundant because `plot` reads a metrics cache and the run-once rule
covers file outputs.

## What changed in the analysis actions

- `evaluate_graph` writes a `metrics` object to an output cache (AGGREGATE)
  instead of adding results to the learned graph's entry.
- `plot` reads a metrics cache (AGGREGATE) and writes one image (run-once).
- `best_graph` writes a `dag` to its own output cache (AGGREGATE).
- `merge_graphs` continues to aggregate PDGs into a `pdg` object
  (AGGREGATE).
- `migrate_trace` writes a `dag` per key, without the `dag_0..dag_n`
  lumping that occurred when the matrix omitted a distinguishing dimension.
- `summarise` continues to write one CSV row per matrix combination. It is
  planned to write workflow caches and LaTeX tables as well, which would
  supersede the earlier idea of a separate `table` action.

## Compatibility

Workflow caches are treated as disposable until the Zenodo deposit, so no
data migration tooling is provided: re-run the workflow to regenerate a
cache in the new shape. Import and export tooling keeps using the permissive
write path, whilst action writes enforce the one-object and cache-type rules.

## See also

- [Action Patterns](https://causaliq.org/projects/causaliq-workflow/userguide/action_patterns/)
- [Cache Type Model](https://causaliq.org/projects/causaliq-workflow/architecture/cache_type_model/)
- [causaliq-workflow documentation](https://causaliq.org/projects/causaliq-workflow/)
