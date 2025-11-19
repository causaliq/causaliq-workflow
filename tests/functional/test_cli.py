"""
Functional tests for the CLI.

These tests use Click's CliRunner to invoke the CLI commands

monkeypatch only works on curent process, so CLI runner must be invoked
using standalone=False
"""

# Import test_action to register it for CLI tests
import test_action  # noqa: F401
from click.testing import CliRunner
from pytest import fixture

from causaliq_workflow.cli import cli

CLI_BASE_DIR = "tests/data/functional/cli"


# Provide a CLI runner for testing
@fixture
def cli_runner():
    return CliRunner()


# Test missing required WORKFLOW_FILE argument
def test_cli_missing_workflow_argument():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code != 0  # Should fail
    assert "Missing argument" in result.output or "Usage:" in result.output


# Test help is shown when no arguments provided
def test_cli_no_args_shows_usage():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code != 0
    assert "WORKFLOW_FILE" in result.output  # Should show usage info


# Test with valid workflow file
def test_cli_shows_action_success(cli_runner):
    # Test that CLI shows error when action is not available in CLI context
    # (test_action is imported in test context but not in CLI runner context)
    workflow_file = "tests/data/functional/test_cli_workflow.yml"

    result = cli_runner.invoke(cli, [workflow_file, "--log-level=summary"])
    assert (
        result.exit_code == 0
    )  # Actually succeeds because test_action is available
    assert "[causaliq-workflow] LOADING" in result.output


# Test basic CLI validation with empty workflow (should fail validation)
def test_cli_validation_error(cli_runner):
    # Test with workflow file that has validation error
    workflow_file = "tests/data/functional/invalid_cli_test.yml"

    result = cli_runner.invoke(cli, [workflow_file, "--log-level=summary"])
    assert result.exit_code == 1  # Should fail validation
    assert "[causaliq-workflow] LOADING" in result.output
    assert "[causaliq-workflow] ERROR" in result.output


