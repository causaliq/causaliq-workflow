# Workflow Cache Design

!!! note "Partially superseded"

    The cache type model and metadata structure have changed since this
    document was written. One cache holds one object type, every entry
    holds at most one typed object, and metadata uses schema version 2.
    See [Cache Type Model](cache_type_model.md) and
    [Metadata Structure](metadata_structure.md) for the current design;
    the mutable-metadata and multi-object sections below are historical.

## Overview

Workflow Caches provide persistent storage for workflow step results in a
compact, fast SQLite database. This enables *conservative execution* (skipping
work if results exist) and supports reproducibility of research over many
years.

The cache is built on common infrastructure (`TokenCache`, `JsonEncoder`)
shared with LLM response caching. This common infrastructure currently resides
in causaliq-knowledge but will migrate to causaliq-core.

## Design Goals

| Goal | Description |
|------|-------------|
| **Compact storage** | SQLite with tokenised blobs, not unwieldy file trees |
| **Fast lookup** | Quick existence checks for conservative execution |
| **Flexibility** | Multiple entry types without schema changes |
| **Open export** | Convert to GraphML, JSON, CSV for archival |
| **Reproducibility** | Results persist and can be replicated years later |

## Architecture Decisions

### Cache Entry Structure

Each cache entry consists of a **metadata envelope** and at most **one typed
data blob**:

| Component | Storage | Purpose |
|-----------|---------|---------|
| **Metadata envelope** | Tokenised JSON | Provenance, inputs, result and the reserved history block |
| **Data blob** | Type-specific encoded object | Exactly one result object for a successful run; none for a failure |

The envelope is schema version 2 (see
[Metadata Structure](metadata_structure.md)). A structure learning result
writes a `dag` object to the graph cache and, when requested, a `trace`
object to a separate trace cache. A failed run records `result.status` and
`result.error` and writes no object.

This design:

- keeps one object type per cache and one object per entry
- keeps metric values in the typed object rather than duplicating them in
  metadata
- records provider versions, the action start time, elapsed seconds and
  environment for
  reproducibility
- supports adding object types and action fields without schema changes

### Cache Key Strategy

#### Schema Binding

A Workflow Cache is bound to its **matrix variable structure** (the set of
variable names), not to specific values. This means:

| Change | Permitted | Reason |
|--------|-----------|--------|
| Add new value to existing variable | ✓ Yes | New entries created, existing entries unchanged |
| Remove value from variable | ✓ Yes | Existing entries remain accessible |
| Add new matrix variable | ✗ No | Changes key structure, requires new cache |
| Remove matrix variable | ✗ No | Changes key structure, requires new cache |
| Rename matrix variable | ✗ No | Changes key structure, requires new cache |

**Example - permitted change:**
```yaml
# Original
matrix:
  algorithm: [pc, ges]

# Extended (same cache works)
matrix:
  algorithm: [pc, ges, fci, tabu]  # Added values
```

**Example - requires new cache:**
```yaml
# Original
matrix:
  algorithm: [pc, ges]

# Extended with new dimension (new cache needed)
matrix:
  algorithm: [pc, ges]
  network: [asia, cancer]  # New variable
```

This constraint keeps the implementation simple. Future versions may support
schema migration if needed.

#### Key Derivation

The cache key is a SHA-256 hash (truncated to 16 hex characters) of the
**workflow matrix variable values** for that step execution:

```python
# Example: workflow with matrix expansion
matrix_values = {
    "network": "cancer",
    "llm_model": "groq/llama-3.1-8b",
    "prompt_detail": "standard"
}
key = sha256(json.dumps(matrix_values, sort_keys=True))[:16]
```

**Rationale**: Matrix values capture the experimental design - they define
what distinguishes one result from another. This aligns cache keys with
research intent rather than implementation details.

**Deferred**: Complex key strategies (action params, step names) can be
added if the simple approach proves insufficient.

### Edge Confidences

Edge confidences from LLM graph generation are stored in the **PDG object's
edge probability attributes**, not in metadata:

- the PDG object carries the uncertainty over edge states;
- metadata records how the object was produced (`provenance`, `parameters`
  and `result`).

**Rationale**: edge confidences are intrinsic to that graph result, so they
belong to the typed object. Keeping metadata as provenance preserves one
consistent shape across graph, trace and metrics objects.

### SDG Changes (Minimal)

The SDG class requires only:

- `compress()` / `decompress()` methods for compact blob representation
- `to_graphml()` / `from_graphml()` for open format export

Edge attributes are **not** added to SDG in this release.

### Graph Encoding Format

The `SDG.compress()` method produces a compact binary representation that
leverages the Workflow Cache's shared token dictionary for variable names:

**Header** (4 bytes):

