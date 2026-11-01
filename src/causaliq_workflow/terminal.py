"""Terminal output helpers that keep workflow messages timely.

Workflow messages are written one line at a time and flushed as they are
produced, so a long run reports progress instead of releasing the whole
transcript when it ends. Action providers also print their own progress
directly to ``stdout``, so the stream itself is asked to line-buffer for
the duration of a run.
"""

import sys
from typing import Any

import click


def configure_terminal_output() -> None:
    """Ask stdout and stderr to flush after every line.

    Streams that cannot be reconfigured, such as the in-memory captures
    used by test harnesses, are left untouched. Reconfiguring is
    idempotent, so asking more than once is harmless.

    Returns:
        None.
    """
    for stream in (sys.stdout, sys.stderr):
        _reconfigure_stream(stream)


def _reconfigure_stream(stream: Any) -> None:
    """Enable line buffering on one stream when it supports it."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(line_buffering=True, write_through=True)
    except (ValueError, OSError):
        return


def flush_terminal() -> None:
    """Flush stdout and stderr, ignoring streams that are closed."""
    for stream in (sys.stdout, sys.stderr):
        _flush_stream(stream)


def _flush_stream(stream: Any) -> None:
    """Flush one stream, ignoring a stream that is already closed."""
    try:
        stream.flush()
    except (ValueError, OSError):
        return


def echo_line(message: str = "", *, err: bool = False) -> None:
    """Write one terminal line and flush it immediately.

    Args:
        message: Text to write, without the trailing newline.
        err: Write to stderr instead of stdout.

    Returns:
        None.
    """
    click.echo(message, err=err)
    flush_terminal()
