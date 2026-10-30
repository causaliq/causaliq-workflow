"""Unit tests for CLI."""

import pytest
from click.testing import CliRunner
from pytest import fixture

from causaliq_workflow.cli import cli


@fixture
def runner() -> CliRunner:
    """Pytest fixture for CLI runner."""
    return CliRunner()


# Test version option prints correctly.
def test_cli_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()


# Test help shows group commands.
def test_cli_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    # Click usage formatting varies by version; assert stable semantics.
    assert "Usage: causaliq-workflow" in result.output
    assert "[OPTIONS]" in result.output
    assert "run" in result.output
    assert "export-cache" in result.output
    assert "import-cache" in result.output


# Test run subcommand help.
def test_cli_run_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "Usage: causaliq-workflow run" in result.output
    assert "WORKFLOW_FILE" in result.output
    assert "--mode" in result.output
    assert "--log-depth" in result.output


# Test export-cache subcommand help.
def test_cli_export_cache_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["export-cache", "--help"])
    assert result.exit_code == 0
    assert "--input" in result.output
    assert "--output" in result.output


# ===========================================================================
# _report_results tests
# ===========================================================================


# Test _report_results with empty results list.
def test_report_results_empty_results(capsys: "pytest.CaptureFixture") -> None:
    from causaliq_workflow.cli import _report_results

    _report_results([], {}, "run", 2)

    captured = capsys.readouterr()
    assert "COMPLETED 0 steps" in captured.out


# Test _report_results with would_execute in dry-run mode.
def test_report_results_dry_run_would_execute(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "would_execute"}}}]
    _report_results(results, {}, "dry-run", 2)

    captured = capsys.readouterr()
    assert "1 would execute" in captured.out


# Test _report_results with would_skip in dry-run mode.
def test_report_results_dry_run_would_skip(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "would_skip"}}}]
    _report_results(results, {}, "dry-run", 2)

    captured = capsys.readouterr()
    assert "1 would skip" in captured.out


# Test _report_results with skipped steps in normal mode.
def test_report_results_skipped(capsys: "pytest.CaptureFixture") -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "skipped"}}}]
    _report_results(results, {}, "run", 2)

    captured = capsys.readouterr()
    assert "1 skipped" in captured.out


# Test _report_results with forced steps in force mode.
def test_report_results_forced(capsys: "pytest.CaptureFixture") -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "success"}}}]
    _report_results(results, {}, "force", 2)

    captured = capsys.readouterr()
    assert "1 forced" in captured.out


# Test _report_results with failed steps.
def test_report_results_failed(capsys: "pytest.CaptureFixture") -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "failed"}}}]
    _report_results(results, {}, "run", 2)

    captured = capsys.readouterr()
    assert "1 failed" in captured.out


