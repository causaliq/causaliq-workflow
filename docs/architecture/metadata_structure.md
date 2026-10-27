# Metadata Structure

## Purpose

This document is the design record for schema version 2 of the metadata
stored with workflow cache entries and exported as `_meta.json`. It
separates four concerns that were previously mixed together:

- **provenance** — who produced the entry, when, and in what environment;
- **parameters** — the effective parameters used by the action;
- **result** — what the action produced;
- **history** — metadata inherited from earlier actions.

The structure is established first. A later task audits each action's
values (moving parameter-like keys into `parameters` and checking
completeness), and a further task populates `history` through a reserved
`history` step parameter.

## Problems Addressed

- A single metadata dictionary mixed input parameters (`algorithm`) with
  results (`status`, `elapsed_seconds`), so consumers could not tell
  configuration from outcome.
- The `provider -> action -> fields` nesting was redundant once an entry
  was always written by one action.
- Provenance lacked the action start time, the provider and workflow
  versions, and the runtime environment, so reproducibility depended on
  external records.
- Filters could not address metadata from earlier actions without either
  copying everything or merging caches by hand.

## Envelope

```json
{
  "schema_version": 2,
  "matrix_values": {
    "series": "BNLEARN/HC_STD",
    "network": "asia",
    "sample_size": 1000
  },
  "metadata": {
    "provenance": {
      "provider": "causaliq-discovery",
      "provider_version": "0.2.0.dev1",
      "workflow_version": "0.6.0.dev9",
      "action": "learn_graph",
      "started": "2026-10-22T06:06:16+01:00",
      "elapsed": 3204.4,
      "environment": {
        "os": "Linux v6.8.0",
        "cpu": "AMD EPYC 7763",
        "python": "3.12.4",
        "ram": 64
      }
    },
    "parameters": {},
    "result": {
      "status": "ok",
      "algorithm": "hc",
      "variant": "bnlearn",
      "sample_size": 1000,
      "num_nodes": 8,
      "num_edges": 8,
      "algorithm_seconds": 3200.1,
      "elapsed_seconds": 3201.5
    },
    "history": {}
  }
}
```

- `parameters` holds the effective parameters used by the action: values the
  user supplied plus the declared defaults that applied. Parameters that
  do not apply to the action in that configuration are absent, never
  `null`; see `causaliq-core/docs/architecture/action_parameter_contract.md`.
- `history` stays empty until the history-population task.
- Failure entries use the same shape with `result.status` and
  `result.error`, and no object file.
- `objects` remains omitted from cache exports because a cache holds one
  object type and the object filename identifies it.
- `created_at` is not part of the metadata contract. The SQLite cache keeps
  an internal record time column for ordering, but it is not exported or
  listed.

## Block Ownership

| Block | Written by | Contents |
|-------|------------|----------|
| `provenance` | Framework | Provider, versions, action, start time, elapsed seconds, environment |
| `parameters` | Action | Effective parameters used by the action |
| `result` | Action | Status, error, action-measured timings, counts, derived values |
| `history` | Framework (future) | Metadata inherited from earlier producers |
| `matrix_values` | Cache | Experimental design key |

Actions never construct the envelope. During the structure phase they
may return a flat metadata mapping, which the framework places in
`result`; as each action is audited it adopts the explicit
`ActionMetadata` mapping holding `parameters` and `result`. The framework
adds `provenance` and `history` exactly once.

## Provenance

### Timestamps and duration

- `started` is the local time at which the action started, as an ISO 8601
  value with an offset and second precision (for example
  `2026-10-22T06:06:16+01:00`).
- `elapsed` is measured with a monotonic clock rather than by subtracting
  wall-clock timestamps, so a clock adjustment cannot corrupt it.
- There is no finish timestamp: it would duplicate `started + elapsed`.
- `created_at` (the cache record time) is not metadata and is not exported
  or listed. The SQLite column remains internal to `TokenCache`, which is
  shared with the long-lived LLM caches.

### Versions

- `provider_version` comes from the provider class's `version` attribute,
  falling back to the installed package metadata.
- `workflow_version` identifies the orchestration code that wrote the
  entry. It is absent for outputs written outside a workflow run.
- Unavailable versions are recorded as `null` and logged, never raised.

### Environment

`environment` holds the four values from
`causaliq_core.utils.environment()`: `os`, `cpu`, `python` and `ram`. It
is collected once per workflow run, cached by core for 24 hours, and
wrapped so that a platform failure cannot fail a step. Recording it per
entry keeps each exported `_meta.json` self-contained for long-term
archival; repeated values are tokenised in the cache.

