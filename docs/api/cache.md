# Workflow Cache API

The workflow cache provides SQLite-based storage for workflow step results,
enabling conservative execution and reproducibility. It is built on
causaliq-core's `TokenCache` infrastructure.

## causaliq-core Foundation

The workflow cache imports the following from causaliq-core:

- **TokenCache** - SQLite-based caching with tokenised JSON storage
- **JsonCompressor** - Compressor for JSON tokenisation
- **Compressor** - Abstract compressor interface

## Core Classes

### causaliq_workflow.cache.WorkflowCache

::: causaliq_workflow.cache.WorkflowCache
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
      members:
        - open
        - close
        - put
        - put_typed
        - put_failure
        - get
        - exists
        - entry_count
        - list_entries
        - list_entry_summaries
        - list_entry_records
        - decompress_metadata
        - export
        - import_entries

### causaliq_workflow.cache.CacheEntry

::: causaliq_workflow.cache.CacheEntry
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### causaliq_workflow.cache.CacheObject

::: causaliq_workflow.cache.CacheObject
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Exception Handling

### causaliq_workflow.cache.MatrixSchemaError

::: causaliq_workflow.cache.MatrixSchemaError
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Metadata Envelope

Every entry carries a schema version 2 metadata envelope with four blocks:

- `provenance` — provider, provider and workflow versions, action, local
  start time, elapsed seconds and runtime environment;
- `parameters` — the effective parameters used by the action;
- `result` — status, error, action-measured timings and counts;
- `history` — reserved for metadata inherited from earlier producers.

Build it with `causaliq_core.metadata.build_metadata` rather than
constructing the blocks by hand; the workflow executor does this for every
step. See [Metadata Structure](../architecture/metadata_structure.md) for
the full schema and naming rules.

## Usage Examples

### Basic Cache Operations

```python
from causaliq_core.metadata import build_metadata

from causaliq_workflow.cache import CacheEntry, WorkflowCache

# Create and use cache with context manager
with WorkflowCache("results/experiment.db") as cache:
    # Create an entry with version 2 metadata
    entry = CacheEntry(
        metadata=build_metadata(
            "causaliq-discovery",
            "learn_graph",
            {},
            {"algorithm": "pc", "alpha": 0.05, "node_count": 8},
        )
    )

    # Add a graph object
    graphml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <graphml xmlns="http://graphml.graphdrawing.org/xmlns">
      <graph id="G" edgedefault="directed">
        <node id="A"/><node id="B"/>
        <edge source="A" target="B"/>
      </graph>
    </graphml>'''
    entry.add_object("graph", "graphml", graphml_content)

    # Store with matrix key
    key = {"network": "asia", "algorithm": "pc", "sample_size": "1000"}
    cache.put(key, entry)

    # Check existence
    if cache.exists(key):
        print("Entry found in cache")

    # Retrieve entry
    result = cache.get(key)
    print(f"Algorithm: {result.metadata['result']['algorithm']}")
```

### Matrix Key Hashing

The cache uses SHA-256 hashing of matrix variable values as keys:

```python
from causaliq_workflow.cache import WorkflowCache

with WorkflowCache(":memory:") as cache:
    # These keys produce different hashes
    key1 = {"algorithm": "pc", "network": "asia"}
    key2 = {"algorithm": "ges", "network": "asia"}

    # Key order doesn't matter - sorted before hashing
    key3 = {"network": "asia", "algorithm": "pc"}  # Same hash as key1
```

### Matrix Schema Validation

Once a cache contains entries, all subsequent entries must use the same
matrix variable names. The names are pinned in the cache config on the first
write, so later writes compare against that record instead of scanning the
cache:

```python
from causaliq_workflow.cache import WorkflowCache, CacheEntry, MatrixSchemaError

with WorkflowCache(":memory:") as cache:
    entry = CacheEntry()

    # First entry establishes schema
    cache.put({"algorithm": "pc", "network": "asia"}, entry)

    # This raises MatrixSchemaError - wrong keys
    try:
        cache.put({"method": "pc", "dataset": "asia"}, entry)
    except MatrixSchemaError as e:
        print(f"Schema error: {e}")
```

