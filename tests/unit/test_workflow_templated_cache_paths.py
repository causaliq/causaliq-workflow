"""Matrix derivation from templated input cache paths.

Cache introspection runs before a job exists, so the executor must
resolve the workflow's parameter defaults and the values supplied by a
caller or the CLI before it reads a path such as
``{{cache_dir}}/dags.db``. These tests pin that behaviour for MAP steps,
whose matrix is taken from the input cache when the workflow declares no
matrix of its own.
"""

from pathlib import Path
from typing import Any, Dict, Iterable

import pytest
from causaliq_core import ActionPattern

from causaliq_workflow.cache import CacheEntry, WorkflowCache
from causaliq_workflow.workflow import WorkflowExecutor
from causaliq_workflow.workflow.entry_scan import AggregationConfig


def _write_entries(path: Any, rows: Iterable[Dict[str, Any]]) -> None:
    """Write one cache entry per row of matrix values."""
    with WorkflowCache(path) as cache:
        for row in rows:
            cache.put(row, CacheEntry())


def _use_map_pattern(
    executor: WorkflowExecutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Make every action look like a MAP and accept any parameters."""
    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        lambda provider, action: ActionPattern.MAP,
    )
    monkeypatch.setattr(
        executor.action_registry,
        "validate_action_parameters",
        lambda provider, inputs: None,
    )


def _workflow(cache_dir: Any = None) -> Dict[str, Any]:
    """Return a one-step MAP workflow whose input path is templated."""
    workflow: Dict[str, Any] = {
        "steps": [
            {
                "name": "evaluate",
                "uses": "map-provider",
                "with": {
                    "action": "evaluate",
                    "input": "{{cache_dir}}/input.db",
                    "output": "{{cache_dir}}/output.db",
                },
            }
        ]
    }
    if cache_dir is not None:
        workflow["cache_dir"] = cache_dir
    return workflow


def _write_input(tmp_path: Path) -> None:
    """Write an input cache with two dimensions."""
    _write_entries(
        tmp_path / "input.db",
        [
            {"network": "asia", "seed": 0},
            {"network": "asia", "seed": 1},
            {"network": "alarm", "seed": 0},
        ],
    )


# A declared default resolves the templated path before the cache is read.
def test_derive_workflow_matrix_resolves_declared_default(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A top-level default is used to resolve the MAP input path."""
    _use_map_pattern(executor, monkeypatch)
    _write_input(tmp_path)

    matrix = executor._derive_workflow_matrix(_workflow(str(tmp_path)), {})

    assert matrix == {"network": ["alarm", "asia"], "seed": [0, 1]}


# A supplied parameter overrides the declared default for path resolution.
def test_derive_workflow_matrix_resolves_supplied_parameter(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CLI or caller value is used instead of a declared default."""
    _use_map_pattern(executor, monkeypatch)
    _write_input(tmp_path)
    workflow = _workflow("missing-directory")

    matrix = executor._derive_workflow_matrix(
        workflow, {"cache_dir": str(tmp_path)}
    )

    assert matrix == {"network": ["alarm", "asia"], "seed": [0, 1]}


# An unresolved path keeps the existing raw-definition behaviour.
def test_derive_workflow_matrix_leaves_unresolved_path_unresolved(
    executor: WorkflowExecutor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No value for the token means no matrix can be derived."""
    _use_map_pattern(executor, monkeypatch)

    assert executor._derive_workflow_matrix(_workflow(), {}) == {}


# The scan config resolves its input path and derives its matrix keys.
def test_get_entry_scan_config_resolves_templated_input(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A templated input yields the resolved cache and its keys."""
    _use_map_pattern(executor, monkeypatch)
    _write_input(tmp_path)
    workflow = _workflow()

    config = executor._get_entry_scan_config(
        workflow["steps"][0], {}, {"cache_dir": str(tmp_path)}
    )

    assert config is not None
    assert [Path(path) for path in config.input_caches] == [
        tmp_path / "input.db"
    ]
    assert config.matrix_vars == ["network", "seed"]
    assert config.derive_matrix_vars is True


# The validation pass accepts a templated MAP input path.
def test_validate_all_entries_accepts_templated_map_input(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each derived job selects one entry, so the arity check passes."""
    _use_map_pattern(executor, monkeypatch)
    _write_input(tmp_path)

    errors = executor._validate_all_entries(
        _workflow(), {"cache_dir": str(tmp_path)}
    )

    assert errors == []


# A scan config rebuilt from resolved inputs derives the keys again.
def test_resolved_entry_scan_config_rederives_matrix_vars(
    executor: WorkflowExecutor,
    tmp_path: Path,
) -> None:
    """Resolving a path after the raw config was built updates the keys."""
    _write_input(tmp_path)
    config = AggregationConfig(
        input_caches=["{{cache_dir}}/input.db"],
        matrix_vars=[],
        derive_matrix_vars=True,
    )

    resolved = executor._resolved_entry_scan_config(
        config, {"input": str(tmp_path / "input.db")}
    )

    assert [Path(path) for path in resolved.input_caches] == [
        tmp_path / "input.db"
    ]
    assert resolved.matrix_vars == ["network", "seed"]


# An explicit matrix still constrains the scan and reports ambiguity.
def test_validate_all_entries_reports_multiple_matches_for_explicit_matrix(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit matrix with too few dimensions still reports matches."""
    _use_map_pattern(executor, monkeypatch)
    _write_input(tmp_path)
    workflow = _workflow()
    workflow["matrix"] = {"network": ["asia"]}

    errors = executor._validate_all_entries(
        workflow, {"cache_dir": str(tmp_path)}
    )

    assert len(errors) == 1
    assert "matched 2" in errors[0]
    assert "add a matrix key to distinguish them" in errors[0]


def _use_aggregate_pattern(
    executor: WorkflowExecutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Make every action look like an AGGREGATE and accept any parameters."""
    monkeypatch.setattr(
        executor.action_registry,
        "get_action_pattern",
        lambda provider, action: ActionPattern.AGGREGATE,
    )
    monkeypatch.setattr(
        executor.action_registry,
        "validate_action_parameters",
        lambda provider, inputs: None,
    )


def _write_mixed_key_caches(tmp_path: Path) -> None:
    """Write a swept cache and a per-network cache for the same network."""
    _write_entries(
        tmp_path / "sweep.db",
        [
            {"network": "asia", "fusion_weights": [0.85, 0.15]},
            {"network": "asia", "fusion_weights": [0.9, 0.1]},
        ],
    )
    _write_entries(tmp_path / "fused.db", [{"network": "asia"}])


def test_collect_matrix_keys_unions_input_caches(tmp_path: Path) -> None:
    """Key discovery unions the dimensions of every input cache."""
    from causaliq_workflow.workflow.matrix import _collect_matrix_keys

    _write_mixed_key_caches(tmp_path)

    keys = _collect_matrix_keys(
        [
            str(tmp_path / "sweep.db"),
            str(tmp_path / "fused.db"),
            str(tmp_path / "missing.db"),
        ]
    )

    assert keys == {"network", "fusion_weights"}


def test_aggregate_scope_accepts_caches_with_different_keys(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An aggregation step may read caches holding different dimensions."""
    _use_aggregate_pattern(executor, monkeypatch)
    _write_mixed_key_caches(tmp_path)
    parameters = {"cache_dir": str(tmp_path)}
    workflow: Dict[str, Any] = {
        "matrix": {"network": ["alarm", "asia"]},
        "cache_dir": str(tmp_path),
        "steps": [
            {
                "name": "summarise",
                "uses": "aggregate-provider",
                "with": {
                    "action": "summarise",
                    "input": [
                        "{{cache_dir}}/sweep.db",
                        "{{cache_dir}}/fused.db",
                    ],
                    "metric": ["f1.max[1]", "f1.mean[2]"],
                    "output": "{{cache_dir}}/table.md",
                },
            }
        ],
    }

    derived, deferred = executor._aggregate_template_scope(
        workflow, parameters
    )

    assert derived == {"network", "fusion_weights"}
    assert deferred == set()
    assert executor._missing_variable_errors(workflow, parameters) == []
    # The failure that rejected this shape used to surface here.
    executor._validate_template_variables(workflow, parameters)


def _map_step(tmp_path: Path) -> Dict[str, Any]:
    """Return a one-step MAP definition reading the two mixed-key caches."""
    return {
        "uses": "map-provider",
        "with": {
            "action": "evaluate",
            "input": [
                "{{cache_dir}}/sweep.db",
                "{{cache_dir}}/fused.db",
            ],
            "output": "{{cache_dir}}/output.db",
        },
    }


def _mixed_key_config(tmp_path: Path) -> AggregationConfig:
    """Return the scan configuration for the two mixed-key caches."""
    return AggregationConfig(
        input_caches=[
            str(tmp_path / "sweep.db"),
            str(tmp_path / "fused.db"),
        ],
        matrix_vars=["network"],
    )


def test_map_input_key_error_reports_mixed_keys(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MAP step cannot join caches whose entries carry different keys."""
    _use_map_pattern(executor, monkeypatch)
    _write_mixed_key_caches(tmp_path)

    error = executor._map_input_key_error(
        "evaluate", _map_step(tmp_path), _mixed_key_config(tmp_path)
    )

    assert error is not None
    assert "must use the same matrix keys" in error
    assert "fusion_weights" in error


def test_map_input_key_error_allows_like_keys(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caches that agree on their dimensions are accepted."""
    _use_map_pattern(executor, monkeypatch)
    _write_entries(tmp_path / "sweep.db", [{"network": "asia"}])
    _write_entries(tmp_path / "fused.db", [{"network": "alarm"}])

    assert (
        executor._map_input_key_error(
            "evaluate", _map_step(tmp_path), _mixed_key_config(tmp_path)
        )
        is None
    )


def test_map_input_key_error_ignores_aggregate_steps(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aggregation collapses dimensions, so mixed keys are allowed."""
    _use_aggregate_pattern(executor, monkeypatch)
    _write_mixed_key_caches(tmp_path)

    assert (
        executor._map_input_key_error(
            "summarise", _map_step(tmp_path), _mixed_key_config(tmp_path)
        )
        is None
    )


def test_map_input_key_error_skips_missing_caches(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cache an earlier step has not written yet is not compared."""
    _use_map_pattern(executor, monkeypatch)
    _write_entries(
        tmp_path / "sweep.db",
        [{"network": "asia", "fusion_weights": [0.5, 0.5]}],
    )

    assert (
        executor._map_input_key_error(
            "evaluate", _map_step(tmp_path), _mixed_key_config(tmp_path)
        )
        is None
    )


def test_map_input_key_error_ignores_steps_without_cache_scan(
    executor: WorkflowExecutor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A step the scan configuration does not cover has no keys to compare."""
    _use_map_pattern(executor, monkeypatch)
    step: Dict[str, Any] = {
        "uses": "map-provider",
        "with": {"action": "evaluate"},
    }

    assert executor._map_input_key_error("evaluate", step, None) is None


def test_validate_all_entries_reports_mixed_input_keys(
    executor: WorkflowExecutor,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The validation pass reports a MAP step's mixed input keys once."""
    _use_map_pattern(executor, monkeypatch)
    _write_mixed_key_caches(tmp_path)
    workflow: Dict[str, Any] = {
        "matrix": {"network": ["asia"]},
        "cache_dir": str(tmp_path),
        "steps": [{"name": "evaluate", **_map_step(tmp_path)}],
    }

    errors = executor._validate_all_entries(
        workflow, {"cache_dir": str(tmp_path)}
    )

    assert len(errors) == 1
    assert "must use the same matrix keys" in errors[0]
    assert "fusion_weights" in errors[0]
