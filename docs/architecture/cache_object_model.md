# Cache Object Model

## Overview

This document defines the model for objects stored within workflow cache
entries. Objects are the primary data artefacts produced by actions, such
as graphs, traces, and statistical summaries.

## Design Goals

| Goal | Description |
|------|-------------|
| **Type-based lookup** | Actions find objects by semantic type, not arbitrary names |
| **Multiple objects** | Entries can hold multiple objects (e.g., graph + trace) |
| **Clear provenance** | Action metadata references the object(s) it created |
| **Format flexibility** | Same object type can be serialised in different formats |
| **Simple constraints** | One object per type per entry avoids ambiguity |

## Object Model

### CacheObject Structure

Each object in a cache entry has three components:

| Field | Description | Example |
|-------|-------------|---------|
| `type` | Semantic object type | `"pdg"`, `"dag"`, `"cpdag"`, `"trace"` |
| `format` | Serialisation format | `"graphml"`, `"json"`, `"csv"` |
| `content` | Serialised data | GraphML string, JSON string, etc. |

**Example object:**

```python
CacheObject(
    type="pdg",
    format="graphml",
    content="<?xml version='1.0'?>..."
)
```

### Supported Object Types

| Type | Description | Typical Format |
|------|-------------|----------------|
| `dag` | Directed Acyclic Graph | graphml |
| `pdag` | Partially Directed Acyclic Graph (CPDAG) | graphml |
| `pdg` | Probabilistic Dependency Graph | graphml |
| `trace` | Algorithm execution trace | json, csv |
| `summary` | Statistical summary | json |
| `confidences` | Edge confidence scores | json |

New types can be added without schema changes.

### One Object Per Type Constraint

**Rule:** Each cache entry may contain at most one object of each type.

This constraint:

- Enables unambiguous lookup by type
- Simplifies action interfaces (request type, get exactly one result)
- Avoids naming conflicts and arbitrary identifier proliferation

**Valid entry:**
```json
{
  "objects": {
    "pdg": {"type": "pdg", "format": "graphml", "content": "..."},
    "trace": {"type": "trace", "format": "json", "content": "..."}
  }
}
```

**Invalid entry (two objects of same type):**
```json
{
  "objects": {
    "reference_dag": {"type": "dag", ...},
    "learnt_dag": {"type": "dag", ...}
  }
}
```

If an action needs to produce multiple objects of the same conceptual type,
use qualified types (e.g., `reference_dag`, `learnt_dag`) or separate entries.

## Storage Structure

### Entry Layout

Objects are stored in a dictionary keyed by type:

```json
{
  "matrix_values": {"network": "asia", "sample_size": "1k"},
  "metadata": {
    "created_at": "2026-03-15T09:00:00Z",
    "causaliq-analysis": {
      "merge_graphs": {
        "action": "merge_graphs",
        "timestamp": "2026-03-15T09:00:00Z",
        "num_graphs": 25,
        "output": {"type": "pdg", "format": "graphml"}
      }
    }
  },
  "objects": {
    "pdg": {
      "type": "pdg",
      "format": "graphml",
      "content": "<?xml version='1.0'?>..."
    }
  }
}
```

### Action Metadata Output Reference

Each action that creates or modifies objects records its output in metadata:

```json
"merge_graphs": {
  "action": "merge_graphs",
  "timestamp": "...",
  "output": {"type": "pdg", "format": "graphml"}
}
```

For CHANGE actions that modify entries:

```json
"best_graph": {
  "action": "best_graph",
  "timestamp": "...",
  "input": {"type": "pdg"},
  "output": {"type": "dag", "format": "graphml"}
}
```

This provides clear provenance: which action created which object.

## Action Patterns

### CREATE Actions

CREATE actions produce new cache entries with objects:

```python
# merge_graphs creates PDG from input DAGs
def run_merge_graphs(...) -> Tuple[str, Dict, List[Dict]]:
    pdg = merge(input_dags)
    return (
        "success",
        {"num_graphs": len(input_dags)},
        [{"type": "pdg", "format": "graphml", "content": pdg_xml}]
    )
```

### CHANGE Actions

CHANGE actions transform objects within existing entries:

```python
# best_graph reads PDG, creates DAG
def run_best_graph(entry: CacheEntry, ...) -> CacheEntry:
    pdg = entry.get_object_by_type("pdg")
    dag = extract_best_dag(pdg)
    entry.add_object("dag", "graphml", dag_xml)
    return entry
```

### Object Lookup

Actions request objects by type:

```python
# Get PDG from entry
pdg_obj = entry.get_object_by_type("pdg")
if pdg_obj is None:
    raise ActionExecutionError("Entry missing required 'pdg' object")

pdg = graphml.read_pdg(StringIO(pdg_obj.content))
```

## Migration from Current Model

### Current Model

```python
# Objects keyed by arbitrary name
entry.objects = {
    "merged_pdg": CacheObject(type="graphml", content="...")
}
```

### New Model

```python
# Objects keyed by semantic type
entry.objects = {
    "pdg": CacheObject(type="pdg", format="graphml", content="...")
}
```

### Migration Steps

1. **Phase 1**: Update `CacheObject` model
   - Rename `type` → `format`
   - Add `type` field for semantic type
   - Update serialisation/deserialisation

2. **Phase 2**: Update action metadata
   - Add `output` reference to action metadata
   - Update metadata writing in all actions

3. **Phase 3**: Update object access
   - Change from name-based to type-based lookup
   - Update all actions that read objects

4. **Phase 4**: Update tests and regenerate caches

### Backward Compatibility

During migration, support reading old-format caches:

```python
def get_object_by_type(self, obj_type: str) -> CacheObject | None:
    # New format: keyed by type
    if obj_type in self.objects:
        return self.objects[obj_type]
    
    # Legacy format: scan for matching name pattern
    for name, obj in self.objects.items():
        if obj_type in name:  # e.g., "merged_pdg" contains "pdg"
            return obj
    
    return None
```

## Implementation Checklist

- [ ] Update `CacheObject` dataclass in `cache/entry.py`
- [ ] Add `get_object_by_type()` method to `CacheEntry`
- [ ] Update `to_storage()` and `from_storage()` methods
- [ ] Update action return format in all providers
- [ ] Add output reference to action metadata
- [ ] Update `best_graph` to CHANGE pattern
- [ ] Update tests
- [ ] Regenerate test caches

## See Also

- [Workflow Cache Design](workflow_cache_design.md) - Overall cache architecture
- [Action Architecture](action_architecture_design.md) - Action patterns
