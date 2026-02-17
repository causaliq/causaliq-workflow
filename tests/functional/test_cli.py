"""Functional tests for the CLI.

These tests use Click's CliRunner to invoke the CLI commands.
monkeypatch only works on current process, so CLI runner must be invoked
using standalone=False.
"""

import test_action  # noqa: F401
from click.testing import CliRunner
from pytest import fixture

from causaliq_workflow.cli import cli


@fixture
def cli_runner() -> CliRunner:
    """Pytest fixture for CLI runner."""
    return CliRunner()


# Test no subcommand shows help.
def test_cli_no_args_shows_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "run" in result.output
    assert "export_cache" in result.output
    assert "import_cache" in result.output


# Test run subcommand missing workflow argument.
def test_cli_run_missing_workflow_argument() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["run"])
    assert result.exit_code != 0
    assert "Missing argument" in result.output or "Usage:" in result.output


# Test run with valid workflow file.
def test_cli_run_shows_action_success(cli_runner: CliRunner) -> None:
    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--log-level=summary"]
    )
    assert result.exit_code == 0
    assert "[causaliq-workflow] LOADING" in result.output


# Test run with invalid workflow (validation error).
def test_cli_run_validation_error(cli_runner: CliRunner) -> None:
    workflow_file = "tests/data/functional/invalid_cli_test.yml"
    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--log-level=summary"]
    )
    assert result.exit_code == 1
    assert "[causaliq-workflow] LOADING" in result.output
    assert "[causaliq-workflow] ERROR" in result.output


# Test run successful execution with empty results.
def test_cli_run_successful_execution_empty_results(
    cli_runner: CliRunner, monkeypatch
) -> None:
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None, cache=None
    ):
        if mode == "validate":
            return []
        return []

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )
    monkeypatch.setattr(
        WorkflowExecutor, "execute_workflow", mock_execute_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--log-level=summary"]
    )
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


# Test run successful execution with log level none.
def test_cli_run_successful_execution_log_none(
    cli_runner: CliRunner, monkeypatch
) -> None:
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None, cache=None
    ):
        if mode == "validate":
            return []
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
    result = cli_runner.invoke(cli, ["run", workflow_file, "--log-level=none"])
    assert result.exit_code == 0
    assert result.output == ""


# Test run KeyboardInterrupt handling.
def test_cli_run_keyboard_interrupt(
    cli_runner: CliRunner, monkeypatch
) -> None:
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None, cache=None
    ):
        if mode == "validate":
            return []
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )
    monkeypatch.setattr(
        WorkflowExecutor, "execute_workflow", mock_execute_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--log-level=summary"]
    )
    assert result.exit_code == 130
    assert (
        "[causaliq-workflow] ERROR Workflow execution interrupted by user"
        in result.output
    )


# Test run ImportError handling at module level.
def test_cli_run_import_error(cli_runner: CliRunner, monkeypatch) -> None:
    from causaliq_workflow import workflow

    def mock_workflow_executor(*args, **kwargs):
        raise ImportError("Missing module 'some_required_package'")

    monkeypatch.setattr(workflow, "WorkflowExecutor", mock_workflow_executor)

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--log-level=summary"]
    )
    assert result.exit_code == 1
    assert (
        "[causaliq-workflow] ERROR Missing required dependencies"
        in result.output
    )


# Test run successful workflow execution with results reporting.
def test_cli_run_successful_execution(
    cli_runner: CliRunner, monkeypatch
) -> None:
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None, cache=None
    ):
        if mode == "validate":
            return []
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
    result = cli_runner.invoke(cli, ["run", workflow_file, "--log-level=all"])
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


# Test run workflow execution failure.
def test_cli_run_execution_failure(cli_runner: CliRunner, monkeypatch) -> None:
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None, cache=None
    ):
        if mode == "validate":
            return []
        raise RuntimeError("Execution failed: action not found")

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )
    monkeypatch.setattr(
        WorkflowExecutor, "execute_workflow", mock_execute_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--log-level=summary"]
    )
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


# Test run workflow validation failure.
def test_cli_run_validation_failure(
    cli_runner: CliRunner, monkeypatch
) -> None:
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        return {"jobs": []}

    def mock_execute_workflow(
        self, workflow, mode="dry-run", step_logger=None, cache=None
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
    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--log-level=summary"]
    )
    assert result.exit_code == 1
    assert "[causaliq-workflow] LOADING" in result.output
    assert "[causaliq-workflow] VALIDATING" in result.output
    assert (
        "[causaliq-workflow] ERROR Workflow validation failed" in result.output
    )


