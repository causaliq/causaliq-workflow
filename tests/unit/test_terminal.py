"""Unit tests for immediate terminal output (terminal.py)."""

import io
import sys
from typing import Any, Dict, List

import pytest
from pytest_mock import MockerFixture

from causaliq_workflow.terminal import (
    configure_terminal_output,
    echo_line,
    flush_terminal,
)


class SpyStream:
    """Stream stand-in that records reconfiguration and flush requests."""

    def __init__(self, *, fail: bool = False) -> None:
        self.reconfigure_calls: List[Dict[str, Any]] = []
        self.flush_calls = 0
        self._fail = fail

    def reconfigure(self, **kwargs: Any) -> None:
        """Record the requested stream configuration."""
        if self._fail:
            raise ValueError("stream is detached")
        self.reconfigure_calls.append(kwargs)

    def flush(self) -> None:
        """Record a flush request."""
        if self._fail:
            raise ValueError("stream is closed")
        self.flush_calls += 1


# Line buffering is requested for both standard streams.
def test_configure_terminal_output_enables_line_buffering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout, stderr = SpyStream(), SpyStream()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    configure_terminal_output()

    expected = {"line_buffering": True, "write_through": True}
    assert stdout.reconfigure_calls == [expected]
    assert stderr.reconfigure_calls == [expected]


# A real text stream ends up line buffered.
def test_configure_terminal_output_line_buffers_text_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.TextIOWrapper(io.BytesIO())
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(io.BytesIO()))

    configure_terminal_output()

    assert stream.line_buffering is True


# Streams without a reconfigure method are left untouched.
def test_configure_terminal_output_skips_plain_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plain = io.StringIO()
    monkeypatch.setattr(sys, "stdout", plain)
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    configure_terminal_output()

    assert sys.stdout is plain


# A detached stream does not interrupt the reconfiguration pass.
def test_configure_terminal_output_ignores_detached_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = SpyStream(fail=True)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", SpyStream(fail=True))

    configure_terminal_output()

    assert stdout.reconfigure_calls == []


# Both standard streams are flushed.
def test_flush_terminal_flushes_stdout_and_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout, stderr = SpyStream(), SpyStream()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    flush_terminal()

    assert stdout.flush_calls == 1
    assert stderr.flush_calls == 1


# A closed stream does not interrupt the flush pass.
def test_flush_terminal_ignores_closed_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdout = SpyStream(fail=True)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", SpyStream(fail=True))

    flush_terminal()

    assert stdout.flush_calls == 0


# Emitting a line writes it and flushes immediately.
def test_echo_line_writes_and_flushes(
    capsys: pytest.CaptureFixture, mocker: MockerFixture
) -> None:
    flush = mocker.patch("causaliq_workflow.terminal.flush_terminal")

    echo_line("progress")

    assert capsys.readouterr().out == "progress\n"
    flush.assert_called_once_with()


# Error lines are written to stderr.
def test_echo_line_writes_errors_to_stderr(
    capsys: pytest.CaptureFixture,
) -> None:
    echo_line("boom", err=True)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "boom" in captured.err
