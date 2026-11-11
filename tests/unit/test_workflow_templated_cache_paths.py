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