# Test run workflow parsing error that is not YAML-related.
def test_cli_run_general_parsing_error(
    cli_runner: CliRunner, monkeypatch
) -> None:
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        raise ValueError("Some general error message")

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--log-level=summary"]
    )
    assert result.exit_code == 1
    assert "[causaliq-workflow] LOADING" in result.output
    assert (
        "[causaliq-workflow] ERROR Failed to parse workflow" in result.output
    )


# Test run workflow file not found error handling.
def test_cli_run_file_not_found_direct_error(
    cli_runner: CliRunner, monkeypatch
) -> None:
    from causaliq_workflow.workflow import WorkflowExecutor

    def mock_parse_workflow(self, filepath):
        raise FileNotFoundError(f"No such file or directory: '{filepath}'")

    monkeypatch.setattr(
        WorkflowExecutor, "parse_workflow", mock_parse_workflow
    )

    workflow_file = "tests/data/functional/test_cli_workflow.yml"
    result = cli_runner.invoke(
        cli, ["run", workflow_file, "--log-level=summary"]
    )
    assert result.exit_code == 1
    assert "[causaliq-workflow] LOADING" in result.output
    assert "[causaliq-workflow] ERROR Workflow file not found" in result.output


# Test export_cache command missing required arguments.
def test_cli_export_cache_missing_args(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli, ["export_cache"])
    assert result.exit_code != 0
    assert "Missing option" in result.output or "Usage:" in result.output


# Test export_cache command with nonexistent cache file.
def test_cli_export_cache_nonexistent_cache(
    cli_runner: CliRunner, tmp_path
) -> None:
    cache_path = tmp_path / "nonexistent.db"
    output_dir = tmp_path / "output"
    result = cli_runner.invoke(
        cli,
        ["export_cache", "-c", str(cache_path), "-o", str(output_dir)],
    )
    # Click validates exists=True and returns exit code 2
    assert result.exit_code == 2
    assert "does not exist" in result.output


# =============================================================================
# Encoder-based export tests removed - replaced with provider-based export
# See tests/unit/cache/test_export.py for new export tests
# =============================================================================