### Recording a Failure

A failed run is recorded as provenance only: the entry holds the metadata
envelope and no object, so it can never be mistaken for a result. The entry
replaces any prior entry for the key, so the latest run wins.

```python
from causaliq_core.metadata import build_metadata

from causaliq_workflow.cache import WorkflowCache

failure = build_metadata(
    "causaliq-discovery",
    "learn_graph",
    {},
    {"status": "input_error", "error": "variable asia has too few levels"},
)

with WorkflowCache("results/graphs.db") as cache:
    cache.put_failure({"network": "asia"}, failure)
```

A failure entry declares no object type, so `put_failure` pins the cache
type only when it is already known: a failure recorded before the cache's
first successful write leaves the cache unpinned, and the first typed write
pins it. Pass `cache_type` to pin an explicit type. See
[Cache Type Model](../architecture/cache_type_model.md) for the rule.

### Scanning Entries Without Objects

`list_entry_records()` returns each entry's matrix values with its metadata
still compressed, so a scan can match on matrix values first and decompress
metadata only for the entries it keeps:

```python
with WorkflowCache("cache.db") as cache:
    for record in cache.list_entry_records():
        if record["matrix_values"]["network"] != "asia":
            continue
        metadata = cache.decompress_metadata(record["metadata_blob"])
        print(metadata)
```

### Export and Import

```python
from causaliq_workflow.cache import WorkflowCache
from pathlib import Path

# Export cache to directory
with WorkflowCache("experiment.db") as cache:
    exported = cache.export(Path("./exported"))
    print(f"Exported {exported} entries")

# Export to zip file
with WorkflowCache("experiment.db") as cache:
    exported = cache.export(Path("./results.zip"))

# Import from directory
with WorkflowCache("new_cache.db") as cache:
    imported = cache.import_entries(Path("./exported"))
    print(f"Imported {imported} entries")
```

### In-Memory Cache

Use `:memory:` for fast, non-persistent caching:

```python
from causaliq_core.metadata import build_metadata

from causaliq_workflow.cache import CacheEntry, WorkflowCache

# In-memory cache for testing
with WorkflowCache(":memory:") as cache:
    entry = CacheEntry(
        metadata=build_metadata(
            "test-provider",
            "test_action",
            {},
            {"test": True},
        )
    )

    cache.put({"key": "value"}, entry)
    assert cache.entry_count() == 1
# Cache automatically closed and discarded
```

## Describing a Cache

`describe_cache()` scans an open cache and returns its object type, entry
and object counts, per-variable value coverage and an example entry.
`format_description()` turns that mapping into the terminal report printed
by `cqflow describe-cache`.

::: causaliq_workflow.cache.describe.describe_cache
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: causaliq_workflow.cache.describe.format_description
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

```python
from pathlib import Path

from causaliq_workflow.cache import describe_cache, WorkflowCache
from causaliq_workflow.cache.describe import format_description

with WorkflowCache("results/graphs.db") as cache:
    description = describe_cache(cache)
print(description["cache_type"], description["entry_count"])

lines = format_description(
    description, Path("results/graphs.db").resolve(), 1_048_576
)
print("\n".join(lines))
```

## Architecture Notes

The WorkflowCache wraps causaliq-core's TokenCache with workflow-specific
functionality:

- **Matrix key hashing** - SHA-256 hash of sorted matrix values (16 hex chars)
- **Schema validation** - Ensures consistent matrix variable names across
  entries
- **Metadata envelope** - Schema version 2 provenance, inputs, result and
  history blocks
- **Entry model** - `CacheEntry` with the metadata envelope and at most one
  typed object
- **Export/Import** - Convert entries to/from open standard formats (GraphML,
  JSON) and normalise version 1 metadata on import

The cache design focuses on:

- **Speed** - Fast existence checks and lookups via hash keys
- **Compactness** - JSON tokenisation reduces storage size
- **Reproducibility** - Entries can be exported to human-readable formats

---

**[← Previous: Workflow Engine](workflow.md)** | **[Back to API Overview](overview.md)** | **[Next: Schema Validation →](schema.md)**
