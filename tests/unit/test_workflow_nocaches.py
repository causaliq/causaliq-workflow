"""Unit tests for the NOCACHES workflow action pattern."""

from causaliq_core import (
    ActionPattern,
    ActionValidationError,
    CausalIQActionProvider,
)

from causaliq_workflow.workflow import WorkflowExecutor


class NocachesActionProvider(CausalIQActionProvider):
    """Mock provider with a NOCACHES pattern action."""

    name = "nocaches-provider"
    version = "1.0.0"
    supported_actions = {"nocache_action"}
    action_patterns = {"nocache_action": ActionPattern.NOCACHES}

    def _execute(self, action, parameters, mode, context, logger):
        """Execute the mock nocaches action."""
        return ("success", {"ran": True}, [])


def _make_executor() -> WorkflowExecutor:
    """Create an executor with the NOCACHES provider registered."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["nocaches-provider"] = (
        NocachesActionProvider
    )
    return executor


def _nocache_workflow(output="out.png") -> dict:
    """Return a workflow containing only a NOCACHES step."""
    return {
        "steps": [
            {
                "name": "nocache-step",
                "uses": "nocaches-provider",
                "with": {"action": "nocache_action", "output": output},
            }
        ]
    }


# NOCACHES steps pass pattern validation without a matrix or cache.
def test_nocaches_no_matrix_validation() -> None:
    """A NOCACHES step needs no matrix or cache requirements."""
    executor = _make_executor()
    errors = executor._validate_action_patterns(_nocache_workflow())
    assert errors == []


# NOCACHES pattern prohibits cache (.db) inputs.
def test_nocaches_prohibits_cache_input() -> None:
    """A NOCACHES step cannot read from a workflow cache."""
    executor = _make_executor()
    workflow = _nocache_workflow()
    workflow["steps"][0]["with"]["input"] = "cache.db"
    errors = executor._validate_action_patterns(workflow)
    assert any("prohibits cache input" in e for e in errors)


# NOCACHES pattern prohibits cache (.db) outputs.
def test_nocaches_prohibits_cache_output() -> None:
    """A NOCACHES step cannot write to a workflow cache."""
    executor = _make_executor()
    errors = executor._validate_action_patterns(
        _nocache_workflow(output="cache.db")
    )
    assert any("prohibits cache output" in e for e in errors)


# NOCACHES steps validate once without implicit matrix variables.
def test_nocaches_validate_all_entries_once() -> None:
    """NOCACHES steps are validated once regardless of matrix."""
    executor = _make_executor()
    workflow = _nocache_workflow()
    workflow["matrix"] = {"network": ["asia", "sports"]}
    errors = executor._validate_all_entries(workflow, {})
    assert errors == []


# NOCACHES steps run once when there is no matrix.
def test_nocaches_runs_once_no_matrix() -> None:
    """A NOCACHES step executes once in a workflow without a matrix."""
    executor = _make_executor()
    results = executor.execute_workflow(_nocache_workflow(), mode="run")
    assert len(results) == 1
    assert results[0]["steps"]["nocache-step"]["status"] == "success"


# NOCACHES steps run once and skip later matrix jobs.
def test_nocaches_runs_once_with_matrix() -> None:
    """A NOCACHES step runs once and skips subsequent matrix jobs."""
    executor = _make_executor()
    workflow = _nocache_workflow()
    workflow["matrix"] = {"network": ["asia", "sports"]}
    results = executor.execute_workflow(workflow, mode="run")
    assert len(results) == 2
    assert results[0]["steps"]["nocache-step"]["status"] == "success"
    assert results[1]["steps"]["nocache-step"]["status"] == "skipped"
    assert (
        results[1]["steps"]["nocache-step"].get("reason")
        == "nocache-step-runs-once"
    )


class StrictNocachesActionProvider(NocachesActionProvider):
    """Mock NOCACHES provider which requires a parameter."""

    name = "strict-nocaches-provider"

    def validate_parameters(self, action, parameters):
        """Require the required_param parameter."""
        super().validate_parameters(action, parameters)
        if "required_param" not in parameters:
            raise ActionValidationError("Missing required_param")


# _is_nocache_step returns False when the step has no provider.
def test_is_nocache_step_no_provider() -> None:
    """A step without a provider is not a NOCACHES step."""
    executor = _make_executor()
    assert (
        executor._is_nocache_step({"with": {"action": "nocache_action"}})
        is False
    )


# _is_nocache_step returns False when the step has no action name.
def test_is_nocache_step_no_action() -> None:
    """A step without an action name is not a NOCACHES step."""
    executor = _make_executor()
    assert executor._is_nocache_step({"uses": "nocaches-provider"}) is False


# NOCACHES parameter validation errors are reported once.
def test_nocaches_validation_error_reported() -> None:
    """NOCACHES validation errors are captured without matrix repetition."""
    executor = WorkflowExecutor()
    executor.action_registry._actions["strict-nocaches-provider"] = (
        StrictNocachesActionProvider
    )
    workflow = {
        "matrix": {"network": ["asia", "sports"]},
        "steps": [
            {
                "name": "strict-nocache-step",
                "uses": "strict-nocaches-provider",
                "with": {"action": "nocache_action"},
            }
        ],
    }
    errors = executor._validate_all_entries(workflow, {})
    assert len(errors) == 1  # validated once, not per matrix combination
    assert "Missing required_param" in errors[0]


# A skipped NOCACHES step logs a SKIPPED message via the step logger.
def test_nocaches_skipped_step_logs() -> None:
    """Later matrix jobs log a SKIPPED status for NOCACHES steps."""
    executor = _make_executor()
    workflow = _nocache_workflow()
    workflow["matrix"] = {"network": ["asia", "sports"]}
    logged: list = []
    results = executor.execute_workflow(
        workflow, mode="run", step_logger=lambda *args: logged.append(args)
    )
    assert len(results) == 2
    assert results[0]["steps"]["nocache-step"]["status"] == "success"
    assert results[1]["steps"]["nocache-step"]["status"] == "skipped"
    skipped = [entry for entry in logged if entry[2] == "SKIPPED"]
    assert len(skipped) == 1
    assert skipped[0][1] == "nocache-step"