# Test export_cache command success path.
def test_cli_export_cache_success(cli_runner: CliRunner, tmp_path) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "success_export.db"
    output_dir = tmp_path / "exported"

    with WorkflowCache(cache_path) as cache:
        entry = CacheEntry(metadata={"v": 1})
        entry.add_object("data", "json", '{"key": "value"}')
        cache.put({"test": "export"}, entry)

    result = cli_runner.invoke(
        cli,
        [
            "export_cache",
            "-c",
            str(cache_path),
            "-o",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0
    assert "EXPORTED 1 entries" in result.output


# Test export_cache command empty cache.
def test_cli_export_cache_empty_cache(cli_runner: CliRunner, tmp_path) -> None:
    from causaliq_workflow.cache import WorkflowCache

    cache_path = tmp_path / "empty_cache.db"
    output_dir = tmp_path / "exported"

    # Create empty cache
    with WorkflowCache(cache_path) as _:
        pass  # Just create empty cache

    result = cli_runner.invoke(
        cli,
        [
            "export_cache",
            "-c",
            str(cache_path),
            "-o",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0
    assert "No entries found in cache" in result.output


# Test CLI structure keys parsing removed - see test_export.py


# Test export_cache general Exception handling.
def test_cli_export_cache_general_exception(
    cli_runner: CliRunner, tmp_path, monkeypatch
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "exception_cache.db"
    output_dir = tmp_path / "exported"

    with WorkflowCache(cache_path) as cache:
        entry = CacheEntry(metadata={"value": 1})
        entry.add_object("data", "json", '{"v": 1}')
        cache.put({"a": "1"}, entry)

    # Patch the export method to raise RuntimeError
    def raise_runtime_error(*args, **kwargs):
        raise RuntimeError("Test runtime error")

    monkeypatch.setattr(WorkflowCache, "export", raise_runtime_error)

    result = cli_runner.invoke(
        cli,
        [
            "export_cache",
            "-c",
            str(cache_path),
            "-o",
            str(output_dir),
        ],
    )

    assert result.exit_code == 1
    assert "Export failed" in result.output


# Test export_cache KeyError from export method.
def test_cli_export_cache_keyerror_from_export(
    cli_runner: CliRunner, tmp_path, monkeypatch
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "keyerror_export.db"
    output_dir = tmp_path / "exported"

    with WorkflowCache(cache_path) as cache:
        entry = CacheEntry(metadata={"value": 1})
        entry.add_object("data", "json", '{"v": 1}')
        cache.put({"a": "1"}, entry)

    def raise_key_error(*args, **kwargs):
        raise KeyError("No encoder found")

    monkeypatch.setattr(WorkflowCache, "export", raise_key_error)

    result = cli_runner.invoke(
        cli,
        [
            "export_cache",
            "-c",
            str(cache_path),
            "-o",
            str(output_dir),
        ],
    )

    assert result.exit_code == 1
    assert "Export failed" in result.output


# Test export_cache KeyboardInterrupt handling.
def test_cli_export_cache_keyboard_interrupt(
    cli_runner: CliRunner, tmp_path, monkeypatch
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    cache_path = tmp_path / "interrupt_cache.db"
    output_dir = tmp_path / "exported"

    with WorkflowCache(cache_path) as cache:
        entry = CacheEntry(metadata={"value": 1})
        entry.add_object("data", "json", '{"v": 1}')
        cache.put({"a": "1"}, entry)

    def raise_keyboard_interrupt(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(WorkflowCache, "export", raise_keyboard_interrupt)

    result = cli_runner.invoke(
        cli,
        [
            "export_cache",
            "-c",
            str(cache_path),
            "-o",
            str(output_dir),
        ],
    )

    assert result.exit_code == 130
    assert "Export interrupted by user" in result.output


# Test export_cache ImportError handling.
def test_cli_export_cache_import_error(
    cli_runner: CliRunner, tmp_path, monkeypatch
) -> None:
    cache_path = tmp_path / "import_error.db"
    # Create a minimal file so Click's exists check passes
    cache_path.write_bytes(b"")
    output_dir = tmp_path / "exported"

    def raise_import_error(*args, **kwargs):
        raise ImportError("Missing causaliq_core")

    # Patch at the point where WorkflowCache is used
    monkeypatch.setattr(
        "causaliq_workflow.cache.WorkflowCache", raise_import_error
    )

    result = cli_runner.invoke(
        cli,
        [
            "export_cache",
            "-c",
            str(cache_path),
            "-o",
            str(output_dir),
        ],
    )

    assert result.exit_code == 1
    assert "Missing required dependencies" in result.output


# Test main function entry point.
def test_main_function(monkeypatch) -> None:
    called = {}

    def fake_cli(*args, **kwargs):
        called["cli"] = args != kwargs

    monkeypatch.setattr("causaliq_workflow.cli.cli", fake_cli)
    from causaliq_workflow.cli import main

    main()
    assert called.get("cli") is True


# Test step logger coverage with real workflow execution.
def test_cli_run_step_logger_coverage(cli_runner: CliRunner, tmp_path) -> None:
    data_file = tmp_path / "test_data.csv"
    data_file.write_text("col1,col2\nvalue1,value2\n")

    output_dir = tmp_path / "output"
    output_dir.mkdir()

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

    result = cli_runner.invoke(
        cli, ["run", str(workflow_file), "--log-level=all"]
    )
    assert result.exit_code == 0
    assert "[test-action] STEP EXECUTING Test Step" in result.output
    assert "[test-action] STEP " in result.output


# ============================================================================
# import_cache CLI tests
# ============================================================================


# Test import_cache command missing required arguments.
def test_cli_import_cache_missing_args(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli, ["import_cache"])
    assert result.exit_code != 0
    assert "Missing option" in result.output or "Usage:" in result.output


# Test import_cache command with nonexistent input path.
def test_cli_import_cache_nonexistent_input(
    cli_runner: CliRunner, tmp_path
) -> None:
    input_path = tmp_path / "nonexistent"
    cache_path = tmp_path / "cache.db"
    result = cli_runner.invoke(
        cli,
        ["import_cache", "-i", str(input_path), "-c", str(cache_path)],
    )
    # Click validates exists=True and returns exit code 2
    assert result.exit_code == 2
    assert "does not exist" in result.output


# =============================================================================
# Encoder-based import tests removed - replaced with provider-based export
# See tests/unit/cache/test_export.py for new export tests
# =============================================================================


# Test import_cache command success path.
def test_cli_import_cache_success(cli_runner: CliRunner, tmp_path) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    source_cache = tmp_path / "source.db"
    export_dir = tmp_path / "exported"
    dest_cache = tmp_path / "dest.db"

    with WorkflowCache(source_cache) as cache:
        entry = CacheEntry(metadata={"v": 1})
        entry.add_object("data", "json", '{"key": "value"}')
        cache.put({"test": "import"}, entry)
        cache.export(export_dir)

    result = cli_runner.invoke(
        cli,
        [
            "import_cache",
            "-i",
            str(export_dir),
            "-c",
            str(dest_cache),
        ],
    )
    assert result.exit_code == 0
    assert "IMPORTED 1 entries" in result.output


# Test import_cache KeyError handling.
def test_cli_import_cache_keyerror(
    cli_runner: CliRunner, tmp_path, monkeypatch
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    source_cache = tmp_path / "source.db"
    export_dir = tmp_path / "exported"
    dest_cache = tmp_path / "dest.db"

    with WorkflowCache(source_cache) as cache:
        entry = CacheEntry(metadata={"v": 1})
        entry.add_object("data", "json", '{"v": 1}')
        cache.put({"a": "1"}, entry)
        cache.export(export_dir)

    def raise_key_error(*args, **kwargs):
        raise KeyError("No encoder found")

    monkeypatch.setattr(WorkflowCache, "import_entries", raise_key_error)

    result = cli_runner.invoke(
        cli,
        [
            "import_cache",
            "-i",
            str(export_dir),
            "-c",
            str(dest_cache),
        ],
    )

    assert result.exit_code == 1
    assert "Import failed" in result.output


# Test import_cache general Exception handling.
def test_cli_import_cache_general_exception(
    cli_runner: CliRunner, tmp_path, monkeypatch
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    source_cache = tmp_path / "source.db"
    export_dir = tmp_path / "exported"
    dest_cache = tmp_path / "dest.db"

    with WorkflowCache(source_cache) as cache:
        entry = CacheEntry(metadata={"v": 1})
        entry.add_object("data", "json", '{"v": 1}')
        cache.put({"a": "1"}, entry)
        cache.export(export_dir)

    def raise_runtime_error(*args, **kwargs):
        raise RuntimeError("Test runtime error")

    monkeypatch.setattr(WorkflowCache, "import_entries", raise_runtime_error)

    result = cli_runner.invoke(
        cli,
        [
            "import_cache",
            "-i",
            str(export_dir),
            "-c",
            str(dest_cache),
        ],
    )

    assert result.exit_code == 1
    assert "Import failed" in result.output


# Test import_cache KeyboardInterrupt handling.
def test_cli_import_cache_keyboard_interrupt(
    cli_runner: CliRunner, tmp_path, monkeypatch
) -> None:
    from causaliq_workflow.cache import CacheEntry, WorkflowCache

    source_cache = tmp_path / "source.db"
    export_dir = tmp_path / "exported"
    dest_cache = tmp_path / "dest.db"

    with WorkflowCache(source_cache) as cache:
        entry = CacheEntry(metadata={"v": 1})
        entry.add_object("data", "json", '{"v": 1}')
        cache.put({"a": "1"}, entry)
        cache.export(export_dir)

    def raise_keyboard_interrupt(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        WorkflowCache, "import_entries", raise_keyboard_interrupt
    )

    result = cli_runner.invoke(
        cli,
        [
            "import_cache",
            "-i",
            str(export_dir),
            "-c",
            str(dest_cache),
        ],
    )

    assert result.exit_code == 130
    assert "Import interrupted by user" in result.output


# Test import_cache ImportError handling.
def test_cli_import_cache_import_error(
    cli_runner: CliRunner, tmp_path, monkeypatch
) -> None:
    export_dir = tmp_path / "exported"
    export_dir.mkdir()
    dest_cache = tmp_path / "dest.db"

    def raise_import_error(*args, **kwargs):
        raise ImportError("Missing causaliq_core")

    monkeypatch.setattr(
        "causaliq_workflow.cache.WorkflowCache", raise_import_error
    )

    result = cli_runner.invoke(
        cli,
        [
            "import_cache",
            "-i",
            str(export_dir),
            "-c",
            str(dest_cache),
        ],
    )

    assert result.exit_code == 1
    assert "Missing required dependencies" in result.output
