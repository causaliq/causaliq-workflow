"""Workflow logging infrastructure for standardized task execution reporting.

This module provides the WorkflowLogger class for centralized logging with
multiple output destinations (terminal, file, test capture).
"""

import sys
from enum import Enum
from pathlib import Path
from typing import Any, TextIO


class LogLevel(Enum):
    """Logging verbosity levels for workflow execution."""

    NONE = "none"
    """No logging output - silent execution."""

    SUMMARY = "summary"
    """Summary-level logging - key status and final results only."""

    ALL = "all"
    """Comprehensive logging - all task details and intermediate steps."""


class WorkflowLogger:
    """Centralized logging with multiple output destinations.

    Provides standardized logging infrastructure supporting file output,
    terminal output, and test-capturable output for workflow execution
    monitoring and debugging.

    This is the core logging structure without task-specific logic.
    The log_task method and progress functionality will be added in
    subsequent commits.

    Args:
        terminal: Enable terminal output (default: True)
        log_file: Optional file path for log output
        log_level: Logging verbosity level (default: SUMMARY)
    """

    def __init__(
        self,
        terminal: bool = True,
        log_file: Path | None = None,
        log_level: LogLevel = LogLevel.SUMMARY,
    ) -> None:
        """Initialize logger with output destinations and verbosity level."""
        self.terminal = terminal
        self.log_file = log_file
        self.log_level = log_level

        # Initialize output streams
        self._terminal_stream: TextIO = sys.stdout
        self._file_stream: TextIO | None = None

        # File stream will be opened lazily when first needed

    def _open_log_file(self) -> None:
        """Open log file for writing, creating directories if needed."""
        if self.log_file and self._file_stream is None:
            # Create parent directories if they don't exist
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

            # Open file in append mode to support multiple workflow runs
            self._file_stream = open(self.log_file, "a", encoding="utf-8")

    def close(self) -> None:
        """Close file streams and cleanup resources."""
        if self._file_stream:
            self._file_stream.close()
            self._file_stream = None

    def __enter__(self) -> "WorkflowLogger":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit with cleanup."""
        self.close()

    @property
    def is_file_logging(self) -> bool:
        """Return True if file logging is enabled."""
        return self.log_file is not None

    def _ensure_file_stream(self) -> None:
        """Ensure file stream is open if file logging is enabled."""
        if self.log_file and self._file_stream is None:
            self._open_log_file()

    @property
    def is_terminal_logging(self) -> bool:
        """Return True if terminal logging is enabled."""
        return self.terminal

    @property
    def has_output_destinations(self) -> bool:
        """Return True if any output destination is configured."""
        return self.terminal or self.log_file is not None
