"""Unit tests for WorkflowExecutor - execution and template variables."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from causaliq_workflow.workflow import (
    WorkflowExecutionError,
    WorkflowExecutor,
)


# Test resolving template variables in a dictionary.
def test_resolve_template_variables_dict(executor: WorkflowExecutor) -> None:
    variables = {"dataset": "asia", "algorithm": "pc"}
    obj = {
        "input": "{{dataset}}.csv",
        "output": "results/{{algorithm}}/{{dataset}}.xml",
        "nested": {"path": "/data/{{dataset}}/{{algorithm}}"},
    }
    result = executor._resolve_template_variables(obj, variables)
    assert result["input"] == "asia.csv"
    assert result["output"] == "results/pc/asia.xml"
    assert result["nested"]["path"] == "/data/asia/pc"


# Test resolving template variables in a list.
def test_resolve_template_variables_list(executor: WorkflowExecutor) -> None:
    variables = {"dataset": "asia", "num": "42"}
    obj = [
        "{{dataset}}.csv",
        "file_{{num}}.txt",
        {"name": "{{dataset}}_{{num}}"},
    ]
    result = executor._resolve_template_variables(obj, variables)
    assert result[0] == "asia.csv"
    assert result[1] == "file_42.txt"
    assert result[2]["name"] == "asia_42"


# Test resolving template variables in a string.
def test_resolve_template_variables_string(executor: WorkflowExecutor) -> None:
    variables = {"name": "test", "version": "1.0", "extra": "value"}
    obj = "{{name}}_v{{version}}_{{extra}}.log"
    result = executor._resolve_template_variables(obj, variables)
    assert result == "test_v1.0_value.log"


# Test resolving template variables with a missing variable.
def test_resolve_template_variables_missing(
    executor: WorkflowExecutor,
) -> None:
    variables = {"name": "test"}
    obj = "{{name}}_{{missing}}.log"
    result = executor._resolve_template_variables(obj, variables)
    assert result == "test_{{missing}}.log"


# Test resolving template variables with non-string types.
def test_resolve_template_variables_non_string(
    executor: WorkflowExecutor,
) -> None:
    variables = {"key": "value"}
    assert executor._resolve_template_variables(42, variables) == 42
    assert executor._resolve_template_variables(True, variables) is True
    assert executor._resolve_template_variables(None, variables) is None
    assert executor._resolve_template_variables(3.14, variables) == 3.14


# Test validation failure for unknown action.
def test_validate_workflow_actions_failure(
    executor: WorkflowExecutor,
) -> None:
    workflow = {"steps": [{"uses": "unknown-action", "name": "Test Step"}]}
    with pytest.raises(
        WorkflowExecutionError, match="Unknown provider 'unknown-action'"
    ):
        executor._validate_workflow_actions(workflow, "run")


# Test skipping validation in dry-run mode.
def test_validate_workflow_actions_dry_run_skip(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"action": "test", "param": "value"},
            }
        ]
    }
    executor._validate_workflow_actions(workflow, "dry-run")


# Test executing workflow in dry-run mode.
def test_execute_workflow_dry_run_mode(executor: WorkflowExecutor) -> None:
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"action": "test", "input": "{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="dry-run")
    assert len(results) == 1
    assert "job" in results[0]
    assert "steps" in results[0]
    assert "Test Step" in results[0]["steps"]
    step_result = results[0]["steps"]["Test Step"]
    assert step_result["status"] == "would_execute"


# Test executing workflow in run mode.
def test_execute_workflow_run_mode(executor: WorkflowExecutor) -> None:
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"action": "test", "input": "{{dataset}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 1
    assert "job" in results[0]
    assert "steps" in results[0]
    assert "Test Step" in results[0]["steps"]
    step_result = results[0]["steps"]["Test Step"]
    assert step_result["status"] == "executed"
    assert step_result["mode"] == "run"
    assert step_result["parameters"]["input"] == "asia.csv"


# Test executing workflow with CLI parameters.
def test_execute_workflow_with_cli_params(executor: WorkflowExecutor) -> None:
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
                    "action": "test",
                    "input": "{{dataset}}.csv",
                    "extra_param": "{{extra_param}}",
                },
            }
        ],
    }
    cli_params = {"extra_param": "cli_value"}
    results = executor.execute_workflow(
        workflow, mode="run", cli_params=cli_params
    )
    assert len(results) == 1
    step_result = results[0]["steps"]["Test Step"]
    assert "extra_param" in step_result["parameters"]
    assert step_result["parameters"]["extra_param"] == "cli_value"


# Test executing workflow with multiple matrix combinations.
def test_execute_workflow_multiple_matrix(executor: WorkflowExecutor) -> None:
    workflow = {
        "matrix": {
            "dataset": ["asia", "cancer"],
            "algorithm": ["pc", "ges"],
        },
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {
                    "action": "test",
                    "dataset": "{{dataset}}",
                    "algorithm": "{{algorithm}}",
                },
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 4
    combinations = []
    for result in results:
        step_result = result["steps"]["Test Step"]
        combinations.append(
            (
                step_result["parameters"]["dataset"],
                step_result["parameters"]["algorithm"],
            )
        )
    expected_combinations = [
        ("asia", "pc"),
        ("asia", "ges"),
        ("cancer", "pc"),
        ("cancer", "ges"),
    ]
    assert set(combinations) == set(expected_combinations)


# Test workflow execution error when action fails.
def test_execute_workflow_action_execution_error(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_failing_action",
                "name": "Failing Step",
                "with": {"action": "test"},
            }
        ],
    }
    with pytest.raises(
        WorkflowExecutionError, match="Workflow execution failed"
    ):
        executor.execute_workflow(workflow, mode="run")


# Test workflow execution error for missing action.
def test_execute_workflow_missing_action(executor: WorkflowExecutor) -> None:
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "nonexistent-action",
                "name": "Missing Action Step",
                "with": {"action": "test"},
            }
        ],
    }
    with pytest.raises(
        WorkflowExecutionError, match="Action 'nonexistent-action' not found"
    ):
        executor.execute_workflow(workflow, mode="run")


# Test matrix variables are NOT passed implicitly to actions (explicit only).
def test_execute_workflow_matrix_params_require_explicit_specification(
    executor: WorkflowExecutor,
) -> None:
    """Matrix variables should NOT be passed to actions without {{var}}."""
    workflow = {
        "matrix": {
            "network": ["asia", "alarm"],
            "sample_size": [100, 500],
        },
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                # Note: no {{network}} or {{sample_size}} templates
                "with": {"action": "test", "explicit_param": "value"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")

    # Should have 4 combinations (2 networks × 2 sample_sizes)
    assert len(results) == 4

    # Verify each result does NOT have implicit matrix params
    for result in results:
        step_result = result["steps"]["Test Step"]
        params = step_result["parameters"]

        # Explicit param should be present
        assert params["explicit_param"] == "value"

        # Matrix variables should NOT be implicitly passed
        assert "network" not in params
        assert "sample_size" not in params


# Test matrix params are passed when explicitly specified via templates.
def test_execute_workflow_explicit_matrix_params_via_templates(
    executor: WorkflowExecutor,
) -> None:
    """Matrix variables passed via {{var}} templates should work."""
    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                # Explicit network param via template
                "with": {"action": "test", "network": "{{network}}"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 1

    step_result = results[0]["steps"]["Test Step"]
    params = step_result["parameters"]

    # Explicit param via template should be present
    assert params["network"] == "asia"


# Test error when action produces objects but no workflow cache is open.
def test_execute_workflow_objects_without_cache_raises_error(
    executor: WorkflowExecutor,
) -> None:
    """Action producing objects without a cache destination raises error."""
    workflow = {
        "steps": [
            {
                "uses": "mock_object_action",
                "name": "Produce Objects",
                "with": {"action": "test"},
                # Note: no 'output' specified, so no cache is created
            }
        ],
    }
    with pytest.raises(
        WorkflowExecutionError,
        match="produced objects but no workflow cache is open",
    ):
        executor.execute_workflow(workflow, mode="run")


# A step returning error with failure metadata records a cache entry.
def test_execute_workflow_records_failure_entry(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    from causaliq_core import CausalIQActionProvider

    from causaliq_workflow.cache import WorkflowCache

    class MockFailureRecordingAction(CausalIQActionProvider):
        name = "mock-failure-recording"
        supported_actions = {"learn_graph"}

        def _execute(self, action, parameters, mode, context, logger):
            metadata = {"status": "input", "error": "bad data"}
            return ("error", metadata, [])

    executor.action_registry._actions["mock_failure_recording"] = (
        MockFailureRecordingAction
    )

    db_path = tmp_path / "out.db"
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_failure_recording",
                "name": "Test Step",
                "with": {
                    "action": "learn_graph",
                    "output": str(db_path),
                },
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    step_result = results[0]["steps"]["Test Step"]
    assert step_result["status"] == "error"

    with WorkflowCache(str(db_path)) as cache:
        entries = cache.list_entries()
        assert len(entries) == 1
        entry = cache.get(entries[0]["matrix_values"])
        assert entry is not None
        assert entry.objects == {}
        metadata = entry.metadata
        assert metadata["provenance"]["provider"] == "mock-failure-recording"
        assert metadata["provenance"]["action"] == "learn_graph"
        assert metadata["result"]["status"] == "input"
        assert metadata["result"]["error"] == "bad data"


# A failure replaces a typed entry with provenance only.
def test_execute_workflow_failure_replaces_entry_with_provenance(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    from causaliq_core import CausalIQActionProvider

    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    class MockFailingLearner(CausalIQActionProvider):
        name = "mock-failing-learner"
        supported_actions = {"learn_graph"}

        def _execute(self, action, parameters, mode, context, logger):
            return ("error", {"status": "failed", "error": "boom"}, [])

    executor.action_registry._actions["mock_failing_learner"] = (
        MockFailingLearner
    )

    db_path = tmp_path / "out.db"
    key = {"dataset": "asia"}
    with WorkflowCache(str(db_path)) as cache:
        entry = CacheEntry()
        entry.add_object("dag", "graphml", "<graphml/>", "learn_graph")
        cache.put_typed(key, entry)

    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_failing_learner",
                "name": "Test Step",
                "with": {"action": "learn_graph", "output": str(db_path)},
            }
        ],
    }
    executor.execute_workflow(workflow, mode="force")

    with WorkflowCache(str(db_path)) as cache:
        entry = cache.get(key)
        assert entry is not None
        assert entry.objects == {}
        metadata = entry.metadata
        assert metadata["provenance"]["provider"] == "mock-failing-learner"
        assert metadata["provenance"]["action"] == "learn_graph"
        assert metadata["result"]["error"] == "boom"


# Test step logging reports executed and forced completions.
def test_execute_workflow_logs_step_completion(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    from causaliq_core import CausalIQActionProvider

    class MockSuccessfulAction(CausalIQActionProvider):
        name = "mock-successful"
        supported_actions = {"learn_graph"}

        def _execute(self, action, parameters, mode, context, logger):
            return (
                "success",
                {"status": "done"},
                [
                    {
                        "type": "dag",
                        "format": "graphml",
                        "action": "learn_graph",
                        "content": "<graphml/>",
                    }
                ],
            )

    executor.action_registry._actions["mock_successful"] = MockSuccessfulAction
    statuses = []

    def step_logger(action_method, step_name, status, matrix_values):
        statuses.append(status)

    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_successful",
                "name": "Test Step",
                "with": {
                    "action": "learn_graph",
                    "output": str(tmp_path / "out.db"),
                },
            }
        ],
    }
    executor.execute_workflow(workflow, mode="run", step_logger=step_logger)
    executor.execute_workflow(workflow, mode="force", step_logger=step_logger)

    assert statuses == ["EXECUTED", "FORCED"]


# Test step logging reports a failed step.
def test_execute_workflow_logs_failed_step(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    from causaliq_core import CausalIQActionProvider

    class MockErrorAction(CausalIQActionProvider):
        name = "mock-error-action"
        supported_actions = {"learn_graph"}

        def _execute(self, action, parameters, mode, context, logger):
            return ("error", {"status": "failed", "error": "boom"}, [])

    executor.action_registry._actions["mock_error_action"] = MockErrorAction
    statuses = []

    def step_logger(action_method, step_name, status, matrix_values):
        statuses.append(status)

    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_error_action",
                "name": "Test Step",
                "with": {
                    "action": "learn_graph",
                    "output": str(tmp_path / "out.db"),
                },
            }
        ],
    }
    executor.execute_workflow(workflow, mode="run", step_logger=step_logger)

    assert statuses == ["FAILED"]


# Test step logging reports a skipped step.
def test_execute_workflow_logs_skipped_step(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    from causaliq_core import CausalIQActionProvider

    class MockSkippingAction(CausalIQActionProvider):
        name = "mock-skipping"
        supported_actions = {"learn_graph"}

        def _execute(self, action, parameters, mode, context, logger):
            return ("skipped", {"reason": "recorded failure"}, [])

    executor.action_registry._actions["mock_skipping"] = MockSkippingAction
    statuses = []

    def step_logger(action_method, step_name, status, matrix_values):
        statuses.append(status)

    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_skipping",
                "name": "Test Step",
                "with": {
                    "action": "learn_graph",
                    "output": str(tmp_path / "out.db"),
                },
            }
        ],
    }
    executor.execute_workflow(workflow, mode="run", step_logger=step_logger)

    assert statuses == ["SKIPPED"]


# Test dry-run reports would_skip when the output cache holds the entry.
def test_execute_workflow_dry_run_skips_existing_cache_entry(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    db_path = tmp_path / "out.db"
    with WorkflowCache(str(db_path)) as cache:
        entry = CacheEntry()
        entry.add_object("dag", "graphml", "<graphml/>", "learn_graph")
        cache.put_typed({"dataset": "asia"}, entry)

    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock_workflow_action",
                "name": "Test Step",
                "with": {"action": "test", "output": str(db_path)},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="dry-run")

    assert results[0]["steps"]["Test Step"]["status"] == "would_skip"


# Test a successful step stores the version 2 envelope with provenance.
def test_execute_workflow_records_version_two_envelope(
    executor: WorkflowExecutor,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    from causaliq_core import CausalIQActionProvider

    from causaliq_workflow.cache import WorkflowCache

    mocker.patch(
        "causaliq_workflow.workflow.execution.collect_environment",
        return_value={
            "os": "test-os",
            "cpu": "test-cpu",
            "python": "3.12.4",
            "ram": 8,
        },
    )

    class MockVersionTwoAction(CausalIQActionProvider):
        name = "mock-version-two"
        version = "1.2.3"
        supported_actions = {"learn_graph"}

        def _execute(self, action, parameters, mode, context, logger):
            metadata = {"status": "ok", "node_count": 5}
            objects = [{"type": "dag", "format": "graphml", "content": "<g/>"}]
            return ("success", metadata, objects)

    executor.action_registry._actions["mock-version-two"] = (
        MockVersionTwoAction
    )

    db_path = tmp_path / "out.db"
    workflow = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "mock-version-two",
                "name": "Test Step",
                "with": {
                    "action": "learn_graph",
                    "output": str(db_path),
                },
            }
        ],
    }
    executor.execute_workflow(workflow, mode="run")

    with WorkflowCache(str(db_path)) as cache:
        entry = cache.get({"dataset": "asia"})
        assert entry is not None
        metadata = entry.metadata
        assert set(metadata) == {
            "provenance",
            "parameters",
            "result",
            "history",
        }
        provenance = metadata["provenance"]
        assert provenance["provider"] == "mock-version-two"
        assert provenance["provider_version"] == "1.2.3"
        assert provenance["action"] == "learn_graph"
        assert provenance["environment"]["python"] == "3.12.4"
        assert provenance["started"] is not None
        assert isinstance(provenance["elapsed"], float)
        assert "finished_at" not in provenance
        assert metadata["parameters"] == {}
        assert metadata["result"]["node_count"] == 5
        assert metadata["history"] == {}
