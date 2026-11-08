"""Tests for entry-scan ordering and lazy reporting views.

The scan matches matrix values before it evaluates a filter expression,
and it builds reporting views only for the entries it keeps. These tests
pin both properties, which is what keeps a scan cheap on a large cache.
"""

from typing import Any, Dict, Iterable, Set

import pytest
from pytest_mock import MockerFixture

from causaliq_workflow.cache import CacheEntry, WorkflowCache
from causaliq_workflow.cache.reporting import (
    build_entry_view,
    evaluate_entry_filter,
)
from causaliq_workflow.workflow import WorkflowExecutor
from causaliq_workflow.workflow.entry_scan import (
    AggregationConfig,
    _fill_views,
    _PopulationEntry,
)
from causaliq_workflow.workflow.matrix import _matrix_values_match


def _write_entries(path: Any, rows: Iterable[Dict[str, Any]]) -> None:
    """Write one cache entry per row of matrix values."""
    with WorkflowCache(path) as cache:
        for row in rows:
            cache.put(row, CacheEntry(metadata={"status": "completed"}))


def _reference_hashes(
    path: Any,
    config: AggregationConfig,
    job: Dict[str, Any],
) -> Set[str]:
    """Return entry hashes found by filtering first, then matching."""
    with WorkflowCache(path) as cache:
        summaries = cache.list_entry_summaries()

    hashes: Set[str] = set()
    for summary in summaries:
        view = build_entry_view(summary["matrix_values"], summary["metadata"])
        if not evaluate_entry_filter(str(config.filter_expr), view):
            continue
        if _matrix_values_match(
            summary["matrix_values"], job, config.matrix_vars
        ):
            hashes.add(summary["hash"])
    return hashes


# Test the filter runs only for entries matching the job's matrix values.
def test_scan_filters_only_matrix_matching_entries(
    executor: WorkflowExecutor,
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
    mocker: MockerFixture,
) -> None:
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    _write_entries(
        cache_path,
        [
            {"network": "asia", "seed": 0},
            {"network": "asia", "seed": 1},
            {"network": "alarm", "seed": 0},
        ],
    )
    config = AggregationConfig(
        input_caches=[str(cache_path)],
        filter_expr="seed > 0",
        matrix_vars=["network"],
    )

    spy = mocker.patch(
        "causaliq_workflow.cache.reporting.evaluate_entry_filter",
        wraps=evaluate_entry_filter,
    )
    results = executor._scan_input_entries(config, {"network": "asia"})

    assert len(results) == 1
    assert spy.call_count == 2


# Test the scan returns the entries a filter-first scan would return.
def test_scan_matches_filter_first_reference(
    executor: WorkflowExecutor,
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
) -> None:
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    _write_entries(
        cache_path,
        [{"network": "asia", "seed": seed} for seed in range(4)]
        + [{"network": "alarm", "seed": seed} for seed in range(4)],
    )
    config = AggregationConfig(
        input_caches=[str(cache_path)],
        filter_expr="seed < 2",
        matrix_vars=["network"],
    )

    results = executor._scan_input_entries(config, {"network": "alarm"})
    found = {entry["entry_hash"] for entry in results}

    assert found == _reference_hashes(cache_path, config, {"network": "alarm"})
    assert len(results) == 2


# Test a templated input reads the cache its resolved path names.
def test_scan_uses_resolved_input_path(
    executor: WorkflowExecutor,
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
) -> None:
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    _write_entries(
        cache_path,
        [{"network": "asia", "seed": seed} for seed in range(2)],
    )
    step = {"uses": "action", "with": {"input": "{{cache_dir}}/input.db"}}
    config = executor._get_entry_scan_config(step, {"network": ["asia"]})
    assert config is not None
    resolved = executor._resolve_template_variables(
        step["with"], {"cache_dir": str(tmp_path)}
    )

    entries = executor._scan_entries_for(config, resolved, {"network": "asia"})

    assert len(entries) == 2