## Parameters and Result

The split is introduced in two phases:

1. **Structure phase (this change).** Every action's existing metadata is
   placed in `result`, and `parameters` starts empty. This establishes the
   contract without judging each field.
2. **Values-audit phase (separate).** Parameter-like keys (`algorithm`,
   `hyperparameters`, `sample_size`, paths, seeds, timeouts, LLM models)
   move from `result` to `parameters`, and completeness is checked.

The split distinguishes two timing concepts:

- `result.elapsed_seconds` and `result.algorithm_seconds` are measured by
  the action;
- `provenance.elapsed` is measured by the framework for the whole step.

## History

`history` is reserved and written as `{}` in this change. When populated,
an entry mirrors the producer's blocks, so a carried field can be
identified as an inherited input or an inherited result:

```json
"history": {
  "causaliq-discovery.learn_graph": {
    "parameters": {"algorithm": "hc"},
    "result": {"status": "ok", "algorithm_seconds": 3200.1}
  }
}
```

The future `history` step parameter accepts `standard`, a list of field
paths, or `all`. It is defined for one-to-one aggregate steps first;
many-to-one actions require action-specific reductions rather than
generic copying.

## Naming and References

Bare names refer only to the row's design and result:

- matrix values: `sample_size`, `network`, `series`;
- result-object fields: `f1`, `shd`, `equiv.f1`.

Metadata is always producer-qualified. There is no user-facing concept of
"the entry writer's own metadata": from a report's perspective every
metadata value belongs to some previous action.

| Form | Example | Availability |
|------|---------|--------------|
| Short | `learn_graph.status` | When the name is unique across `parameters` and `result` |
| Explicit | `learn_graph.result.status`, `learn_graph.parameters.algorithm` | Always |
| Provider-qualified | `causaliq_discovery.learn_graph.status` | When action names collide |

Provider names are normalised to underscores in the provider-qualified
form because hyphens cannot be parsed as attribute chains. Bare metadata
names are rejected with a suggestion such as "did you mean
`learn_graph.status`?".

Filter expressions are rewritten before evaluation so that qualified
names resolve against the flat reporting view; the evaluator cannot
address dotted keys directly. Undefined names raise a clear error rather
than silently excluding entries.

`provenance` is recorded for reproducibility but is not exposed in
filters or plot columns by default. If it is needed later, it can be
exposed as `learn_graph.provider_version` and
`learn_graph.environment.python` without changing the stored shape.

## Compatibility

- **Write:** only version 2 from now on; export writes
  `"schema_version": 2`.
- **Read:** version 1 metadata is normalised on read. The last legacy
  provider/action block becomes the producer; earlier blocks move to
  `history` with their fields under `result`.
- **No migration tooling:** caches remain disposable until the Zenodo
  deposit, consistent with the cache type model. Obsolete provenance keys
  are dropped when metadata is normalised rather than migrated.

## Implementation

The shared envelope lives in `causaliq_core.metadata`:

- `build_metadata(...)` constructs the envelope;
- `split_metadata(...)` returns the four blocks;
- `normalise_metadata(...)` converts version 1 to version 2;
- `RESERVED_KEYS`, `PROVENANCE_KEYS`, `SCHEMA_VERSION` and
  `ActionMetadata` define the contract.

`causaliq-workflow` applies the envelope in the executor, cache write
helpers, export and import. `causaliq-discovery` uses the same builder
for its directory `_meta.json`. `causaliq-analysis` and
`causaliq-knowledge` keep returning flat metadata during the structure
phase; the framework places it in `result`, and the values audit moves
each action to the explicit `parameters`/`result` contract and reads
through the shared reporting view.

## Phased Plan

1. **Structure (this change):** schema version 2, framework provenance,
   action contract, all write paths, readers, compatibility and tests.
2. **Values audit (separate):** classify fields into `parameters` and
   `result`, check each action's completeness, and document its contract.
3. **History population (separate):** the `history` step parameter for
   one-to-one aggregate steps.
4. **Reporting (separate):** `plot` filtering and categorical
   summarisation.
5. **Hat 2 clean-up (separate):** consolidate the duplicate metadata
   flatteners and remove dead write paths.

## See Also

- [Cache Type Model](cache_type_model.md) - one object type per cache and
  the failure-entry rule
- [Workflow Cache Design](workflow_cache_design.md) - cache architecture
  and aggregation scanning
- [Caching](../userguide/caching.md) - user-facing cache and filter guide
- [Common Parameters](../userguide/common_parameters.md) - shared action
  parameters