| Bytes | Content |
|-------|---------||
| 0-1 | Node count (uint16, max 65,535 nodes) |
| 2-3 | Edge count (uint16, max 65,535 edges) |

**Node table** (2 bytes per node):

Each node is a token ID (uint16) referencing the token dictionary.
Variable names like "BMI", "Age", "Smoking" are stored once in the
token dictionary and referenced by ID.

**Edge list** (5 bytes per edge):

Each edge is packed into 36 bits (padded to 5 bytes):

| Bits | Content |
|------|---------||
| 0-15 | Source node token ID (uint16) |
| 16-31 | Target node token ID (uint16) |
| 32-33 | Source endpoint type (2 bits: `-`, `>`, `o`) |
| 34-35 | Target endpoint type (2 bits: `-`, `>`, `o`) |

**Example**: A graph with 20 nodes and 25 edges:

- Header: 4 bytes
- Nodes: 20 × 2 = 40 bytes
- Edges: 25 × 5 = 125 bytes
- **Total: 169 bytes** (vs ~2KB for JSON representation)

The token dictionary is shared across all cache entries, so common
variable names are stored only once regardless of how many graphs
reference them.

## SQLite Schema

```sql
-- Shared token dictionary for compression (includes variable names)
CREATE TABLE tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    frequency INTEGER DEFAULT 1
);

-- Cache entries with metadata
CREATE TABLE cache_entries (
    hash TEXT NOT NULL,
    seq INTEGER NOT NULL DEFAULT 0,  -- Collision sequence (0 = first entry)
    key_json TEXT NOT NULL,          -- Original key for collision detection
    metadata BLOB,
    created_at TEXT NOT NULL,
    hit_count INTEGER DEFAULT 0,
    last_accessed_at TEXT,
    PRIMARY KEY (hash, seq)
);

-- Data blobs associated with cache entries
CREATE TABLE cache_data (
    hash TEXT NOT NULL,
    seq INTEGER NOT NULL DEFAULT 0,
    data_type TEXT NOT NULL,        -- 'graph', 'trace', etc.
    data BLOB NOT NULL,
    PRIMARY KEY (hash, seq, data_type),
    FOREIGN KEY (hash, seq) REFERENCES cache_entries(hash, seq) ON DELETE CASCADE
);

CREATE INDEX idx_created_at ON cache_entries(created_at);
CREATE INDEX idx_data_type ON cache_data(data_type);
```

### Hash Collision Handling

With truncated SHA-256 hashes (16 hex chars = 64 bits), collisions are rare
but possible. The `seq` column handles multiple entries with the same hash:

```python
def put(self, key_data: dict, data: dict[str, bytes], metadata: dict) -> None:
    hash = self._compute_hash(key_data)
    key_json = json.dumps(key_data, sort_keys=True)
    
    # Find existing entry with same key, or next available seq
    rows = self.conn.execute(
        "SELECT seq, key_json FROM cache_entries WHERE hash = ? ORDER BY seq",
        (hash,)
    ).fetchall()
    
    seq = 0
    for row_seq, row_key_json in rows:
        if row_key_json == key_json:
            # Exact match - update existing entry
            seq = row_seq
            self._delete_entry(hash, seq)  # Remove old data blobs
            break
        seq = row_seq + 1  # Collision - use next sequence number
    
    # Insert entry and data blobs
    self.conn.execute(
        "INSERT INTO cache_entries (hash, seq, key_json, metadata, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (hash, seq, key_json, self._encode_metadata(metadata), datetime.utcnow())
    )
    for data_type, blob in data.items():
        self.conn.execute(
            "INSERT INTO cache_data (hash, seq, data_type, data) VALUES (?, ?, ?, ?)",
            (hash, seq, data_type, blob)
        )
    self.conn.commit()


def get(self, key_data: dict, data_type: str) -> bytes | None:
    hash = self._compute_hash(key_data)
    key_json = json.dumps(key_data, sort_keys=True)
    
    # Find entry matching both hash and key
    rows = self.conn.execute(
        "SELECT seq, key_json FROM cache_entries WHERE hash = ?", (hash,)
    ).fetchall()
    
    for seq, row_key_json in rows:
        if row_key_json == key_json:
            # Found matching entry - fetch data blob
            data_row = self.conn.execute(
                "SELECT data FROM cache_data "
                "WHERE hash = ? AND seq = ? AND data_type = ?",
                (hash, seq, data_type)
            ).fetchone()
            return data_row[0] if data_row else None
    
    return None  # No matching entry found
```

In practice, collisions are extremely rare with 64-bit hashes (birthday problem
suggests ~4 billion entries before 50% collision probability), but the schema
handles them correctly when they occur.

## Entry Types

