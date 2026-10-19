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

Metadata is a flat dictionary stored with each entry. Actions add their
results here:

```python
{
    "network": "asia",
    "sample_size": 1000,
    "algorithm": "pc",
    "node_count": 8,
    "edge_count": 8,
    "f1_score": 0.857,
    "evaluate_graph": {"completed": "2026-03-15T10:23:45"}
}
```

The presence of action-specific metadata (e.g., `evaluate_graph`) indicates
that action has been applied to the entry.

### Entry Objects

Each cache holds one object type, and every entry holds exactly one object
of that type:

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
        print(entry.metadata["f1_score"])
```
