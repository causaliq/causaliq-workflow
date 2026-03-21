"""Integration tests for the summarisation paradigm.

These tests verify end-to-end aggregation workflows including cache
creation, entry storage, scanning, filtering, and action execution.
"""

import pytest

from causaliq_workflow.cache import CacheEntry, WorkflowCache
from causaliq_workflow.workflow import AggregationConfig, WorkflowExecutor


# Test complete aggregation workflow with multiple entries.
def test_aggregation_workflow_end_to_end(
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
) -> None:
    """Test complete aggregation from cache creation to action execution."""
    # Phase 1: Create input cache with multiple network/seed combinations
    input_cache = tmp_path / "graphs.db"  # type: ignore[operator]
    with WorkflowCache(input_cache) as cache:
        # Asia network with 3 seeds
        for seed in [1, 2, 3]:
            entry = CacheEntry(
                metadata={
                    "causaliq-research": {
                        "generate_graph": {
                            "status": "completed",
                            "node_count": 8,
                            "edge_count": 10 + seed,
                        }
                    }
                }
            )
            cache.put({"network": "asia", "seed": seed}, entry)

        # Alarm network with 3 seeds
        for seed in [1, 2, 3]:
            entry = CacheEntry(
                metadata={
                    "causaliq-research": {
                        "generate_graph": {
                            "status": "completed",
                            "node_count": 37,
                            "edge_count": 45 + seed,
                        }
                    }
                }
            )
            cache.put({"network": "alarm", "seed": seed}, entry)

    # Phase 2: Setup aggregation action that captures entries
    captured_entries: list = []

    class AggregateAction:
        name = "aggregate-action"
        version = "1.0.0"
        description = "Test aggregation action"

        def run(self, action, parameters, **kwargs):
            entries = parameters.get("_aggregation_entries", [])
            captured_entries.extend(entries)
            return ("success", {"count": len(entries)}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["aggregate-action"] = AggregateAction

    # Phase 3: Execute aggregation workflow for asia network
    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "summarise",
                "uses": "aggregate-action",
                "with": {
                    "action": "model_average",
                    "input": str(input_cache),
                },
            }
        ],
    }

    results = executor.execute_workflow(workflow, mode="run")

    # Verify: Should have captured 3 asia entries
    assert len(results) == 1
    assert len(captured_entries) == 3
    for entry in captured_entries:
        assert entry["matrix_values"]["network"] == "asia"


# Test aggregation with filter expression.
def test_aggregation_with_filter(
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
) -> None:
    """Test that filter expressions correctly exclude entries."""
    input_cache = tmp_path / "graphs.db"  # type: ignore[operator]
    with WorkflowCache(input_cache) as cache:
        # Mix of completed and failed entries
        for i, status in enumerate(["completed", "failed", "completed"]):
            entry = CacheEntry(
                metadata={
                    "provider": {
                        "action": {
                            "status": status,
                            "index": i,
                        }
                    }
                }
            )
            cache.put({"network": "asia", "run": i}, entry)

    captured_entries: list = []

    class FilterAction:
        name = "filter-action"
        version = "1.0.0"
        description = "Test filter action"

        def run(self, action, parameters, **kwargs):
            entries = parameters.get("_aggregation_entries", [])
            captured_entries.extend(entries)
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["filter-action"] = FilterAction

    # Execute with filter for completed status only
    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "filtered-summarise",
                "uses": "filter-action",
                "with": {
                    "action": "summarise",
                    "input": str(input_cache),
                    "filter": "status == 'completed'",
                },
            }
        ],
    }

    executor.execute_workflow(workflow, mode="run")

    # Only 2 completed entries should pass filter
    assert len(captured_entries) == 2
    for entry in captured_entries:
        status = entry["metadata"]["provider"]["action"]["status"]
        assert status == "completed"


