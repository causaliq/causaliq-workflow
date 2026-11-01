"""Functional tests for prompt workflow output."""

from pathlib import Path

import test_action  # noqa: F401
from click.testing import CliRunner
from pytest import fixture
from pytest_mock import MockerFixture

from causaliq_workflow.cli import cli


@fixture
def cli_runner() -> CliRunner:
    """Pytest fixture for CLI runner."""
    return CliRunner()


def _as_posix(path: Path) -> str:
    """Return a path with forward slashes for YAML double quotes."""
    return str(path).replace("\\", "/")


def _write_workflow(tmp_path: Path) -> str:
    """Write a single-step workflow that runs the test action."""
    data_file = tmp_path / "test_data.csv"
    data_file.write_text("col1,col2\nvalue1,value2\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    workflow_file = tmp_path / "workflow.yml"
    workflow_file.write_text(
        "steps:\n"
        '  - name: "Test Step"\n'
        '    uses: "test_action"\n'
        "    with:\n"
        '      action: "run"\n'
        f'      data_path: "{_as_posix(data_file)}"\n'
        f'      output_dir: "{_as_posix(output_dir)}"\n',
        encoding="utf-8",
    )
    return str(workflow_file)


# An action's own progress output precedes the step completion line.
def test_action_progress_precedes_completion(
    cli_runner: CliRunner, tmp_path: Path, mocker: MockerFixture
) -> None:
    from causaliq_workflow.workflow import step_runner

    real_execute = step_runner.execute_with_provenance

    def printing_execute(*args: object, **kwargs: object) -> object:
        print("action-progress")
        return real_execute(*args, **kwargs)  # type: ignore[arg-type]

    mocker.patch.object(
        step_runner, "execute_with_provenance", printing_execute
    )
    workflow_file = _write_workflow(tmp_path)

    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--mode=run", "--log-depth=2"]
    )

    assert result.exit_code == 0
    assert result.output.index("action-progress") < result.output.index(
        "EXECUTED"
    )


# Executed steps report a start line and their elapsed duration.
def test_run_reports_running_and_elapsed(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    workflow_file = _write_workflow(tmp_path)

    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--mode=run", "--log-depth=2"]
    )

    assert result.exit_code == 0
    assert "[run] RUNNING Test Step" in result.output
    assert "[run] EXECUTED Test Step (" in result.output


# The default log depth reports top-level steps.
def test_default_log_depth_reports_steps(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    workflow_file = _write_workflow(tmp_path)

    result = cli_runner.invoke(cli, ["run", workflow_file, "--mode=run"])

    assert result.exit_code == 0
    assert "[run] RUNNING Test Step" in result.output
    assert "[run] EXECUTED Test Step (" in result.output


# Depth zero still emits nothing at all.
def test_log_depth_zero_emits_nothing(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    workflow_file = _write_workflow(tmp_path)

    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--mode=run", "--log-depth=0"]
    )

    assert result.exit_code == 0
    assert result.output.strip() == ""


# Every emitted line is flushed as soon as it is written.
def test_each_line_is_flushed(
    cli_runner: CliRunner, tmp_path: Path, mocker: MockerFixture
) -> None:
    flush = mocker.patch("causaliq_workflow.terminal.flush_terminal")
    workflow_file = _write_workflow(tmp_path)

    cli_runner.invoke(cli, ["run", workflow_file, "--mode=run"])

    # LOADING, EXECUTING, RUNNING, EXECUTED and COMPLETED.
    assert flush.call_count >= 5
