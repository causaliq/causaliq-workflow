"""Cache writes and step completion logging for workflow execution.

The store mixin owns every write to the open workflow cache, plus the
completion log line, so the execution and step-runner mixins stay within
the module and method limits.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from causaliq_workflow.reporting import format_elapsed
from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.job_state import _JobState
from causaliq_workflow.workflow.provenance import (
    build_result_metadata,
    collect_environment,
)

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.cache import WorkflowCache


class StepStoreMixin(WorkflowExecutorBase):
    """Storing step results and failures for WorkflowExecutor."""

    def _get_environment(self) -> Optional[Dict[str, Any]]:
        """Return the run environment, collecting it at most once."""
        if not getattr(self, "_environment_ready", False):
            self._environment = collect_environment()
            self._environment_ready = True
        return self._environment

    def _store_step_result(
        self,
        state: _JobState,
        step_result: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> None:
        """Store a step result to the open cache when appropriate.

        Successful actions store their single typed object. Actions that
        return an "error" status record provenance only (status and failure
        reason), replacing any prior entry for the key so the latest run
        wins and the failure is exported as _meta.json.
        """
        cache = state.context.cache
        if cache is None:
            return

        if step_result.get("status") == "error":
            self._store_failure(state, cache, step_result, provenance)
            return

        successful = step_result.get(
            "status"
        ) == "success" and step_result.get("objects")
        if not successful:
            return

        self._store_action_result(state, step_result, provenance)

    def _store_failure(
        self,
        state: _JobState,
        cache: "WorkflowCache",
        step_result: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> None:
        """Record a failed step as provenance only.

        Failure entries hold no object, so the cache type is pinned only
        when it is already known: a failed first write leaves the cache
        unpinned for the next successful write to declare the type.
        """
        metadata = build_result_metadata(provenance, step_result)
        cache.put_failure(
            state.context.matrix_values,
            metadata,
            matrix_key_order=list(state.context.matrix.keys()),
        )
        self._invalidate_scan_index(cache)

    def _store_action_result(
        self,
        state: _JobState,
        step_result: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> None:
        """Write a step result (objects and metadata) to the open cache."""
        from causaliq_workflow.cache import store_action_result

        metadata = build_result_metadata(provenance, step_result)
        store_action_result(
            cache=state.context.cache,
            context=state.context,
            metadata=metadata,
            objects=step_result.get("objects", []),
            matrix_key_order=list(state.context.matrix.keys()),
        )
        self._invalidate_scan_index(state.context.cache)

    def _log_step_completion(
        self,
        state: _JobState,
        step_name: str,
        resolved_inputs: Dict[str, Any],
        step_result: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> None:
        """Log a step's completion status when a step logger is present."""
        if not state.step_logger:
            return

        action_method = resolved_inputs.get("action", "default")
        state.step_logger(
            action_method,
            step_name,
            _completion_status(state, step_result),
            state.context.matrix_values,
            depth=state.depth,
            detail=format_elapsed(float(provenance["elapsed"])),
        )


def _completion_status(state: _JobState, step_result: Dict[str, Any]) -> str:
    """Return the reported status of a finished step."""
    status = step_result.get("status", "unknown")
    if status == "success":
        return "FORCED" if state.context.mode == "force" else "EXECUTED"
    if status == "skipped":
        return "SKIPPED"
    return "FAILED"