# Test aggregation across multiple input caches.
def test_aggregation_multiple_caches(
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
) -> None:
    """Test aggregation combining entries from multiple caches."""
    # Create two separate caches (e.g., from different algorithms)
    pc_cache = tmp_path / "pc_results.db"  # type: ignore[operator]
    with WorkflowCache(pc_cache) as cache:
        entry = CacheEntry(metadata={"algorithm": "pc", "edges": 10})
        cache.put({"network": "asia"}, entry)

    ges_cache = tmp_path / "ges_results.db"  # type: ignore[operator]
    with WorkflowCache(ges_cache) as cache:
        entry = CacheEntry(metadata={"algorithm": "ges", "edges": 12})
        cache.put({"network": "asia"}, entry)

    captured_entries: list = []

    class MergeAction:
        name = "merge-action"
        version = "1.0.0"
        description = "Merge action"

        def run(self, action, parameters, **kwargs):
            entries = parameters.get("_aggregation_entries", [])
            captured_entries.extend(entries)
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["merge-action"] = MergeAction

    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "merge",
                "uses": "merge-action",
                "with": {
                    "action": "merge",
                    "input": [str(pc_cache), str(ges_cache)],
                },
            }
        ],
    }

    executor.execute_workflow(workflow, mode="run")

    # Should have entries from both caches
    assert len(captured_entries) == 2
    algorithms = {e["metadata"]["algorithm"] for e in captured_entries}
    assert algorithms == {"pc", "ges"}


# Test aggregation grouping by matrix variables.
def test_aggregation_matrix_grouping(
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
) -> None:
    """Test that entries are correctly grouped by matrix variables."""
    input_cache = tmp_path / "graphs.db"  # type: ignore[operator]
    with WorkflowCache(input_cache) as cache:
        # Entries for multiple networks
        for network in ["asia", "alarm", "sachs"]:
            for seed in [1, 2]:
                entry = CacheEntry(metadata={"network": network, "seed": seed})
                cache.put({"network": network, "seed": seed}, entry)

    results_by_network: dict = {}

    class GroupAction:
        name = "group-action"
        version = "1.0.0"
        description = "Group action"

        def run(self, action, parameters, **kwargs):
            context = kwargs.get("context")
            entries = parameters.get("_aggregation_entries", [])
            network = context.matrix_values.get("network")
            results_by_network[network] = len(entries)
            return ("success", {}, [])

        def get_action_schema(self, action):
            return {}

    executor = WorkflowExecutor()
    executor.action_registry._actions["group-action"] = GroupAction

    workflow = {
        "matrix": {"network": ["asia", "alarm", "sachs"]},
        "steps": [
            {
                "name": "group",
                "uses": "group-action",
                "with": {
                    "action": "group",
                    "input": str(input_cache),
                },
            }
        ],
    }

    executor.execute_workflow(workflow, mode="run")

    # Each network should have 2 entries (2 seeds each)
    assert results_by_network == {"asia": 2, "alarm": 2, "sachs": 2}


# Test aggregation scan statistics logging.
def test_aggregation_scan_logging(
    tmp_path: pytest.TempPathFactory,  # type: ignore[name-defined]
) -> None:
    """Test that aggregation scan logs correct statistics."""
    input_cache = tmp_path / "graphs.db"  # type: ignore[operator]
    with WorkflowCache(input_cache) as cache:
        # 5 entries: 3 completed, 2 failed
        for i in range(5):
            status = "completed" if i < 3 else "failed"
            entry = CacheEntry(
                metadata={"provider": {"action": {"status": status}}}
            )
            cache.put({"network": "asia", "run": i}, entry)

    executor = WorkflowExecutor()

    config = AggregationConfig(
        input_caches=[str(input_cache)],
        filter_expr="status == 'completed'",
        matrix_vars=["network"],
    )

    log_messages: list = []
    results = executor._scan_aggregation_inputs(
        config,
        {"network": "asia"},
        logger=log_messages.append,
    )

    # Should have 3 matched, 2 filtered
    assert len(results) == 3
    assert len(log_messages) == 1
    assert "scanned=5" in log_messages[0]
    assert "filtered=2" in log_messages[0]
    assert "matched=3" in log_messages[0]
