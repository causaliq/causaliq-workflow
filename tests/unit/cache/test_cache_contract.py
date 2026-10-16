"""Unit tests for the cache type and one-object contract."""

import pytest

from causaliq_workflow.cache import (
    EMPTY_FORMAT,
    CacheEntry,
    CacheTypeError,
    WorkflowCache,
)
from causaliq_workflow.cache.contract import (
    build_failure_entry,
    pin_cache_type,
    single_object_type,
)

# ============================================================================
# Contract helper tests
# ============================================================================


# Test pin_cache_type returns the new type when unpinned.
def test_pin_cache_type_returns_new_type() -> None:
    assert pin_cache_type(None, "dag") == "dag"


# Test pin_cache_type returns the existing type when it matches.
def test_pin_cache_type_accepts_matching_type() -> None:
    assert pin_cache_type("dag", "dag") == "dag"


# Test pin_cache_type raises when the types conflict.
def test_pin_cache_type_raises_on_conflict() -> None:
    with pytest.raises(CacheTypeError, match="holds 'dag'"):
        pin_cache_type("dag", "pdg")


# Test single_object_type returns the entry's single type.
def test_single_object_type_returns_type() -> None:
    entry = CacheEntry()
    entry.add_object("pdg", "graphml", "<g/>")
    assert single_object_type(entry) == "pdg"


# Test single_object_type rejects an entry with no objects.
def test_single_object_type_raises_when_empty() -> None:
    with pytest.raises(CacheTypeError, match="exactly one object, found 0"):
        single_object_type(CacheEntry())


# Test single_object_type rejects an entry with several objects.
def test_single_object_type_raises_when_multiple() -> None:
    entry = CacheEntry()
    entry.add_object("pdg", "graphml", "<g/>")
    entry.add_object("dag", "graphml", "<g/>")
    with pytest.raises(CacheTypeError, match="exactly one object, found 2"):
        single_object_type(entry)


# Test build_failure_entry keys the empty object by the cache type.
def test_build_failure_entry_holds_empty_object() -> None:
    entry = build_failure_entry("dag", "learn_graph", {"status": "error"})
    assert single_object_type(entry) == "dag"
    assert entry.objects["dag"].is_empty is True


# Test build_failure_entry records the supplied provenance.
def test_build_failure_entry_uses_provenance() -> None:
    entry = build_failure_entry("dag", "learn_graph", {"status": "error"})
    assert entry.metadata == {"status": "error"}


# Test build_failure_entry defaults to empty provenance.
def test_build_failure_entry_defaults_provenance() -> None:
    entry = build_failure_entry("dag", "learn_graph")
    assert entry.metadata == {}


# ============================================================================
# CacheObject empty marker tests
# ============================================================================


# Test an empty marker object reports is_empty.
def test_empty_object_reports_is_empty() -> None:
    entry = build_failure_entry("dag", "learn_graph")
    assert entry.objects["dag"].format == EMPTY_FORMAT
    assert entry.objects["dag"].is_empty is True


# Test a populated object does not report is_empty.
def test_populated_object_not_empty() -> None:
    entry = CacheEntry()
    entry.add_object("dag", "graphml", "<g/>")
    assert entry.objects["dag"].is_empty is False


# ============================================================================
# WorkflowCache typed contract tests
# ============================================================================


# Test get_cache_type returns None for an empty cache.
def test_get_cache_type_none_when_unpinned() -> None:
    with WorkflowCache(":memory:") as cache:
        assert cache.get_cache_type() is None


# Test set_cache_type pins and persists the type.
def test_set_cache_type_pins_type() -> None:
    with WorkflowCache(":memory:") as cache:
        assert cache.set_cache_type("pdg") == "pdg"
        assert cache.get_cache_type() == "pdg"


# Test set_cache_type raises when the cache is already pinned.
def test_set_cache_type_raises_on_conflict() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.set_cache_type("pdg")
        with pytest.raises(CacheTypeError):
            cache.set_cache_type("dag")


# Test put_typed pins the cache type from the entry's object.
def test_put_typed_pins_type_from_entry() -> None:
    with WorkflowCache(":memory:") as cache:
        entry = CacheEntry()
        entry.add_object("pdg", "graphml", "<g/>")
        cache.put_typed({"algo": "pc"}, entry)
        assert cache.get_cache_type() == "pdg"


# Test put_typed stores the entry so it can be read back.
def test_put_typed_stores_entry() -> None:
    with WorkflowCache(":memory:") as cache:
        entry = CacheEntry()
        entry.add_object("pdg", "graphml", "<g/>")
        cache.put_typed({"algo": "pc"}, entry)
        result = cache.get({"algo": "pc"})
        assert result is not None
        assert result.objects["pdg"].content == "<g/>"


# Test put_typed rejects an entry holding several objects.
def test_put_typed_rejects_multiple_objects() -> None:
    with WorkflowCache(":memory:") as cache:
        entry = CacheEntry()
        entry.add_object("pdg", "graphml", "<g/>")
        entry.add_object("dag", "graphml", "<g/>")
        with pytest.raises(CacheTypeError):
            cache.put_typed({"algo": "pc"}, entry)


# Test put_typed rejects an object type conflicting with the cache.
def test_put_typed_rejects_conflicting_type() -> None:
    with WorkflowCache(":memory:") as cache:
        pdg_entry = CacheEntry()
        pdg_entry.add_object("pdg", "graphml", "<g/>")
        cache.put_typed({"algo": "pc"}, pdg_entry)

        dag_entry = CacheEntry()
        dag_entry.add_object("dag", "graphml", "<g/>")
        with pytest.raises(CacheTypeError):
            cache.put_typed({"algo": "ges"}, dag_entry)


# Test put_failure requires a known cache type.
def test_put_failure_requires_known_type() -> None:
    with WorkflowCache(":memory:") as cache:
        with pytest.raises(CacheTypeError, match="before the cache"):
            cache.put_failure({"algo": "pc"}, {"status": "error"}, "learn")


# Test put_failure stores provenance plus an empty object.
def test_put_failure_stores_empty_object() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.set_cache_type("dag")
        cache.put_failure({"algo": "pc"}, {"status": "error"}, "learn_graph")
        result = cache.get({"algo": "pc"})
        assert result is not None
        assert result.metadata == {"status": "error"}
        assert result.objects["dag"].is_empty is True


# Test put_failure pins an explicitly supplied cache type.
def test_put_failure_pins_explicit_type() -> None:
    with WorkflowCache(":memory:") as cache:
        cache.put_failure(
            {"algo": "pc"},
            {"status": "error"},
            "learn_graph",
            cache_type="dag",
        )
        assert cache.get_cache_type() == "dag"


# Test the legacy put path still accepts multiple objects.
def test_legacy_put_accepts_multiple_objects() -> None:
    with WorkflowCache(":memory:") as cache:
        entry = CacheEntry()
        entry.add_object("pdg", "graphml", "<g/>")
        entry.add_object("dag", "graphml", "<g/>")
        cache.put({"algo": "pc"}, entry)
        result = cache.get({"algo": "pc"})
        assert result is not None
        assert sorted(result.object_types()) == ["dag", "pdg"]
