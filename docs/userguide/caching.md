# Workflow Caching

CausalIQ Workflow uses SQLite-based caches to store step results, enabling
conservative execution and reproducibility.

## What is a Workflow Cache?

A **workflow cache** is a `.db` file containing:

- **Entries**: Individual results from workflow steps
- **Metadata**: Key-value pairs describing each entry (algorithm, parameters,
  metrics)
- **Objects**: Named data objects (graphs, tables, traces) stored with each
  entry

Caches are the primary mechanism for passing results between workflow steps
and enabling conservative execution.

## Cache Entries

Each entry in a cache has:

| Component | Description |
|-----------|-------------|
| **Key** | Matrix values that uniquely identify the entry |
| **Metadata** | Dictionary of properties (algorithm, scores, timestamps) |
| **Objects** | Named data items (e.g., `graph`, `trace`, `summary`) |

### Entry Keys

Entries are keyed by their matrix values. For a workflow with:

```yaml
matrix:
  network: [asia, cancer]
  sample_size: [100, 1000]
```

Each entry is identified by a unique `{network, sample_size}` combination.

### Entry Metadata

Metadata uses schema version 2 and four blocks: `provenance`, `inputs`,
`result` and `history`. The framework writes provenance, the action writes
`result` (and `inputs` when it supplies them), and `history` is reserved for
metadata inherited from earlier actions.

```json
{
  "provenance": {
    "provider": "causaliq-discovery",
    "provider_version": "0.8.0.dev4",
    "workflow_version": "0.6.0.dev8",
    "action": "learn_graph",
    "started_at": "2026-03-15T10:20:00+00:00",
    "finished_at": "2026-03-15T10:23:45+00:00",
    "duration_seconds": 225.0,
    "environment": {
      "os": "Linux v6.8.0",
      "cpu": "AMD EPYC 7763",
      "python": "3.12.4",
      "ram": 64
    }
  },
  "inputs": {},
  "result": {
    "status": "ok",
    "algorithm": "pc",
    "node_count": 8,
    "edge_count": 8
  },
  "history": {}
}
```

During the structure phase, action fields live in `result`; the separate
values audit moves input-like fields into `inputs`. See
[Metadata Structure](../architecture/metadata_structure.md) for the full
schema.

### Metadata Names in Filters and Plots

- Bare names refer to matrix values and result-object fields: `sample_size`,
  `f1`, `equiv.f1`.
- Metadata is producer-qualified: `learn_graph.status`,
  `learn_graph.hyperparameters.iss`.
- Explicit forms (`learn_graph.inputs.algorithm`,
  `learn_graph.result.status`) and provider-qualified forms
  (`causaliq_discovery.learn_graph.status`) are available when needed.
- A bare metadata name such as `status` is rejected; the reference must name
  the producer.

```yaml
with:
  action: plot
  input: results/metrics.db
  filter: "learn_graph.algorithm_seconds < 3600"
  x: sample_size
  y: f1
```

### Entry Objects

Each cache holds one object type, and every successful entry holds exactly
one object of that type:

| Name | Format | Description |
|------|--------|-------------|
| `dag` | GraphML | Learned DAG |
| `pdg` | GraphML | Merged or LLM-sourced PDG |
| `metrics` | JSON | Evaluation scores |
| `trace` | JSON | Algorithm iteration history |

Objects are stored as content strings with a format identifier. See
[Cache Type Model](../architecture/cache_type_model.md) for the full design.

## Conservative Execution

By default, workflows execute **conservatively** — skipping work that has
already been completed:

- **Create steps**: Skip if entry with matching key exists
- **Aggregate steps**: Skip if output entry with matching key exists
- **Run-once steps**: Execute on the first job only

This enables:

- **Resumable workflows**: Restart interrupted workflows without re-running
  completed steps
- **Incremental analysis**: Write new results to their own typed caches
- **Efficient iteration**: Modify workflow and re-run without starting from
  scratch

### Bypassing Conservative Execution

Use `--mode=force` to re-run all steps regardless of existing results:

```bash
cqflow run workflow.yml --mode=force
```

## Cache Files

Cache files are self-contained SQLite databases:

```
results/
├── graphs.db       # Learned graphs from discovery
├── evaluated.db    # Graphs with evaluation metrics
└── merged.db       # Aggregated results
```

### Cache Location

Specify cache paths relative to the workflow's `root_dir`:

```yaml
root_dir: "/experiments/project-001"

steps:
  - name: "Learn"
    uses: "causaliq-discovery"
    with:
      action: "learn_structure"
      output: "results/graphs.db"  # → /experiments/project-001/results/graphs.db
```

## Exporting and Importing

Caches can be exported to open formats for sharing and archival:

```bash
# Export to directory
cqflow export-cache -i results/graphs.db -o ./exported

# Export to zip
cqflow export-cache -i results/graphs.db -o results.zip

# Import from export
cqflow import-cache -i ./exported -o results/restored.db
```

Exported format uses:

- **JSON** for metadata
- **GraphML** for graph objects
- **JSON** for other objects

Each `_meta.json` records `schema_version: 2`, `matrix_values`, `created_at`
and the metadata envelope. Version 1 exports remain readable: import
normalises them to the current schema.

This enables interoperability with external tools and long-term archival in
open formats.

## Cache Schema Consistency

When using a cache across multiple workflow runs, the matrix dimensions must
remain consistent. Adding or removing matrix variables from a workflow that
writes to an existing cache will raise a `MatrixSchemaError`.

To change matrix dimensions, either:

- Use a new cache file
- Export, delete, and re-import the cache
- Delete the cache and regenerate

## Python API

For programmatic cache access, see the
[Workflow Cache API](../api/cache.md).

```python
from causaliq_workflow.cache import WorkflowCache

with WorkflowCache("results/graphs.db") as cache:
    # Check if entry exists
    key = {"network": "asia", "sample_size": 1000}
    if cache.exists(key):
        entry = cache.get(key)
        print(entry.metadata["result"]["status"])
```
