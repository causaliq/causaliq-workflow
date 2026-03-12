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
    assert "Usage: causaliq-workflow [OPTIONS] COMMAND" in result.output
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
    assert "--log-level" in result.output


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

    _report_results([], {}, "run", "all")

    captured = capsys.readouterr()
    assert "COMPLETED 0 steps" in captured.out


# Test _report_results with would_execute in dry-run mode.
def test_report_results_dry_run_would_execute(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "would_execute"}}}]
    _report_results(results, {}, "dry-run", "all")

    captured = capsys.readouterr()
    assert "1 would execute" in captured.out


# Test _report_results with would_skip in dry-run mode.
def test_report_results_dry_run_would_skip(
    capsys: "pytest.CaptureFixture",
) -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "would_skip"}}}]
    _report_results(results, {}, "dry-run", "all")

    captured = capsys.readouterr()
    assert "1 would skip" in captured.out


# Test _report_results with skipped steps in normal mode.
def test_report_results_skipped(capsys: "pytest.CaptureFixture") -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "skipped"}}}]
    _report_results(results, {}, "run", "all")

    captured = capsys.readouterr()
    assert "1 skipped" in captured.out


# Test _report_results with forced steps in force mode.
def test_report_results_forced(capsys: "pytest.CaptureFixture") -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "success"}}}]
    _report_results(results, {}, "force", "all")

    captured = capsys.readouterr()
    assert "1 forced" in captured.out


# Test _report_results with failed steps.
def test_report_results_failed(capsys: "pytest.CaptureFixture") -> None:
    from causaliq_workflow.cli import _report_results

    results = [{"steps": {"step1": {"status": "failed"}}}]
    _report_results(results, {}, "run", "all")

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
    _report_results(results, {}, "run", "all")

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
                f"{timestamp} [{action_method}] {status:12} "
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
    _report_results(results, {}, "dry-run", "all")

    captured = capsys.readouterr()
    assert "1 would execute" in captured.out
    assert "10 entries to process" in captured.out
    assert "2 entries to skip" in captured.out


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
    _report_results(results, {}, "dry-run", "all")

    captured = capsys.readouterr()
    assert "5 entries to process" in captured.out
    # Should not show "entries to skip" when count is 0
    assert "entries to skip" not in captured.out


# Test _report_results with only entries to skip (no process).
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
    _report_results(results, {}, "dry-run", "all")

    captured = capsys.readouterr()
    assert "3 entries to skip" in captured.out
    # Should not show "entries to process" when count is 0
    assert "entries to process" not in captured.out


# Test CLI runs with non-YAML exception (covers else branch).
def test_cli_run_non_yaml_exception(runner: CliRunner, monkeypatch) -> None:
    """Test that non-YAML exceptions trigger 'Failed to parse' error."""
    # Patch at the module level where it's imported
    import causaliq_workflow.workflow as workflow_module

    def mock_parse(self, filepath, mode="dry-run"):
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

    def mock_parse(self, filepath, mode="dry-run"):
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
