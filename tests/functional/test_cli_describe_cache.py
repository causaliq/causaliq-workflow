"""Functional tests for the describe-cache CLI command."""

from pathlib import Path

from causaliq_core.metadata import build_metadata
from click.testing import CliRunner
from pytest import fixture

from causaliq_workflow.cache import CacheEntry, WorkflowCache
from causaliq_workflow.cli import cli


@fixture
def cli_runner() -> CliRunner:
    """Pytest fixture for CLI runner."""
    return CliRunner()


def _metadata() -> dict:
    """Return a version 2 metadata envelope for a test entry."""
    return build_metadata(
        "causaliq-analysis",
        "evaluate_graph",
        {},
        {"status": "ok"},
    )


def _write_cache(path: Path, entries: list[dict]) -> Path:
    """Write a cache whose entries declare a matrix and optional object.

    Args:
        path: Destination cache path.
        entries: Entry specifications, each with ``matrix`` and either an
            ``object_type`` or None for a failure entry.

    Returns:
        The cache path.
    """
    with WorkflowCache(path) as cache:
        for entry in entries:
            matrix = entry["matrix"]
            if entry.get("object_type") is None:
                cache.put_failure(matrix, _metadata())
                continue
            item = CacheEntry(metadata=_metadata())
            item.add_object(
                entry["object_type"],
                entry.get("format", "json"),
                entry.get("content", "{}"),
                entry.get("action", "evaluate_graph"),
            )
            cache.put_typed(matrix, item)
    return path


def _two_networks() -> list[dict]:
    """Return a partitioned metrics cache specification."""
    return [
        {
            "matrix": {"network": "asia", "algorithm": "pc"},
            "object_type": "metrics",
        },
        {
            "matrix": {"network": "asia", "algorithm": "ges"},
            "object_type": "metrics",
        },
        {"matrix": {"network": "cancer", "algorithm": "pc"}},
    ]


def _value_line(output: str, value: str) -> str:
    """Return the report line for one matrix value."""
    return next(
        line
        for line in output.splitlines()
        if line.startswith(f"    {value} ")
    )


