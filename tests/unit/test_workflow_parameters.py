"""Unit tests for workflow parameter binding."""

from pathlib import Path
from typing import Any, Dict

import pytest
from causaliq_core import ActionPattern, CausalIQActionProvider

from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor
from causaliq_workflow.workflow.matrix import _bind_parameters
from causaliq_workflow.workflow.parameters import (
    _call_parameters_vary,
    _missing_required_errors,
    _parameter_matrix_clash_errors,
    _parameter_names,
    _single_token,
    _unknown_parameter_errors,
)

_CHILD: Dict[str, Any] = {
    "sample_size": 1000,
    "seed": None,
    "matrix": {"variant": ["one", "two"]},
    "steps": [
        {"name": "record", "with": {"output": "{{sample_size}}.db"}},
    ],
}


# A scalar parameter replaces a matrix dimension.
def test_bind_parameters_overrides_matrix_scalar() -> None:
    bound, variables = _bind_parameters(_CHILD, {"variant": "two"})
    assert bound["matrix"] == {"variant": ["two"]}
    assert variables == {}


# A list parameter replaces a matrix dimension with its own values.
def test_bind_parameters_uses_list_override() -> None:
    bound, _ = _bind_parameters(_CHILD, {"variant": ["two", "three"]})
    assert bound["matrix"] == {"variant": ["two", "three"]}


# Binding never modifies the workflow it was given.
def test_bind_parameters_leaves_input_untouched() -> None:
    _bind_parameters(_CHILD, {"variant": "two"})
    assert _CHILD["matrix"] == {"variant": ["one", "two"]}


# Parameters that are not dimensions bind as template variables.
def test_bind_parameters_splits_variables() -> None:
    _, variables = _bind_parameters(_CHILD, {"seed": 7})
    assert variables == {"seed": 7}


# Without overrides the original workflow object is returned.
def test_bind_parameters_without_overrides_returns_input() -> None:
    bound, variables = _bind_parameters({"steps": []}, {"x": 1})
    assert bound == {"steps": []}
    assert variables == {"x": 1}


# Accepted names cover declared parameters, matrix and step tokens.
def test_parameter_names_include_declared_matrix_and_tokens() -> None:
    names = _parameter_names(_CHILD)
    assert names == {"sample_size", "seed", "variant"}


# An unused parameter is reported with the accepted names.
def test_unknown_parameter_errors_reports_unused_name() -> None:
    errors = _unknown_parameter_errors({"labl": 1}, _CHILD)
    assert len(errors) == 1
    assert "Parameter 'labl' is not used" in errors[0]
    assert "Accepted: ['sample_size', 'seed', 'variant']" in errors[0]


# A labelled workflow is named in the error message.
def test_unknown_parameter_errors_uses_workflow_label() -> None:
    errors = _unknown_parameter_errors({"labl": 1}, _CHILD, "child.yml")
    assert "not used by workflow 'child.yml'" in errors[0]


# A null default declares a required parameter.
def test_missing_required_errors_reports_null_default() -> None:
    errors = _missing_required_errors(_CHILD, {})
    assert errors == [
        "Required workflow parameter(s) not provided: ['seed']. "
        "Provide them with 'with:' in the calling workflow or --param."
    ]


# Supplying a required parameter clears the error.
def test_missing_required_errors_accepts_supplied() -> None:
    assert _missing_required_errors(_CHILD, {"seed": 1}) == []


# A name may not be both a parameter and a matrix variable.
def test_parameter_matrix_clash_errors() -> None:
    workflow = {"alpha": 0.05, "matrix": {"alpha": [0.01]}, "steps": []}
    errors = _parameter_matrix_clash_errors(workflow)
    assert errors == [
        "Workflow key 'alpha' is declared as both a parameter and a "
        "matrix variable"
    ]


# Template validation rejects a name declared twice.
def test_validate_template_variables_rejects_clash(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "alpha": 0.05,
        "matrix": {"alpha": [0.01]},
        "steps": [
            {
                "name": "Test Step",
                "uses": "mock_workflow_action",
                "with": {"action": "test", "input": "{{alpha}}.csv"},
            }
        ],
    }
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor._validate_template_variables(workflow)
    assert "declared as both a parameter and a matrix variable" in str(
        exc_info.value
    )


