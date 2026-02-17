"""Unit tests for CLI."""

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
    assert "export_cache" in result.output
    assert "import_cache" in result.output


# Test run subcommand help.
def test_cli_run_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "Usage: causaliq-workflow run" in result.output
    assert "WORKFLOW_FILE" in result.output
    assert "--mode" in result.output
    assert "--log-level" in result.output


# Test export_cache subcommand help.
def test_cli_export_cache_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["export_cache", "--help"])
    assert result.exit_code == 0
    assert "--cache" in result.output
    assert "--output" in result.output