| Type | Data Blob | Metadata | Encoder |
|------|-----------|----------|---------|
| `graph` | Encoded SDG | Provenance, edge confidences, scores | `GraphEntryEncoder` |
| `trace` | Encoded DataFrame | Algorithm, iterations, timing | `TraceEntryEncoder` |
| `llm` | Tokenised JSON | Provider, tokens, cost | `LLMEntryEncoder` |

New types can be added by implementing `EntryEncoder` - no schema changes.

## Metadata Mutability and Cache Queries

### Mutable Metadata

While **matrix keys are immutable** (they define entry identity), **metadata
can be updated** after entry creation. This enables analysis workflows that
enrich cached results:

```python
# Update metadata for an existing entry
cache.update_metadata(
    key={"algorithm": "pc", "network": "asia"},
    metadata_updates={"bic_score": -1523.4, "evaluated_at": "2026-02-04"}
)
```

**Use cases:**
- Scoring workflows that evaluate cached graphs
- Adding benchmark results to existing entries
- Annotating entries with review status or notes

### Cache as Workflow Input

Workflow steps can use a Workflow Cache as an **input source**, selecting
entries via predicates:

```yaml
name: "Score cached graphs"
steps:
  - action: score_graphs
    cache_input:
      source: "results/discovery_cache.db"
      select:
        # Matrix key predicates (indexed lookup)
        algorithm: [pc, ges]
        # Metadata predicates (may require scan)
        bic_score: null            # Not yet scored
    cache_output: "results/discovery_cache.db"  # Update same cache
```

### Entry Selection Predicates

Predicates can filter on matrix keys or metadata:

| Predicate Type | Index | Example |
|----------------|-------|---------|
| Matrix key equality | ✓ Hash lookup | `algorithm: pc` |
| Matrix key in list | ✓ Multiple lookups | `algorithm: [pc, ges]` |
| Metadata equality | ✗ Full scan | `evaluated: true` |
| Metadata comparison | ✗ Full scan | `bic_score: {gt: -1000}` |
| Metadata null check | ✗ Full scan | `bic_score: null` |

```python
def select_entries(
    self,
    matrix_predicates: dict[str, Any] | None = None,
    metadata_predicates: dict[str, Any] | None = None,
) -> Iterator[CacheEntry]:
    """Select entries matching predicates.
    
    Args:
        matrix_predicates: Filter on matrix key values (indexed).
        metadata_predicates: Filter on metadata fields (scan).
    
    Yields:
        Matching cache entries.
    """
    if matrix_predicates:
        # Build candidate set from matrix key lookups
        candidates = self._lookup_by_matrix(matrix_predicates)
    else:
        # No matrix filter - full cache scan
        candidates = self._scan_all_entries()
    
    # Apply metadata filters
    for entry in candidates:
        if self._matches_metadata(entry, metadata_predicates):
            yield entry
```

### Query Optimisation

When matrix predicates are provided, selection is efficient:

```python
# Indexed: O(k) where k = number of matching matrix combinations
select(matrix_predicates={"algorithm": "pc", "network": "asia"})

# Scan: O(n) where n = total entries
select(metadata_predicates={"bic_score": {"gt": -1000}})

# Hybrid: O(k) lookups + filter
select(
    matrix_predicates={"algorithm": ["pc", "ges"]},
    metadata_predicates={"bic_score": null}
)
```

**Future optimisation**: Add optional indexes on frequently-queried metadata
fields if scan performance becomes a bottleneck.

## Import/Export

### Export to Open Formats

```bash
cqflow cache export workflow.db --output ./exported/
```

The export creates a **hierarchical directory structure mirroring the matrix
parameters**, making results human-navigable:

```
exported/
├── pc/                          # algorithm (1st matrix variable)
│   ├── asia/                    # network (2nd matrix variable)
│   │   ├── graph.graphml
│   │   ├── trace.csv            # (if present)
│   │   └── metadata.json
│   └── cancer/
│       ├── graph.graphml
│       └── metadata.json
├── ges/
│   ├── asia/
│   │   ├── graph.graphml
│   │   └── metadata.json
│   └── cancer/
│       ├── graph.graphml
│       └── metadata.json
└── manifest.json                # Index with full matrix key mappings
```

The directory hierarchy follows the order of matrix variables as defined in
the workflow. The `manifest.json` provides a complete index mapping directory
paths to cache hashes and full matrix key values:

```json
{
  "matrix_variables": ["algorithm", "network"],
  "entries": [
    {
      "path": "pc/asia",
      "hash": "a3f7b2c1e9d4f8a2",
      "key": {"algorithm": "pc", "network": "asia"},
      "data_types": ["graph", "trace"]
    },
    {
      "path": "pc/cancer",
      "hash": "b4e8c3d2f1a5e9b3",
      "key": {"algorithm": "pc", "network": "cancer"},
      "data_types": ["graph"]
    }
  ]
}
```