# Test a job with no matrix match does not open the cache at all.
def test_scan_skips_cache_open_without_matrix_match(
    executor: WorkflowExecutor,
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
    mocker: MockerFixture,
) -> None:
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    _write_entries(cache_path, [{"network": "asia"}])
    config = AggregationConfig(
        input_caches=[str(cache_path)],
        matrix_vars=["network"],
    )

    executor._scan_input_entries(config, {"network": "asia"})
    spy = mocker.spy(WorkflowCache, "open")

    results = executor._scan_input_entries(config, {"network": "sachs"})
    assert results == []
    assert spy.call_count == 0


# Test metadata is decompressed only for the entries that matched.
def test_scan_decompresses_metadata_for_candidates_only(
    executor: WorkflowExecutor,
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
    mocker: MockerFixture,
) -> None:
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    _write_entries(
        cache_path,
        [{"network": "asia", "seed": seed} for seed in range(3)]
        + [{"network": "alarm", "seed": seed} for seed in range(4)],
    )
    config = AggregationConfig(
        input_caches=[str(cache_path)],
        matrix_vars=["network"],
    )

    executor._scan_index_for(str(cache_path))
    spy = mocker.spy(WorkflowCache, "decompress_metadata")

    results = executor._scan_input_entries(config, {"network": "asia"})
    assert len(results) == 3
    assert spy.call_count == 3


# Test a random() population on a matrix value needs no metadata read.
def test_random_population_reads_matrix_values(
    executor: WorkflowExecutor,
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
    mocker: MockerFixture,
) -> None:
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    _write_entries(
        cache_path,
        [{"network": "asia", "seed": seed} for seed in range(3)]
        + [{"network": "alarm", "seed": seed} for seed in range(4)],
    )
    config = AggregationConfig(
        input_caches=[str(cache_path)],
        filter_expr="seed in random(2, 0)",
        matrix_vars=["network"],
    )

    executor._scan_index_for(str(cache_path))
    spy = mocker.spy(WorkflowCache, "decompress_metadata")

    results = executor._scan_input_entries(config, {"network": "asia"})
    selected = {entry["matrix_values"]["seed"] for entry in results}
    assert selected <= {0, 1, 2}
    assert 1 <= len(selected) <= 2
    assert spy.call_count == 3


# Test a random() population on a metadata name reads every entry.
def test_random_population_falls_back_to_metadata(
    executor: WorkflowExecutor,
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
    mocker: MockerFixture,
) -> None:
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    with WorkflowCache(cache_path) as cache:
        for index, label in enumerate("abcde"):
            metadata = {"provider": {"action": {"label": label}}}
            key = {"network": "asia", "run": index}
            cache.put(key, CacheEntry(metadata=metadata))
    config = AggregationConfig(
        input_caches=[str(cache_path)],
        filter_expr="action.label in random(2, 0)",
        matrix_vars=["network"],
    )

    executor._scan_index_for(str(cache_path))
    spy = mocker.spy(WorkflowCache, "decompress_metadata")

    results = executor._scan_input_entries(config, {"network": "asia"})
    assert len(results) == 2
    assert spy.call_count == 5


# Test a population entry exposes matrix values and the full view.
def test_population_entry_exposes_values(
    executor: WorkflowExecutor,
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
) -> None:
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    metadata = {"provider": {"action": {"label": "alpha"}}}
    with WorkflowCache(cache_path) as cache:
        cache.put({"network": "asia"}, CacheEntry(metadata=metadata))

    index = executor._scan_index_for(str(cache_path))
    entry = _PopulationEntry(str(cache_path), index[0], index)

    assert entry["network"] == "asia"
    assert "network" in entry
    assert entry["action.label"] == "alpha"
    assert "action.label" in entry
    assert sorted(entry) == sorted(dict(entry))
    assert len(entry) == len(dict(entry))


# Test building views is a no-op once the index holds them.
def test_fill_views_is_noop_when_views_exist(
    executor: WorkflowExecutor,
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
    mocker: MockerFixture,
) -> None:
    cache_path = tmp_path / "input.db"  # type: ignore[operator]
    _write_entries(cache_path, [{"network": "asia"}])
    index = executor._scan_index_for(str(cache_path))

    _fill_views(str(cache_path), index)
    spy = mocker.spy(WorkflowCache, "open")
    _fill_views(str(cache_path), index)

    assert spy.call_count == 0
    assert index[0]["flat_meta"] is not None
