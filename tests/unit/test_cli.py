"""Unit tests for CLI"""

from click.testing import CliRunner
from pytest import fixture

from causaliq_workflow.cli import cli


@fixture
def runner():
    return CliRunner()


# Check version printed correctly
def test_cli_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()


# check help printed correctly
def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage: causaliq-workflow [OPTIONS] WORKFLOW_FILE" in result.output
    assert "Execute CausalIQ workflow files." in result.output
    assert "WORKFLOW_FILE is the path to a YAML workflow file" in result.output
    assert "--mode [dry-run|run]" in result.output
    assert "--log-level [none|summary|all]" in result.output
