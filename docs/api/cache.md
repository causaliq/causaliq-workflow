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
        - get
        - exists
        - entry_count
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

## Usage Examples

### Basic Cache Operations

```python
from causaliq_workflow.cache import WorkflowCache, CacheEntry

# Create and use cache with context manager
with WorkflowCache("results/experiment.db") as cache:
    # Create an entry with metadata
    entry = CacheEntry()
    entry.metadata["algorithm"] = "pc"
    entry.metadata["alpha"] = 0.05
    entry.metadata["node_count"] = 8

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
    print(f"Algorithm: {result.metadata['algorithm']}")
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
matrix variable names:

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
from causaliq_workflow.cache import WorkflowCache, CacheEntry

# In-memory cache for testing
with WorkflowCache(":memory:") as cache:
    entry = CacheEntry()
    entry.metadata["test"] = True

    cache.put({"key": "value"}, entry)
    assert cache.entry_count() == 1
# Cache automatically closed and discarded
```

## Architecture Notes

The WorkflowCache wraps causaliq-core's TokenCache with workflow-specific
functionality:

- **Matrix key hashing** - SHA-256 hash of sorted matrix values (16 hex chars)
- **Schema validation** - Ensures consistent matrix variable names across
  entries
- **Entry model** - CacheEntry with metadata dict and named objects list
- **Export/Import** - Convert entries to/from open standard formats (GraphML,
  JSON)

The cache design focuses on:

- **Speed** - Fast existence checks and lookups via hash keys
- **Compactness** - JSON tokenisation reduces storage size
- **Reproducibility** - Entries can be exported to human-readable formats

---

**[← Previous: Workflow Engine](workflow.md)** | **[Back to API Overview](overview.md)** | **[Next: Schema Validation →](schema.md)**