# Test successful execution with empty results
def test_cli_successful_execution_empty_results(cli_runner, monkeypatch):
    # Mock WorkflowExecutor methods - empty results
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}  # Valid workflow dict

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None
    ):
        if mode == "validate":
            return []  # Validation succeeds
        return []  # Empty results

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )
    monkeypatch.setattr(
        WorkflowExecutor, "execute_workflow", mock_execute_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(cli, [workflow_file, "--log-level=summary"])
    assert result.exit_code == 0
    assert "[causaliq-workflow] LOADING" in result.output
    assert "[causaliq-workflow] VALIDATING" in result.output
    assert (
        "[causaliq-workflow] VALIDATED workflow successfully" in result.output
    )
    assert "[causaliq-workflow] EXECUTING" in result.output
    assert (
        "[causaliq-workflow] COMPLETED workflow with 0 jobs" in result.output
    )


# Test successful execution with log level none
def test_cli_successful_execution_log_none(cli_runner, monkeypatch):
    # Mock WorkflowExecutor methods - results with log_level none
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}  # Valid workflow dict

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None
    ):
        if mode == "validate":
            return []  # Validation succeeds
        return [
            {"status": "completed", "steps": {"step1": {"status": "success"}}}
        ]

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )
    monkeypatch.setattr(
        WorkflowExecutor, "execute_workflow", mock_execute_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(cli, [workflow_file, "--log-level=none"])
    assert result.exit_code == 0
    # Should have no output when log_level is none
    assert result.output == ""


# Test KeyboardInterrupt handling
def test_cli_keyboard_interrupt(cli_runner, monkeypatch):
    # Mock WorkflowExecutor methods to raise KeyboardInterrupt
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}  # Valid workflow dict

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None
    ):
        if mode == "validate":
            return []  # Validation succeeds
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )
    monkeypatch.setattr(
        WorkflowExecutor, "execute_workflow", mock_execute_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(cli, [workflow_file, "--log-level=summary"])
    assert result.exit_code == 130
    assert "[causaliq-workflow] LOADING" in result.output
    assert "[causaliq-workflow] VALIDATING" in result.output
    assert (
        "[causaliq-workflow] VALIDATED workflow successfully" in result.output
    )
    assert "[causaliq-workflow] EXECUTING" in result.output
    assert (
        "[causaliq-workflow] ERROR Workflow execution interrupted by user"
        in result.output
    )


# Test ImportError handling at module level
def test_cli_import_error(cli_runner, monkeypatch):
    # Mock WorkflowExecutor class creation to raise ImportError
    from causaliq_workflow import workflow

    def mock_workflow_executor(*args, **kwargs):
        raise ImportError("Missing module 'some_required_package'")

    monkeypatch.setattr(workflow, "WorkflowExecutor", mock_workflow_executor)

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(cli, [workflow_file, "--log-level=summary"])
    assert result.exit_code == 1
    assert (
        "[causaliq-workflow] ERROR Missing required dependencies"
        in result.output
    )


# Test successful workflow execution with results reporting
def test_cli_successful_execution(cli_runner, monkeypatch):
    # Mock WorkflowExecutor methods - everything succeeds
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}  # Valid workflow dict

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None
    ):
        if mode == "validate":
            return []  # Validation succeeds
        # Return mock results for successful execution
        return [
            {
                "status": "completed",
                "steps": {
                    "step1": {"status": "success", "result": "data"},
                    "step2": {"status": "success", "result": "more data"},
                },
            },
            {
                "status": "completed",
                "steps": {
                    "step3": {"status": "success", "result": "final data"}
                },
            },
        ]

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )
    monkeypatch.setattr(
        WorkflowExecutor, "execute_workflow", mock_execute_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(cli, [workflow_file, "--log-level=all"])
    assert result.exit_code == 0
    assert "[causaliq-workflow] LOADING" in result.output
    assert "[causaliq-workflow] VALIDATING" in result.output
    assert (
        "[causaliq-workflow] VALIDATED workflow successfully" in result.output
    )
    assert "[causaliq-workflow] EXECUTING" in result.output
    assert (
        "[causaliq-workflow] COMPLETED workflow with 2 job(s) (3 steps)"
        in result.output
    )
    assert "[causaliq-workflow] JOB 1 completed 2 step(s)" in result.output
    assert "[causaliq-workflow] JOB 2 completed 1 step(s)" in result.output
    # Note: Step messages now come from actions, not CLI framework


# Test workflow execution failure
def test_cli_execution_failure(cli_runner, monkeypatch):
    # Mock WorkflowExecutor methods - parse_workflow succeeds,
    # validation succeeds, execution fails
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}  # Valid workflow dict

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None
    ):
        if mode == "validate":
            return []  # Validation succeeds
        raise RuntimeError("Execution failed: action not found")

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )
    monkeypatch.setattr(
        WorkflowExecutor, "execute_workflow", mock_execute_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(cli, [workflow_file, "--log-level=summary"])
    assert result.exit_code == 1
    assert "[causaliq-workflow] LOADING" in result.output
    assert "[causaliq-workflow] VALIDATING" in result.output
    assert (
        "[causaliq-workflow] VALIDATED workflow successfully" in result.output
    )
    assert "[causaliq-workflow] EXECUTING" in result.output
    assert (
        "[causaliq-workflow] ERROR Workflow execution failed" in result.output
    )


# Test workflow validation failure
def test_cli_validation_failure(cli_runner, monkeypatch):
    # Mock WorkflowExecutor methods - parse_workflow succeeds
    # but execute_workflow fails
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}  # Valid workflow dict

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None
    ):
        if mode == "validate":
            raise ValueError("Validation error: missing required field")
        return []

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )
    monkeypatch.setattr(
        WorkflowExecutor, "execute_workflow", mock_execute_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(cli, [workflow_file, "--log-level=summary"])
    assert result.exit_code == 1
    assert "[causaliq-workflow] LOADING" in result.output
    assert "[causaliq-workflow] VALIDATING" in result.output
    assert (
        "[causaliq-workflow] ERROR Workflow validation failed" in result.output
    )


# Test workflow parsing error that is not YAML-related
def test_cli_general_parsing_error(cli_runner, monkeypatch):
    # Mock WorkflowExecutor.parse_workflow to raise a general exception
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        raise ValueError("Some general error message")

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(cli, [workflow_file, "--log-level=summary"])
    assert result.exit_code == 1
    assert "[causaliq-workflow] LOADING" in result.output
    assert (
        "[causaliq-workflow] ERROR Failed to parse workflow" in result.output
    )


# Test workflow file not found error handling (actual FileNotFoundError)
def test_cli_file_not_found_direct_error(cli_runner, monkeypatch):
    # Mock WorkflowExecutor.parse_workflow to raise FileNotFoundError directly
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        raise FileNotFoundError(f"No such file or directory: '{filepath}'")

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(cli, [workflow_file, "--log-level=summary"])
    assert result.exit_code == 1
    assert "[causaliq-workflow] LOADING" in result.output
    assert "[causaliq-workflow] ERROR Workflow file not found" in result.output


# Test workflow file not found error handling
def test_cli_file_not_found_error(cli_runner):
    # Test with non-existent workflow file
    workflow_file = "tests/data/functional/nonexistent.yml"

    result = cli_runner.invoke(cli, [workflow_file, "--log-level=summary"])
    assert result.exit_code == 1
    assert "[causaliq-workflow] LOADING" in result.output
    assert (
        "[causaliq-workflow] ERROR Invalid YAML in workflow file"
        in result.output
    )


# Test that invoking script directly will run the CLI
def test_main_function(monkeypatch):
    called = {}

    def fake_cli(*args, **kwargs):
        called["cli"] = args != kwargs

    monkeypatch.setattr("causaliq_workflow.cli.cli", fake_cli)
    from causaliq_workflow.cli import main

    main()
    assert called.get("cli") is True


# Test step logger coverage with real workflow execution
def test_cli_step_logger_coverage(cli_runner, tmp_path):
    # Create a dummy data file for the test
    data_file = tmp_path / "test_data.csv"
    data_file.write_text("col1,col2\nvalue1,value2\n")

    # Create an output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Create a minimal workflow file that uses test_action (already imported)
    # Use POSIX paths to avoid YAML escaping issues
    data_path_posix = str(data_file).replace("\\", "/")
    output_dir_posix = str(output_dir).replace("\\", "/")

    workflow_content = f"""description: "Test workflow for step logger"
id: "test-step-logger"

steps:
  - name: "Test Step"
    uses: "test_action"
    with:
      data_path: "{data_path_posix}"
      output_dir: "{output_dir_posix}"
"""

    workflow_file = tmp_path / "test_workflow.yml"
    workflow_file.write_text(workflow_content)

    # Run with log-level=all to trigger step logger (lines 96-97)
    result = cli_runner.invoke(cli, [str(workflow_file), "--log-level=all"])
    assert result.exit_code == 0

    # Verify step logger output is present (this exercises lines 96-97)
    assert "[test-action] STEP EXECUTING Test Step" in result.output
    assert (
        "[test-action] STEP " in result.output
    )  # Should have step completion too
