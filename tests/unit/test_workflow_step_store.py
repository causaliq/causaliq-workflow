"""Unit tests for the workflow step store (step_store.py)."""

from pathlib import Path

from pytest_mock import MockerFixture

from causaliq_workflow.workflow import WorkflowExecutor


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

    def step_logger(
        action_method, step_name, status, matrix_values, **_: object
    ):
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

    def step_logger(
        action_method, step_name, status, matrix_values, **_: object
    ):
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


# Test a successful step stores the version 2 envelope with provenance.
def test_execute_workflow_records_version_two_envelope(
    executor: WorkflowExecutor,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    from causaliq_core import CausalIQActionProvider

    from causaliq_workflow.cache import WorkflowCache

    mocker.patch(
        "causaliq_workflow.workflow.step_store.collect_environment",
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
