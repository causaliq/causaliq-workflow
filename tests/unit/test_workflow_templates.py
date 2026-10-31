"""Unit tests for workflow template variable resolution."""

from causaliq_workflow.workflow import WorkflowExecutor


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
