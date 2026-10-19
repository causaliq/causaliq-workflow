# Cache Type Model

## Purpose

This document is the design record for the simplified workflow cache and
action model introduced to remove the ambiguity in mixed-object cache
entries and to reduce the behavioural action patterns to two. It is the
single source of truth for the decisions taken across `causaliq-core`,
`causaliq-workflow`, `causaliq-analysis` and `causaliq-discovery`.

## Problems Addressed

- Entries could hold zero, one or more objects of different types, so an
  action that read a graph had no reliable way to know which one was
  intended. `evaluate_graph` read the first graph by insertion order, so on
  the common `(pdg, dag)` entries it evaluated the PDG rather than the DAG.
- Entries mixed two data kinds with different write semantics: additive
  provenance metadata and typed objects replaced by key.
- Metadata mixed processing information (action, timestamp, counts) with
  object results (for example graph metrics).
- The `ActionPattern`s were confusing, though they were behavioural rather
  than cosmetic.

## Design Decisions

### 1. Cache type is a property of the cache

One cache holds one object type. The type is pinned on the first write and
every later write must match. Selecting a type therefore means choosing the
cache, which workflows already express with `input` and `output`.

The type is stored in the reserved configuration entry alongside
`matrix_key_order`, so no schema change is required. The declaration is
implicit: the first typed write pins it.

### 2. Provenance metadata and at most one object

Every entry holds provenance metadata and at most one object: exactly one for
a successful run, none for a failed run. Provenance is the namespaced
`provider -> action -> fields` structure already used, carrying the action
name, timestamp, parameters, counts and outcome. Object results, including
metrics, are the single typed object rather than metadata.

### 3. Metrics are objects

Results placed in workflow caches are typed objects, including metrics.
`evaluate_graph` writes a `metrics` object to an output cache rather than
mutating metadata on the input entry. The `UPDATE` pattern is therefore
unnecessary. Metric values live only in that object: the entry metadata
records provenance (`status`, `reference`, `evaluated_graph`) and never
duplicates the values, so `summarise` and `plot` read the object.

Exported `_meta.json` files hold `matrix_values`, `created_at` and
`metadata` only. The object map is omitted because a cache holds a single
type: the object file's name and extension (`dag.graphml`,
`metrics.json`) already identify it, and import reconstructs the format
from the extension.

### 4. Failure entries

A failed run writes provenance (status and the failure reason) and **no
object**. An object would be indistinguishable from the result of a
successful run — a legitimate edgeless graph, for instance — and could be
scored, so failures are recorded only in metadata. The entry replaces any
prior entry for the key: the latest run wins, including when a failure
replaces a previously successful result.

Consumers propagate failures rather than hiding them: `evaluate_graph` does
not compute metrics from a failed input, but writes a provenance-only entry
to the metrics cache (`status: input_failed` with the upstream error), so
failure cases can be analysed by sample size, algorithm or any other matrix
key. Export writes `_meta.json` for such an entry and no data file.

### 5. Discrimination is an ordinary matrix key

A user distinguishes entries (for example by `role`) by adding a normal
matrix key and fixing it to a constant in a daughter workflow's matrix.
There is no special key, reserved name or per-step pinning.

### 6. One object per key

An action that would write more than one object of the cache's type for a
key is an error. This removes the `migrate_trace` `dag_0..dag_n` lumping,
which only occurred when the matrix omitted a distinguishing dimension (for
example `seed`).

### 7. Caches scale with object types

One workflow file can write to several typed caches, so the number of
caches scales with the number of object types rather than with pipeline
stages.

### 8. CREATE and AGGREGATE only

Two behavioural patterns remain, and they are distinguished by whether the
step reads a workflow cache:

| Pattern | Cache input (`input` points at `.db`) | Requirement |
|---------|---------------------------------------|-------------|
| CREATE | No | `output` cache and `matrix` |
| AGGREGATE | Yes | `input` cache(s); `output` optional |

`UPDATE` and `NOCACHES` are removed. `plot` becomes AGGREGATE because it
reads a metrics cache rather than a CSV file.

`ActionPattern` is retained as a two-value enum for explicit declaration and
validation, while the executor may also derive AGGREGATE from the presence
of a `.db` cache input.

### 9. `learn_graph` graph and trace caches

`learn_graph` reuses the `trace` argument name, but it is now a workflow
cache path (`.db`). When `trace` is provided the trace object is written to
that cache; when it is omitted, no trace is produced. The graph is written
to `output`.

## Cache Entry Structure

```json
{
  "matrix_values": {"network": "asia", "sample_size": "1k"},
  "metadata": {
    "causaliq-analysis": {
      "evaluate_graph": {
        "action": "evaluate_graph",
        "timestamp": "2026-10-16T09:00:00Z",
        "status": "success",
        "reference": "networks/asia/asia.xdsl"
      }
    }
  },
  "objects": {
    "metrics": {"format": "json", "content": "{\"f1\": 0.91}"}
  }
}
```

A failed entry uses the same shape with `status: "input_error"` and an
`error` field, and no object at all:

```json
{
  "matrix_values": {"network": "asia", "sample_size": 10},
  "metadata": {
    "causaliq-discovery": {
      "learn_graph": {
        "status": "input_error",
        "error": "variable asia must have at least two levels"
      }
    }
  },
  "objects": {}
}
```

## Compatibility

Existing caches are treated as disposable until the Zenodo deposit, so no
data migration tooling is provided. During the transition the legacy write
path remains permissive; one-object and type enforcement applies to the
typed write API first, then globally once all producers have migrated.

## See Also

- [Workflow Cache Design](workflow_cache_design.md) - overall cache
  architecture
- [Cache Object Model](cache_object_model.md) - object types and lookup
- [Action Patterns](../userguide/action_patterns.md) - user-facing
  pattern guide