# Test describe-cache help lists the command options.
def test_describe_cache_help_lists_options(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(cli, ["describe-cache", "--help"])
    assert result.exit_code == 0
    assert "Describe a workflow cache" in result.output
    assert "--input" in result.output


# Test the report shows the file path, size and cache type.
def test_describe_cache_reports_file_size_and_type(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    cache_path = _write_cache(tmp_path / "metrics.db", _two_networks())

    result = cli_runner.invoke(cli, ["describe-cache", "-i", str(cache_path)])

    assert result.exit_code == 0
    assert str(cache_path.resolve()) in result.output
    assert "  Size        :" in result.output
    assert "KByte" in result.output or "Bytes" in result.output
    assert "  Object type : metrics" in result.output


# Test the report counts possible, present and object-bearing entries.
def test_describe_cache_reports_entry_counts(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    cache_path = _write_cache(tmp_path / "metrics.db", _two_networks())

    result = cli_runner.invoke(cli, ["describe-cache", "-i", str(cache_path)])

    assert (
        "  Entries     : 4 possible / 3 with an entry / "
        "2 with an object" in result.output
    )


# Test each variable lists its values with their counts.
def test_describe_cache_lists_variable_values(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    cache_path = _write_cache(tmp_path / "metrics.db", _two_networks())

    result = cli_runner.invoke(cli, ["describe-cache", "-i", str(cache_path)])

    assert "  network (str)" in result.output
    assert "  algorithm (str)" in result.output
    assert _value_line(result.output, "asia").endswith("2 / 2 / 2")
    assert _value_line(result.output, "cancer").endswith("2 / 1 / 0")
    assert _value_line(result.output, "ges").endswith("2 / 1 / 1")
    assert _value_line(result.output, "pc").endswith("2 / 2 / 1")


# Test the report shows an example entry with its object and metadata.
def test_describe_cache_shows_example_entry(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    cache_path = _write_cache(tmp_path / "metrics.db", _two_networks())

    result = cli_runner.invoke(cli, ["describe-cache", "-i", str(cache_path)])

    assert "Example entry:" in result.output
    assert '  key      : {"algorithm": ' in result.output
    assert (
        "  object   : type=metrics, format=json, "
        "action=evaluate_graph" in result.output
    )
    assert '"status": "ok"' in result.output


# Test an empty cache reports zero counts and no sections.
def test_describe_cache_empty_cache(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "empty.db"
    with WorkflowCache(cache_path):
        pass

    result = cli_runner.invoke(cli, ["describe-cache", "-i", str(cache_path)])

    assert result.exit_code == 0
    assert (
        "  Entries     : 0 possible / 0 with an entry / "
        "0 with an object" in result.output
    )
    assert "  Object type : unknown" in result.output
    assert result.output.count("  (none)") == 2


# Test a failure-only cache has no object and no cache type.
def test_describe_cache_failure_only(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    cache_path = _write_cache(
        tmp_path / "failures.db",
        [{"matrix": {"network": "asia"}}],
    )

    result = cli_runner.invoke(cli, ["describe-cache", "-i", str(cache_path)])

    assert result.exit_code == 0
    assert "  Object type : unknown" in result.output
    assert (
        "  Entries     : 1 possible / 1 with an entry / "
        "0 with an object" in result.output
    )
    assert "  object   : none" in result.output


# Test an unpinned cache reports the object types it holds.
def test_describe_cache_unpinned_cache(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "legacy.db"
    with WorkflowCache(cache_path) as cache:
        entry = CacheEntry(metadata=_metadata())
        entry.add_object("dag", "graphml", "<graphml/>", "learn_graph")
        cache.put({"network": "asia"}, entry)

    result = cli_runner.invoke(cli, ["describe-cache", "-i", str(cache_path)])

    assert result.exit_code == 0
    assert "  Object type : dag" in result.output


# Test list-valued matrix values are reported with their type.
def test_describe_cache_list_valued_matrix(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    cache_path = _write_cache(
        tmp_path / "fusion.db",
        [
            {
                "matrix": {"network": "asia", "weights": [0.5, 0.5]},
                "object_type": "metrics",
            }
        ],
    )

    result = cli_runner.invoke(cli, ["describe-cache", "-i", str(cache_path)])

    assert result.exit_code == 0
    assert "  weights (list)" in result.output
    assert "[0.5, 0.5]" in result.output


# Test a file that is not a cache reports a clear error.
def test_describe_cache_rejects_non_cache_file(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "not_a_cache.db"
    cache_path.write_text("not a cache", encoding="utf-8")

    result = cli_runner.invoke(cli, ["describe-cache", "-i", str(cache_path)])

    assert result.exit_code == 1
    assert "Failed to describe cache" in result.output


# Test a missing cache path is rejected by click.
def test_describe_cache_rejects_missing_path(
    cli_runner: CliRunner,
    tmp_path: Path,
) -> None:
    result = cli_runner.invoke(
        cli, ["describe-cache", "-i", str(tmp_path / "absent.db")]
    )

    assert result.exit_code != 0
    assert "does not exist" in result.output.lower()


# Test an interrupted description exits with the interrupt status.
def test_describe_cache_reports_interrupt(
    cli_runner: CliRunner,
    tmp_path: Path,
    mocker,
) -> None:
    cache_path = _write_cache(tmp_path / "metrics.db", _two_networks())
    mocker.patch(
        "causaliq_workflow.cache.describe.describe_cache",
        side_effect=KeyboardInterrupt,
    )

    result = cli_runner.invoke(cli, ["describe-cache", "-i", str(cache_path)])

    assert result.exit_code == 130
    assert "Description interrupted by user" in result.output