# A call whose parameters reference a matrix variable varies per job.
@pytest.mark.parametrize(
    ("step", "matrix", "expected"),
    [
        ({"uses": "./c.yml"}, {"a": [1, 2]}, False),
        ({"uses": "./c.yml", "with": {"a": "{{a}}"}}, {"a": [1, 2]}, True),
        ({"uses": "./c.yml", "with": {"a": "x"}}, {"a": [1, 2]}, False),
        ({"uses": "./c.yml", "with": {"b": "{{b}}"}}, {"a": [1]}, False),
        ({"uses": "./c.yml", "with": {"a": "{{a}}"}}, {}, False),
    ],
)
def test_call_parameters_vary(
    step: Dict[str, Any], matrix: Dict[str, Any], expected: bool
) -> None:
    assert _call_parameters_vary(step, matrix) is expected


# A whole-value token keeps a list value.
def test_substitute_variables_keeps_list(executor: WorkflowExecutor) -> None:
    resolved = executor._resolve_template_variables(
        {"randomise": "{{randomise}}"}, {"randomise": ["var_best"]}
    )
    assert resolved["randomise"] == ["var_best"]


# A whole-value token keeps numeric, boolean and null values.
@pytest.mark.parametrize("value", [1000, 0.05, True, None])
def test_substitute_variables_keeps_scalar_types(
    executor: WorkflowExecutor, value: Any
) -> None:
    assert executor._substitute_variables("{{value}}", {"value": value}) == (
        value
    )


# Text around a token is still substituted as text.
def test_substitute_variables_mixes_text(executor: WorkflowExecutor) -> None:
    resolved = executor._resolve_template_variables(
        {"input": "data/{{size}}.csv"}, {"size": 1000}
    )
    assert resolved["input"] == "data/1000.csv"


# A string value stays textual.
def test_substitute_variables_keeps_strings_textual(
    executor: WorkflowExecutor,
) -> None:
    assert executor._substitute_variables("{{name}}", {"name": "asia"}) == (
        "asia"
    )


_SEEN: list = []


class _RecordingProvider(CausalIQActionProvider):
    """Provider that records the parameters it receives."""

    name = "recording-provider"
    version = "1.0.0"
    supported_actions = {"produce"}
    action_patterns = {"produce": ActionPattern.CREATE}

    def _execute(
        self,
        action: str,
        parameters: Dict[str, Any],
        mode: str,
        context: Any,
        logger: Any,
    ) -> Any:
        """Record the received parameters."""
        _SEEN.append(dict(parameters))
        return ("success", {}, [])


# A called workflow's action receives a list parameter natively.
def test_called_workflow_receives_list_parameter(tmp_path: Path) -> None:
    child = tmp_path / "child.yml"
    child.write_text(
        "matrix:\n"
        "  variant: [one]\n"
        "steps:\n"
        "  - name: Produce\n"
        "    uses: recording-provider\n"
        "    with:\n"
        "      action: produce\n"
        '      randomise: "{{randomise}}"\n'
        '      output: "{{variant}}.png"\n',
        encoding="utf-8",
    )
    parent = {
        "steps": [
            {
                "name": "Call",
                "uses": "./child.yml",
                "with": {"randomise": ["var_best"]},
            }
        ]
    }
    executor = WorkflowExecutor()
    executor.action_registry._actions["recording-provider"] = (
        _RecordingProvider
    )
    _SEEN.clear()
    results = executor.execute_workflow(
        parent, mode="run", source_path=tmp_path / "parent.yml"
    )
    assert results[0]["steps"]["Call"]["status"] == "success"
    assert _SEEN[-1]["randomise"] == ["var_best"]


# An empty list parameter also arrives as a list.
def test_called_workflow_receives_empty_list(tmp_path: Path) -> None:
    child = tmp_path / "child.yml"
    child.write_text(
        "matrix:\n"
        "  variant: [one]\n"
        "steps:\n"
        "  - name: Produce\n"
        "    uses: recording-provider\n"
        "    with:\n"
        "      action: produce\n"
        '      randomise: "{{randomise}}"\n'
        '      output: "{{variant}}.png"\n',
        encoding="utf-8",
    )
    parent = {
        "steps": [
            {
                "name": "Call",
                "uses": "./child.yml",
                "with": {"randomise": []},
            }
        ]
    }
    executor = WorkflowExecutor()
    executor.action_registry._actions["recording-provider"] = (
        _RecordingProvider
    )
    _SEEN.clear()
    executor.execute_workflow(
        parent, mode="run", source_path=tmp_path / "parent.yml"
    )
    assert _SEEN[-1]["randomise"] == []