# Test _report_results with failed steps shows error messages.
def test_report_results_failed_with_errors(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [
        {
            "steps": {
                "Evaluate Step": {
                    "status": "failed",
                    "errors": [
                        "Entry {'network': 'asia'}: Reference graph not found"
                    ],
                }
            }
        }
    ]
    _report_results(results, {}, "run", 2)

    captured = capsys.readouterr()
    assert "1 failed" in captured.out
    assert "ERRORS:" in captured.out
    assert "Evaluate Step:" in captured.out
    assert "Reference graph not found" in captured.out


# Test log_step_execution callback with matrix values.
def test_log_step_execution_with_matrix_values(
    capsys: "pytest.CaptureFixture",
) -> None:
    from datetime import datetime

    import click

    log_level = "all"

    def log_step_execution(
        action_method: str,
        step_name: str,
        status: str,
        matrix_values: dict,
    ) -> None:
        """Log step execution in real-time."""
        if log_level == "all":
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if matrix_values:
                matrix_str = ", ".join(
                    f"{k}={v}" for k, v in matrix_values.items()
                )
                matrix_part = f" [{matrix_str}]"
            else:
                matrix_part = ""
            click.echo(
                f"{timestamp} [{action_method}] {status} "
                f"{step_name}{matrix_part}"
            )

    log_step_execution(
        "learn_structure",
        "My Step",
        "EXECUTED",
        {"network": "asia", "algorithm": "pc"},
    )

    captured = capsys.readouterr()
    assert "[learn_structure]" in captured.out
    assert "EXECUTED" in captured.out
    assert "My Step" in captured.out
    assert "[network=asia, algorithm=pc]" in captured.out


# Test _report_results with UPDATE step entry counts in dry-run mode.
def test_report_results_with_entry_counts(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    # Step result with entry counts (from UPDATE step dry-run)
    results = [
        {
            "steps": {
                "update-step": {
                    "status": "would_execute",
                    "would_process": 10,
                    "would_skip": 2,
                }
            }
        }
    ]
    _report_results(results, {}, "dry-run", 2)

    captured = capsys.readouterr()
    assert "1 would execute" in captured.out
    assert "10 updates" in captured.out


# Test _report_results with only entries to process (no skip).
def test_report_results_entries_to_process_only(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [
        {
            "steps": {
                "update-step": {
                    "status": "would_execute",
                    "would_process": 5,
                    "would_skip": 0,
                }
            }
        }
    ]
    _report_results(results, {}, "dry-run", 2)

    captured = capsys.readouterr()
    assert "5 updates" in captured.out


# Test _report_results UPDATE step with only skips (no process).
def test_report_results_entries_to_skip_only(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [
        {
            "steps": {
                "update-step": {
                    "status": "would_execute",
                    "would_process": 0,
                    "would_skip": 3,
                }
            }
        }
    ]
    _report_results(results, {}, "dry-run", 2)

    captured = capsys.readouterr()
    # UPDATE step with 0 would_process but 3 would_skip still
    # counts as an UPDATE step, but shows no updates in summary.
    assert "updates" not in captured.out


# Test _report_results counts updates from executed UPDATE steps.
def test_report_results_executed_update_step(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [
        {
            "steps": {
                "update-step": {
                    "status": "success",
                    "entries_updated": 3,
                }
            }
        }
    ]
    _report_results(results, {}, "run", 2)

    captured = capsys.readouterr()
    assert "1 executed" in captured.out
    assert "3 updates" in captured.out


# Test CLI runs with non-YAML exception (covers else branch).
def test_cli_run_non_yaml_exception(runner: CliRunner, monkeypatch) -> None:
    """Test that non-YAML exceptions trigger 'Failed to parse' error."""
    # Patch at the module level where it's imported
    import causaliq_workflow.workflow as workflow_module

    def mock_parse(self, filepath, mode="dry-run", **kwargs):
        raise TypeError("Unexpected type during parsing")

    monkeypatch.setattr(
        workflow_module.WorkflowExecutor,
        "parse_workflow",
        mock_parse,
    )

    # Use mix_stderr=False to help coverage tracking
    result = runner.invoke(
        cli,
        ["run", "tests/data/functional/test_cli_workflow.yml"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, f"Output: {result.output}"
    assert "Failed to parse workflow" in result.output
    assert "Unexpected type during parsing" in result.output


# Test CLI runs with YAML exception (covers yaml branch).
def test_cli_run_yaml_exception(runner: CliRunner, monkeypatch) -> None:
    """Test that YAML exceptions trigger 'Invalid YAML' error."""
    import causaliq_workflow.workflow as workflow_module

    def mock_parse(self, filepath, mode="dry-run", **kwargs):
        raise Exception("YAML parsing error: invalid syntax")

    monkeypatch.setattr(
        workflow_module.WorkflowExecutor,
        "parse_workflow",
        mock_parse,
    )

    result = runner.invoke(
        cli,
        ["run", "tests/data/functional/test_cli_workflow.yml"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, f"Output: {result.output}"
    assert "Invalid YAML in workflow file" in result.output


# Test _format_entry_counts is empty when both counts are zero.
def test_format_entry_counts_zero() -> None:
    from causaliq_workflow.cli import _format_entry_counts

    assert _format_entry_counts(0, 0) == ""


# Test CLI parameters are parsed with YAML types.
def test_parse_cli_parameters_types() -> None:
    from causaliq_workflow.cli import _parse_cli_parameters

    parameters = _parse_cli_parameters(
        ("sample_size=1000", "alpha=0.05", "name=asia", "flag=true")
    )
    assert parameters == {
        "sample_size": 1000,
        "alpha": 0.05,
        "name": "asia",
        "flag": True,
    }


# Test YAML 1.1 type spellings are kept as text.
def test_parse_cli_parameters_keeps_yaml11_text() -> None:
    from causaliq_workflow.cli import _parse_cli_parameters

    parameters = _parse_cli_parameters(
        ("name=no", "identifier=01", "day=2020-01-01")
    )
    assert parameters == {
        "name": "no",
        "identifier": "01",
        "day": "2020-01-01",
    }


# Test a list value is parsed for a matrix override.
def test_parse_cli_parameters_list_value() -> None:
    from causaliq_workflow.cli import _parse_cli_parameters

    parameters = _parse_cli_parameters(("algorithm=[pc, ges]",))
    assert parameters == {"algorithm": ["pc", "ges"]}


# Test an empty value is parsed as null.
def test_parse_cli_parameters_empty_value() -> None:
    from causaliq_workflow.cli import _parse_cli_parameters

    assert _parse_cli_parameters(("seed=",)) == {"seed": None}


# Test a parameter without a value is rejected.
def test_parse_cli_parameters_requires_value() -> None:
    import click
    import pytest

    from causaliq_workflow.cli import _parse_cli_parameters

    with pytest.raises(click.BadParameter):
        _parse_cli_parameters(("sample_size",))


# Test an invalid parameter name is rejected.
def test_parse_cli_parameters_rejects_bad_name() -> None:
    import click
    import pytest

    from causaliq_workflow.cli import _parse_cli_parameters

    with pytest.raises(click.BadParameter):
        _parse_cli_parameters(("2bad=1",))


# Test a duplicate parameter name is rejected.
def test_parse_cli_parameters_rejects_duplicate() -> None:
    import click
    import pytest

    from causaliq_workflow.cli import _parse_cli_parameters

    with pytest.raises(click.BadParameter):
        _parse_cli_parameters(("x=1", "x=2"))


# Test a parameter value that is not valid YAML falls back to a string.
def test_parse_cli_parameters_falls_back_to_string() -> None:
    from causaliq_workflow.cli import _parse_cli_parameters

    parameters = _parse_cli_parameters(("pattern=[unclosed",))
    assert parameters == {"pattern": "[unclosed"}


# Test a mapping value is rejected.
def test_parse_cli_parameters_rejects_mapping() -> None:
    import click
    import pytest

    from causaliq_workflow.cli import _parse_cli_parameters

    with pytest.raises(click.BadParameter):
        _parse_cli_parameters(("x={a: 1}",))


# Test the run help lists the --param option.
def test_cli_run_help_lists_param(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "--param" in result.output


# Test an invalid --param value exits with a usage error.
def test_cli_run_rejects_invalid_param(runner: CliRunner) -> None:
    result = runner.invoke(
        cli,
        ["run", "tests/data/functional/test_cli_workflow.yml", "-p", "x"],
    )
    assert result.exit_code == 2
    assert "NAME=VALUE" in result.output


# ===========================================================================
# Log depth tests
# ===========================================================================


# Depth 1 reports the run summary.
def test_report_results_summary_at_depth_one(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "success"}}}]
    _report_results(results, {}, "run", 1)

    assert "COMPLETED 1 steps: 1 executed" in capsys.readouterr().out


# Depth 0 suppresses the run summary.
def test_report_results_silent_at_depth_zero(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "success"}}}]
    _report_results(results, {}, "run", 0)

    assert capsys.readouterr().out == ""


# Depth 0 suppresses CLI progress messages.
def test_log_cli_message_silent_at_depth_zero(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _log_cli_message

    _log_cli_message(0, "LOADING workflow")

    assert capsys.readouterr().out == ""


# Errors include the matrix values that identify the failing entry.
def test_report_results_error_includes_matrix(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [
        {
            "job": {"network": "asia"},
            "steps": {"Learn": {"status": "failed"}},
        }
    ]
    _report_results(results, {}, "run", 1)

    assert "Learn [network=asia]: failed" in capsys.readouterr().out


# The error list stops at the configured maximum.
def test_report_results_caps_error_list(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    steps = {
        f"step{i}": {"status": "failed", "errors": [f"error {i}"]}
        for i in range(12)
    }
    _report_results([{"steps": steps}], {}, "run", 1)

    out = capsys.readouterr().out
    assert out.count("error ") == 10
    assert "... and 2 more errors" in out


# Depth 2 reports the top-level steps only.
def test_make_step_logger_reports_top_level_steps(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _make_step_logger

    logger = _make_step_logger(2)
    logger("evaluate", "Top step", "EXECUTED", {}, depth=0)
    logger("evaluate", "Child step", "EXECUTED", {}, depth=1)

    out = capsys.readouterr().out
    assert "Top step" in out
    assert "Child step" not in out


# Depth 3 indents first-level sub-workflow steps.
def test_make_step_logger_indents_child_steps(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _make_step_logger

    _make_step_logger(3)("evaluate", "Child step", "EXECUTED", {}, depth=1)

    out = capsys.readouterr().out
    assert "  [evaluate] EXECUTED Child step" in out


# A call completion event renders its cumulative counts.
def test_make_step_logger_renders_call_completion(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _make_step_logger

    _make_step_logger(2)(
        "./child.yml",
        "Call child",
        "COMPLETED",
        {},
        depth=0,
        detail="2 steps: 2 skipped",
    )

    out = capsys.readouterr().out
    assert "[./child.yml] COMPLETED Call child (2 steps: 2 skipped)" in out
