"""UPDATE pattern execution and scanning."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from causaliq_workflow.registry import WorkflowContext
from causaliq_workflow.workflow._base import WorkflowExecutorBase


@dataclass
class _UpdateCounts:
    """Mutable counters shared across an UPDATE step's input caches."""

    processed: int = 0
    skipped: int = 0
    updated: int = 0
    errors: List[str] = field(default_factory=list)

    def to_result(self) -> Dict[str, Any]:
        """Build the UPDATE step result dictionary."""
        if self.updated > 0:
            status = "success"
        elif self.skipped == self.processed:
            status = "skipped"
        else:
            status = "error" if self.errors else "skipped"

        result: Dict[str, Any] = {
            "status": status,
            "entries_processed": self.processed,
            "entries_skipped": self.skipped,
            "entries_updated": self.updated,
        }
        if self.errors:
            result["errors"] = self.errors
        return result


@dataclass
class _UpdateRun:
    """Per-call state for executing an UPDATE step."""

    resolved_inputs: Dict[str, Any]
    provider_name: str
    action_name: str
    action_method: str
    step_name: str
    context: WorkflowContext
    step_logger: Optional[Callable[[str, str, str, Dict[str, Any]], None]]
    counts: _UpdateCounts


@dataclass
class _ScanCounts:
    """Mutable counters for a dry-run UPDATE scan."""

    would_process: int = 0
    would_skip: int = 0


@dataclass
class _ScanRun:
    """Per-call state for a dry-run UPDATE scan."""

    provider_name: str
    action_method: str
    step_name: str
    step_logger: Optional[Callable[[str, str, str, Dict[str, Any]], None]]
    filter_expr: Optional[str]
    matrix_values: Optional[Dict[str, Any]]
    counts: _ScanCounts = field(default_factory=_ScanCounts)