# A parameter name is always a string identifier.
def test_is_parameter_name_rejects_non_string() -> None:
    from causaliq_workflow.workflow.parameters import _is_parameter_name

    assert _is_parameter_name(1) is False
    assert _is_parameter_name("sample_size") is True


# A single token is recognised, mixed text is not.
def test_single_token_detection() -> None:
    assert _single_token("{{sample_size}}") == "sample_size"
    assert _single_token("size-{{sample_size}}") is None
    assert _single_token(1000) is None


def _matrix_workflow() -> Dict[str, Any]:
    """Return a one-step workflow with a two-value matrix."""
    return {
        "matrix": {"dataset": ["asia", "cancer"]},
        "steps": [
            {
                "name": "Test Step",
                "uses": "mock_workflow_action",
                "with": {"action": "test", "input": "{{dataset}}.csv"},
            }
        ],
    }


# A CLI parameter replaces a root matrix dimension.
def test_execute_workflow_overrides_root_matrix(
    executor: WorkflowExecutor,
) -> None:
    results = executor.execute_workflow(
        _matrix_workflow(), mode="run", cli_params={"dataset": "asia"}
    )
    assert len(results) == 1
    step = results[0]["steps"]["Test Step"]
    assert step["parameters"]["input"] == "asia.csv"


# A declared parameter default is available to templates.
def test_execute_workflow_uses_parameter_default(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "sample_size": 1000,
        "steps": [
            {
                "name": "Test Step",
                "uses": "mock_workflow_action",
                "with": {"action": "test", "input": "{{sample_size}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(workflow, mode="run")
    assert results[0]["steps"]["Test Step"]["parameters"]["input"] == (
        "1000.csv"
    )


# A parameter overrides a declared default.
def test_execute_workflow_overrides_parameter_default(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "sample_size": 1000,
        "steps": [
            {
                "name": "Test Step",
                "uses": "mock_workflow_action",
                "with": {"action": "test", "input": "{{sample_size}}.csv"},
            }
        ],
    }
    results = executor.execute_workflow(
        workflow, mode="run", cli_params={"sample_size": 500}
    )
    assert results[0]["steps"]["Test Step"]["parameters"]["input"] == (
        "500.csv"
    )


# An unknown CLI parameter fails validation.
def test_execute_workflow_rejects_unknown_parameter(
    executor: WorkflowExecutor,
) -> None:
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.execute_workflow(
            _matrix_workflow(), mode="validate", cli_params={"nope": 1}
        )
    assert "Parameter 'nope' is not used" in str(exc_info.value)


# A required parameter with no value fails validation.
def test_execute_workflow_rejects_missing_required(
    executor: WorkflowExecutor,
) -> None:
    workflow = {
        "seed": None,
        "steps": [
            {
                "name": "Test Step",
                "uses": "mock_workflow_action",
                "with": {"action": "test", "input": "{{seed}}.csv"},
            }
        ],
    }
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.execute_workflow(workflow, mode="validate")
    assert "Required workflow parameter(s) not provided: ['seed']" in (
        str(exc_info.value)
    )


# Parsing accepts parameter names supplied by the CLI.
def test_parse_workflow_accepts_supplied_parameters(
    executor: WorkflowExecutor, tmp_path: Path
) -> None:
    path = tmp_path / "cli.yml"
    path.write_text(
        "steps:\n"
        "  - name: Test Step\n"
        "    uses: mock_workflow_action\n"
        "    with:\n"
        "      action: test\n"
        '      input: "{{sample_size}}.csv"\n',
        encoding="utf-8",
    )
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow(str(path))
    assert "sample_size" in str(exc_info.value)
    parsed = executor.parse_workflow(str(path), parameters={"sample_size": 10})
    assert parsed["steps"][0]["with"]["input"] == "{{sample_size}}.csv"