### Import from Open Formats

```bash
cqflow cache import ./exported/ --into results.db
```

Useful for:

- Populating test fixtures
- Sharing results between researchers
- Restoring from Zenodo archives

## Integration with Workflows

### Writing Results

Actions write results via the workflow context:

```python
def run(self, inputs, mode, context, logger):
    # ... generate graph and trace ...
    
    if context and context.cache:
        context.cache.put(
            key_data=context.matrix_values,  # Original key dict
            data={                           # Multiple data blobs
                "graph": graph,
                "trace": trace,              # Optional
            },
            metadata={
                "provenance": {...},
                "edge_confidences": {...}
            }
        )
```

### Conservative Execution

The workflow executor checks cache before running steps:

```python
if cache.exists(context.matrix_values):
    logger.info("Skipping: result already cached")
    return cache.get(context.matrix_values, "graph")
```

## Aggregation Mode

Aggregation mode enables workflow steps to consume entries from multiple cache
entries, essential for research workflows that merge graphs or compute
aggregate statistics across parameter sweeps.

### Aggregation Detection

A step enters aggregation mode when:

1. The workflow has a **matrix** definition, AND
2. The step has EITHER:
   - An `aggregate` parameter pointing to cache file(s), OR
   - An `input` parameter pointing to `.db` cache file(s)

```yaml
# Implicit aggregation - input points to .db file
matrix:
  model: [asia, cancer]

steps:
  - uses: causaliq-analysis
    with:
      action: merge_graphs
      input: results/graphs.db    # Triggers aggregation mode
      output: results/merged.db
```

```yaml
# Aggregation with multiple input caches
steps:
  - uses: causaliq-analysis
    with:
      action: merge_graphs
      input:                      # Multiple .db input caches
        - results/llm_graphs.db
        - results/discovery.db
      output: results/merged.db
```

### Entry Scanning Flow

The `_scan_aggregation_inputs()` method scans a memoised per-cache index
rather than re-reading the cache for every matrix job:

1. Build or reuse an index of each entry's matrix values and reporting view
   (`WorkflowCache.list_entry_summaries()`, which does not decompress object
   payloads)
2. Apply the filter expression (if present)
3. Match entries against the current matrix values
4. Load only matched entries in full and return them as entry dictionaries

The index is held on the executor and invalidated whenever the cache is
written, so results stay consistent within a run while avoiding repeated
full-cache reads.

```python
# Scan statistics logged during execution
# "Aggregation scan: scanned=100, filtered=20, matched=8"
```

### Filter Expressions

The `filter` parameter accepts expressions evaluated against the shared
reporting view:

```yaml
with:
  action: merge_graphs
  input: results/graphs.db
  filter: "learn_graph.algorithm == 'pc' and sample_size >= 1000"
```

The view exposes:

- matrix values and result-object fields by bare name (`sample_size`, `f1`);
- metadata by producer-qualified name (`learn_graph.status`,
  `learn_graph.hyperparameters.iss`);
- explicit forms (`learn_graph.parameters.algorithm`,
  `learn_graph.result.status`) and provider-qualified forms
  (`causaliq_discovery.learn_graph.status`) when needed.

Bare metadata names are rejected: the producer always has to be named.
Qualified names are rewritten before evaluation because the underlying
evaluator cannot address dotted keys directly.

### Action Integration

Matching entries are passed to actions via `_aggregation_entries`:

```python
def run(self, inputs, mode, context, logger):
    entries = inputs.get("_aggregation_entries", [])
    
    for entry in entries:
        matrix_vals = entry["matrix_values"]
        metadata = entry["metadata"]
        cache_entry = entry["entry"]  # Full CacheEntry with data
        
        # Access entry data
        graph = cache_entry.get_object("graph")
```

## Cross-Package Dependencies

Workflow Caches span three packages:

| Package | Version | Responsibility |
|---------|---------|----------------|
| **causaliq-core** | v0.5.0 | TokenCache, JsonEncoder, SDG, evaluate_filter |
| **causaliq-knowledge** | v0.5.0 | GraphEntryEncoder, update generate_graph action |
| **causaliq-workflow** | v0.3.0 | WorkflowCache, aggregation mode, CLI commands |

**Implementation order**: core → knowledge → workflow (each depends on prior)

## Future Considerations

**Deferred to later releases:**

- Metadata indexing for complex queries
- SDG edge attributes
- Cache key strategies beyond matrix values
- Cache comparison and diff tools

## See Also

- [Cache Type Model](cache_type_model.md) - one object type per cache,
  provenance metadata and exactly one typed object per entry
- [Metadata Structure](metadata_structure.md) - schema version 2 metadata
  envelope, provenance and naming rules