class UpdateMixin(WorkflowExecutorBase):
    """UPDATE pattern methods for WorkflowExecutor."""

    def _execute_update_step(
        self,
        step: Dict[str, Any],
        resolved_inputs: Dict[str, Any],
        context: WorkflowContext,
        step_logger: Optional[
            Callable[[str, str, str, Dict[str, Any]], None]
        ] = None,
    ) -> Dict[str, Any]:
        """Execute a step in UPDATE pattern mode.

        UPDATE mode processes all entries in one or more input caches:
        1. Opens each input cache
        2. Iterates all entries (subject to filter)
        3. Applies conservative execution (skip if action metadata exists)
        4. Calls action with entry data via _update_entry parameter
        5. Updates entry metadata and objects in place

        Args:
            step: Step configuration dictionary
            resolved_inputs: Resolved action inputs
            context: Workflow context
            step_logger: Optional logging function

        Returns:
            Step result dictionary with status, updated counts, etc.
        """
        from pathlib import Path

        error, input_paths = _resolve_update_inputs(
            resolved_inputs.get("input")
        )
        if error:
            return _update_error_result(error)

        missing = [path for path in input_paths if not Path(path).exists()]
        if missing:
            return _update_error_result(
                f"Input cache(s) do not exist: {', '.join(missing)}"
            )

        run = self._update_run(step, resolved_inputs, context, step_logger)
        matrix_values = getattr(context, "matrix_values", None)
        for input_path in input_paths:
            self._update_cache(
                run, input_path, matrix_values, resolved_inputs.get("filter")
            )

        return run.counts.to_result()

    def _update_run(
        self,
        step: Dict[str, Any],
        resolved_inputs: Dict[str, Any],
        context: WorkflowContext,
        step_logger: Optional[Callable[[str, str, str, Dict[str, Any]], None]],
    ) -> _UpdateRun:
        """Build the per-call state for executing an UPDATE step."""
        action_name = step["uses"]
        action_class = self.action_registry.get_action_class(action_name)
        return _UpdateRun(
            resolved_inputs=resolved_inputs,
            provider_name=getattr(action_class, "name", action_name),
            action_name=action_name,
            action_method=resolved_inputs.get("action", "default"),
            step_name=step.get("name", "unknown"),
            context=context,
            step_logger=step_logger,
            counts=_UpdateCounts(),
        )

    def _update_cache(
        self,
        run: _UpdateRun,
        input_path: str,
        matrix_values: Optional[Dict[str, Any]],
        filter_expr: Optional[str],
    ) -> None:
        """Process every targeted entry in one UPDATE input cache."""
        from causaliq_workflow.cache import WorkflowCache

        with WorkflowCache(input_path) as cache:
            if matrix_values:
                entries = [{"matrix_values": matrix_values}]
            else:
                entries = cache.list_entries()

            resolved_filter, extra_names = self._resolve_filter(
                filter_expr, cache, entries
            )
            for entry_info in entries:
                self._update_entry(
                    run, cache, entry_info, resolved_filter, extra_names
                )

    def _update_entry(
        self,
        run: _UpdateRun,
        cache: Any,
        entry_info: Dict[str, Any],
        resolved_filter: Optional[str],
        extra_names: Dict[str, Any],
    ) -> None:
        """Apply the UPDATE action to a single cache entry."""
        entry_matrix = entry_info.get("matrix_values", {})
        run.counts.processed += 1

        full_entry = cache.get(entry_matrix)
        if full_entry is None:
            return

        flat_meta = self._flatten_metadata(entry_matrix, full_entry.metadata)
        if self._update_entry_skipped(
            run, cache, entry_matrix, resolved_filter, extra_names, flat_meta
        ):
            return

        self._apply_update_action(
            run, cache, entry_matrix, full_entry, flat_meta
        )

    def _update_entry_skipped(
        self,
        run: _UpdateRun,
        cache: Any,
        entry_matrix: Dict[str, Any],
        resolved_filter: Optional[str],
        extra_names: Dict[str, Any],
        flat_meta: Dict[str, Any],
    ) -> bool:
        """Return True when the entry is filtered out or already applied."""
        if _update_filter_skip(
            entry_matrix, resolved_filter, extra_names, flat_meta
        ):
            _log_update_skip(run, entry_matrix, "IGNORED")
            return True

        # Conservative execution: skip if the action was already applied.
        # Bypassed in force mode.
        if run.context.mode == "force":
            return False
        applied = cache.has_action_metadata(
            entry_matrix, run.provider_name, run.action_method
        )
        if applied:
            _log_update_skip(run, entry_matrix, "SKIPPED")
            return True
        return False

    def _apply_update_action(
        self,
        run: _UpdateRun,
        cache: Any,
        entry_matrix: Dict[str, Any],
        full_entry: Any,
        flat_meta: Dict[str, Any],
    ) -> None:
        """Execute the UPDATE action for one entry and store the result."""
        action_inputs = {
            key: value
            for key, value in run.resolved_inputs.items()
            if key not in ("input", "filter")
        }

        # Resolve any remaining template variables from entry metadata.
        # This enables UPDATE steps to use {{network}}, {{sample_size}}
        # etc. resolved from each entry's metadata.
        action_inputs = self._resolve_template_variables(
            action_inputs, flat_meta
        )
        action_inputs["_update_entry"] = {
            "matrix_values": entry_matrix,
            "metadata": full_entry.metadata,
            "entry": full_entry,
        }

        try:
            result = self.action_registry.execute_action(
                run.action_name, action_inputs, run.context
            )
            if result.get("status") == "success":
                self._store_update_result(run, cache, entry_matrix, result)
        except Exception as e:
            run.counts.errors.append(f"Entry {entry_matrix}: {e}")
            _log_update_event(run, entry_matrix, "FAILED")

    def _store_update_result(
        self,
        run: _UpdateRun,
        cache: Any,
        entry_matrix: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """Store a successful UPDATE action result in the cache."""
        raw_metadata = result.get("_action_metadata", {})
        structured_metadata = {
            run.provider_name: {run.action_method: raw_metadata}
        }
        objects = result.get("objects", [])
        if not cache.update_entry(entry_matrix, structured_metadata, objects):
            return

        self._invalidate_scan_index(cache)
        run.counts.updated += 1
        status = "FORCED" if run.context.mode == "force" else "EXECUTED"
        _log_update_event(run, entry_matrix, status)

    def _scan_update_step_entries(
        self,
        step: Dict[str, Any],
        resolved_inputs: Dict[str, Any],
        context: Optional[WorkflowContext] = None,
        step_logger: Optional[
            Callable[[str, str, str, Dict[str, Any]], None]
        ] = None,
    ) -> Dict[str, int]:
        """Scan UPDATE step cache(s) to count entries that would be processed.

        Used in dry-run mode to report how many entries would be updated
        vs skipped (due to conservative execution - action already applied).
        Optionally logs per-entry status via step_logger.

        Args:
            step: Step configuration dictionary
            resolved_inputs: Resolved action inputs
            context: Workflow context
            step_logger: Optional logging function for per-entry status

        Returns:
            Dictionary with would_process and would_skip counts
        """
        from pathlib import Path

        error, input_paths = _resolve_update_inputs(
            resolved_inputs.get("input")
        )
        if error:
            return {"would_process": 0, "would_skip": 0}

        run = self._scan_run(step, resolved_inputs, context, step_logger)
        for input_path in input_paths:
            if Path(input_path).exists():
                self._scan_update_cache(run, input_path)
            else:
                _scan_missing_cache(run)

        return {
            "would_process": run.counts.would_process,
            "would_skip": run.counts.would_skip,
        }

    def _scan_run(
        self,
        step: Dict[str, Any],
        resolved_inputs: Dict[str, Any],
        context: Optional[WorkflowContext],
        step_logger: Optional[Callable[[str, str, str, Dict[str, Any]], None]],
    ) -> _ScanRun:
        """Build the per-call state for a dry-run UPDATE scan."""
        action_name = step["uses"]
        action_class = self.action_registry.get_action_class(action_name)
        return _ScanRun(
            provider_name=getattr(action_class, "name", action_name),
            action_method=resolved_inputs.get("action", "default"),
            step_name=step.get("name", "unknown"),
            step_logger=step_logger,
            filter_expr=resolved_inputs.get("filter"),
            matrix_values=getattr(context, "matrix_values", None),
        )

    def _scan_update_cache(self, run: _ScanRun, input_path: str) -> None:
        """Scan every targeted entry in one UPDATE cache."""
        from causaliq_workflow.cache import WorkflowCache

        with WorkflowCache(input_path) as cache:
            if run.matrix_values:
                entries = [{"matrix_values": run.matrix_values}]
            else:
                entries = cache.list_entries()

            resolved_filter, extra_names = self._resolve_filter(
                run.filter_expr, cache, entries
            )
            for entry_info in entries:
                self._scan_update_entry(
                    run, cache, entry_info, resolved_filter, extra_names
                )

    def _scan_update_entry(
        self,
        run: _ScanRun,
        cache: Any,
        entry_info: Dict[str, Any],
        resolved_filter: Optional[str],
        extra_names: Dict[str, Any],
    ) -> None:
        """Classify a single entry as would-process or would-skip."""
        entry_matrix = entry_info.get("matrix_values", {})
        full_entry = cache.get(entry_matrix)
        if full_entry is None:
            _scan_missing_entry(run, entry_matrix)
            return

        self._scan_classify_entry(
            run,
            cache,
            entry_matrix,
            full_entry,
            resolved_filter,
            extra_names,
        )

    def _scan_classify_entry(
        self,
        run: _ScanRun,
        cache: Any,
        entry_matrix: Dict[str, Any],
        full_entry: Any,
        resolved_filter: Optional[str],
        extra_names: Dict[str, Any],
    ) -> None:
        """Classify an existing entry as would-process or would-skip."""
        flat_meta = self._flatten_metadata(entry_matrix, full_entry.metadata)
        if _update_filter_skip(
            entry_matrix, resolved_filter, extra_names, flat_meta
        ):
            _scan_skip(run, entry_matrix, "WOULD IGNORE")
            return

        applied = cache.has_action_metadata(
            entry_matrix, run.provider_name, run.action_method
        )
        if applied:
            _scan_skip(run, entry_matrix, "WOULD SKIP")
            return
        _scan_process(run, entry_matrix, "WOULD EXECUTE")


def _resolve_update_inputs(
    input_param: Any,
) -> Tuple[Optional[str], List[Any]]:
    """Return (error_message, input_paths) for an UPDATE input parameter."""
    if input_param is None:
        return "UPDATE action requires 'input' parameter", []
    if isinstance(input_param, str):
        return None, [input_param]
    if isinstance(input_param, list):
        return None, list(input_param)
    message = (
        f"'input' must be string or list, got {type(input_param).__name__}"
    )
    return message, []


def _update_error_result(message: str) -> Dict[str, Any]:
    """Build an UPDATE step error result dictionary."""
    return {
        "status": "error",
        "error": message,
        "entries_processed": 0,
        "entries_skipped": 0,
        "entries_updated": 0,
    }


def _update_filter_skip(
    entry_matrix: Dict[str, Any],
    resolved_filter: Optional[str],
    extra_names: Dict[str, Any],
    flat_meta: Dict[str, Any],
) -> bool:
    """Return True when the entry should be skipped by the filter.

    A filter evaluation error also skips the entry (validation catches
    syntax errors upfront).
    """
    from causaliq_core.utils import evaluate_filter

    if not resolved_filter:
        return False
    try:
        return not evaluate_filter(
            resolved_filter, {**flat_meta, **extra_names}
        )
    except Exception:
        return True


def _log_update_event(
    run: _UpdateRun, entry_matrix: Dict[str, Any], status: str
) -> None:
    """Log one entry outcome when a step logger is present."""
    if run.step_logger:
        run.step_logger(run.action_method, run.step_name, status, entry_matrix)


def _log_update_skip(
    run: _UpdateRun, entry_matrix: Dict[str, Any], status: str
) -> None:
    """Increment the skipped counter and log the entry outcome."""
    run.counts.skipped += 1
    _log_update_event(run, entry_matrix, status)


def _scan_missing_cache(run: _ScanRun) -> None:
    """Count a missing cache as work when targeting a matrix entry."""
    if not run.matrix_values:
        return
    run.counts.would_process += 1
    _log_scan_event(run, run.matrix_values, "WOULD EXECUTE")


def _scan_missing_entry(run: _ScanRun, entry_matrix: Dict[str, Any]) -> None:
    """Count a missing entry as work when targeting a matrix entry."""
    if not run.matrix_values:
        return
    run.counts.would_process += 1
    _log_scan_event(run, entry_matrix, "WOULD EXECUTE")


def _scan_skip(
    run: _ScanRun, entry_matrix: Dict[str, Any], status: str
) -> None:
    """Increment the would-skip counter and log the entry."""
    run.counts.would_skip += 1
    _log_scan_event(run, entry_matrix, status)


def _scan_process(
    run: _ScanRun, entry_matrix: Dict[str, Any], status: str
) -> None:
    """Increment the would-process counter and log the entry."""
    run.counts.would_process += 1
    _log_scan_event(run, entry_matrix, status)


def _log_scan_event(
    run: _ScanRun, entry_matrix: Dict[str, Any], status: str
) -> None:
    """Log an entry outcome when a step logger is present."""
    if run.step_logger:
        run.step_logger(run.action_method, run.step_name, status, entry_matrix)
