"""Functional tests for sub-workflow log depth reporting."""

import test_action  # noqa: F401
from click.testing import CliRunner
from pytest import fixture

from causaliq_workflow.cli import cli


@fixture
def cli_runner() -> CliRunner:
    """Pytest fixture for CLI runner."""
    return CliRunner()


def _write_workflows(tmp_path):
    """Write a parent workflow that calls a child workflow."""
    data_file = tmp_path / "test_data.csv"
    data_file.write_text("col1,col2\nvalue1,value2\n")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    data_path = str(data_file).replace("\\", "/")
    output_path = str(output_dir).replace("\\", "/")
    (tmp_path / "child.yml").write_text(
        "steps:\n"
        '  - name: "Child step"\n'
        '    uses: "test_action"\n'
        "    with:\n"
        '      action: "run"\n'
        f'      data_path: "{data_path}"\n'
        f'      output_dir: "{output_path}"\n',
        encoding="utf-8",
    )
    workflow_file = tmp_path / "parent.yml"
    workflow_file.write_text(
        "steps:\n" '  - name: "Call child"\n' '    uses: "./child.yml"\n',
        encoding="utf-8",
    )
    return workflow_file


# Depth 2 reports the call boundaries but no child step messages.
def test_log_depth_two_hides_child_steps(
    cli_runner: CliRunner, tmp_path
) -> None:
    workflow_file = _write_workflows(tmp_path)

    result = cli_runner.invoke(
        cli, ["run", str(workflow_file), "--log-depth=2"]
    )

    assert result.exit_code == 0
    assert "[./child.yml] CALLING" in result.output
    assert "[./child.yml] COMPLETED" in result.output
    assert "[run] WOULD EXECUTE" not in result.output


# Depth 3 adds the child step, indented, and counts its work.
def test_log_depth_three_shows_child_steps(
    cli_runner: CliRunner, tmp_path
) -> None:
    workflow_file = _write_workflows(tmp_path)

    result = cli_runner.invoke(
        cli, ["run", str(workflow_file), "--log-depth=3"]
    )

    assert result.exit_code == 0
    assert "  [run] WOULD EXECUTE" in result.output
    assert "COMPLETED 1 steps: 1 would execute" in result.output


# Depth 0 suppresses every message.
def test_log_depth_zero_is_silent(cli_runner: CliRunner, tmp_path) -> None:
    workflow_file = _write_workflows(tmp_path)

    result = cli_runner.invoke(
        cli, ["run", str(workflow_file), "--log-depth=0"]
    )

    assert result.exit_code == 0
    assert result.output.strip() == ""


# CAUSALIQ_LOG_DEPTH supplies the default depth.
def test_log_depth_from_environment(
    cli_runner: CliRunner, tmp_path, monkeypatch
) -> None:
    workflow_file = _write_workflows(tmp_path)
    monkeypatch.setenv("CAUSALIQ_LOG_DEPTH", "0")

    result = cli_runner.invoke(cli, ["run", str(workflow_file)])

    assert result.exit_code == 0
    assert result.output.strip() == ""
