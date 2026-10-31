"""Cache writes and step completion logging for workflow execution.

The store mixin owns every write to the open workflow cache, plus the
completion log line, so the execution and step-runner mixins stay within
the module and method limits.
"""

from typing import Any, Dict, Optional

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.job_state import _JobState
from causaliq_workflow.workflow.provenance import (
    build_result_metadata,
    collect_environment,
)


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
        if state.context.cache is None:
            return

        if step_result.get("status") == "error":
            self._store_failure(state, step_result, provenance)
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
        step_result: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> None:
        """Record a failed step as provenance only."""
        from causaliq_workflow.cache import store_failure_result

        metadata = build_result_metadata(provenance, step_result)
        store_failure_result(
            cache=state.context.cache,
            context=state.context,
            metadata=metadata,
            matrix_key_order=list(state.context.matrix.keys()),
        )
        self._invalidate_scan_index(state.context.cache)

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
    ) -> None:
        """Log a step's completion status when a step logger is present."""
        if not state.step_logger:
            return

        action_method = resolved_inputs.get("action", "default")
        status = step_result.get("status", "unknown")
        if status == "success":
            status = "FORCED" if state.context.mode == "force" else "EXECUTED"
        elif status == "skipped":
            status = "SKIPPED"
        else:
            status = "FAILED"
        state.step_logger(
            action_method,
            step_name,
            status,
            state.context.matrix_values,
            depth=state.depth,
        )
