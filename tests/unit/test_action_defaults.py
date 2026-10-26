"""Unit tests for action parameter defaults in the workflow engine."""

from typing import Any, Dict

import pytest
from causaliq_core import ActionInput, ActionResult, CausalIQActionProvider

from causaliq_workflow.registry import ActionRegistry, WorkflowContext
from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor
from causaliq_workflow.workflow.validation import _null_parameter_errors


class DefaultsProvider(CausalIQActionProvider):
    """Provider declaring an enumerated default and an open default."""

    name = "defaults-provider"
    supported_actions = {"run"}
    inputs = {
        "randomise": ActionInput(
            name="randomise",
            description="Randomisation options",
            default="no-randomise",
            choices=("no-randomise", "var_best"),
        ),
        "timeout": ActionInput(
            name="timeout",
            description="Timeout in minutes",
            default=60,
        ),
    }

    def _execute(
        self, action, parameters, mode, context, logger
    ) -> ActionResult:
        """Return the effective parameters as metadata."""
        return ("success", {"parameters": parameters}, [])


class MultiProvider(CausalIQActionProvider):
    """Provider whose actions accept different parameter sets."""

    name = "multi-provider"
    supported_actions = {"first", "second"}
    inputs = {
        "alpha": ActionInput(name="alpha", description="Alpha", default="a"),
        "beta": ActionInput(name="beta", description="Beta", default="b"),
    }
    action_parameters = {"first": {"alpha"}, "second": {"beta"}}

    def _execute(
        self, action, parameters, mode, context, logger
    ) -> ActionResult:
        """Return the effective parameters as metadata."""
        return ("success", {"parameters": parameters}, [])


def _run(
    registry: ActionRegistry,
    name: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute an action and return its parameters metadata block."""
    context = WorkflowContext(mode="run", matrix={})
    result = registry.execute_action(name, inputs, context)
    return result["_action_metadata"]["parameters"]


# Test an omitted enumerated parameter takes its declared default.
def test_execute_injects_enumerated_default() -> None:
    registry = ActionRegistry()
    registry._actions["defaults-provider"] = DefaultsProvider

    parameters = _run(registry, "defaults-provider", {"action": "run"})
    assert parameters["randomise"] == "no-randomise"


# Test an omitted open-domain parameter takes its declared default.
def test_execute_injects_open_domain_default() -> None:
    registry = ActionRegistry()
    registry._actions["defaults-provider"] = DefaultsProvider

    parameters = _run(registry, "defaults-provider", {"action": "run"})
    assert parameters["timeout"] == 60


# Test a supplied value wins over the declared default.
def test_execute_keeps_supplied_value() -> None:
    registry = ActionRegistry()
    registry._actions["defaults-provider"] = DefaultsProvider

    parameters = _run(
        registry,
        "defaults-provider",
        {"action": "run", "randomise": "var_best"},
    )
    assert parameters["randomise"] == "var_best"


# Test an explicit null marks not-applicable and receives no default.
def test_execute_does_not_default_null_value() -> None:
    registry = ActionRegistry()
    registry._actions["defaults-provider"] = DefaultsProvider

    parameters = _run(
        registry, "defaults-provider", {"action": "run", "timeout": None}
    )
    assert "timeout" not in parameters


# Test validation accepts an omitted parameter that has a default.
def test_validate_accepts_missing_defaulted_parameter() -> None:
    registry = ActionRegistry()
    registry._actions["defaults-provider"] = DefaultsProvider

    registry.validate_action_parameters("defaults-provider", {"action": "run"})


# Test defaults are limited to the parameters an action declares.
def test_execute_limits_defaults_to_action_parameters() -> None:
    registry = ActionRegistry()
    registry._actions["multi-provider"] = MultiProvider

    parameters = _run(registry, "multi-provider", {"action": "first"})
    assert parameters == {"alpha": "a"}


# Test a literal null parameter is rejected by workflow validation.
def test_validation_rejects_literal_null_parameter() -> None:
    executor = WorkflowExecutor()
    executor.action_registry._actions["defaults-provider"] = DefaultsProvider
    workflow = {
        "matrix": {"network": ["asia"]},
        "steps": [
            {
                "name": "learn",
                "uses": "defaults-provider",
                "with": {"action": "run", "timeout": None},
            }
        ],
    }

    with pytest.raises(WorkflowExecutionError, match="omit the parameter"):
        executor._validate_workflow_actions(workflow, "dry-run")


# Test the null error names the step and the parameter.
def test_null_error_names_step_and_parameter() -> None:
    workflow = {
        "steps": [
            {
                "name": "learn",
                "uses": "defaults-provider",
                "with": {"action": "run", "timeout": None},
            }
        ]
    }

    errors = _null_parameter_errors(workflow)
    assert errors == [
        "Step 'learn': parameter 'timeout' is null; omit the parameter "
        "instead of writing null"
    ]


# Test steps without a with block are ignored by the null check.
def test_null_check_ignores_step_without_with() -> None:
    workflow = {"steps": [{"name": "empty", "run": "echo hi"}]}
    assert _null_parameter_errors(workflow) == []


# Test a template value is not rejected because it resolves at run time.
def test_null_check_ignores_template_value() -> None:
    workflow = {
        "steps": [
            {
                "name": "wildcard",
                "uses": "defaults-provider",
                "with": {"action": "run", "timeout": "{{timeout}}"},
            }
        ]
    }
    assert _null_parameter_errors(workflow) == []
