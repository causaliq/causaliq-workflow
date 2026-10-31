"""Running one workflow step: action calls, skips and dry-run previews.

The step-runner mixin turns a resolved step into an action call. It owns
the conservative skip rules, the aggregation wiring and the CREATE /
AGGREGATE dry-run preview, so the execution mixin only sequences steps.
"""

from typing import Any, Dict

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.aggregation import AggregationConfig
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.frames import is_workflow_call_step
from causaliq_workflow.workflow.job_state import _JobState
from causaliq_workflow.workflow.matrix import _cache_entry_exists
from causaliq_workflow.workflow.provenance import execute_with_provenance


class StepRunnerMixin(WorkflowExecutorBase):
    """Executing a single workflow step for WorkflowExecutor."""

    def _run_action_step(
        self, state: _JobState, step: Dict[str, Any], step_name: str
    ) -> bool:
        """Execute an action ('uses') or workflow-call step.

        Returns True when the step reached normal execution (so the job's
        matrix values should be restored), False when it was skipped.
        """
        if is_workflow_call_step(step):
            return self._run_workflow_call_step(state, step, step_name)

        action_name = step["uses"]
        resolved_inputs = self._resolve_template_variables(
            step.get("with", {}), state.variables
        )
        if self._skip_nocache_step(state, step, step_name, resolved_inputs):
            return False

        self._apply_aggregation(state, step, resolved_inputs)
        return self._run_create_step(
            state, step_name, action_name, resolved_inputs
        )

    def _skip_nocache_step(
        self,
        state: _JobState,
        step: Dict[str, Any],
        step_name: str,
        resolved_inputs: Dict[str, Any],
    ) -> bool:
        """Skip single-run steps on every matrix job after the first.

        A step that writes no workflow cache has no output dimensionality,
        so it runs once. It is skipped on later jobs.
        """
        if (
            not self._runs_once(step, state.workflow.get("matrix", {}))
            or state.context.job_index <= 0
        ):
            return False

        _log_step_status(state, step_name, resolved_inputs, "SKIPPED")
        state.step_results[step_name] = {
            "status": "skipped",
            "reason": "single-run-step-runs-once",
        }
        return True

    def _apply_aggregation(
        self,
        state: _JobState,
        step: Dict[str, Any],
        resolved_inputs: Dict[str, Any],
    ) -> None:
        """Scan aggregation inputs and attach the matched entries."""
        matrix = state.workflow.get("matrix", {})
        agg_config = self._get_aggregation_config(step, matrix)
        if agg_config is None:
            return

        # Use the resolved filter (with template variables substituted)
        # instead of the raw filter from the step definition.
        resolved_filter = resolved_inputs.get("filter")
        if resolved_filter != agg_config.filter_expr:
            agg_config = AggregationConfig(
                input_caches=agg_config.input_caches,
                filter_expr=resolved_filter,
                matrix_vars=agg_config.matrix_vars,
            )
        resolved_inputs["_aggregation_entries"] = (
            self._scan_aggregation_inputs(agg_config, state.job)
        )
        # Remove 'aggregate' from resolved params (config only)
        resolved_inputs.pop("aggregate", None)

    def _run_create_step(
        self,
        state: _JobState,
        step_name: str,
        action_name: str,
        resolved_inputs: Dict[str, Any],
    ) -> bool:
        """Execute a CREATE/AGGREGATE step with step-level caching.

        Only .db outputs are workflow caches; other outputs (like .csv or
        "-" for terminal) are handled directly by the action.
        """
        output_path = resolved_inputs.pop("output", None)
        has_output = _has_output(output_path)
        is_cache_output = has_output and str(output_path).lower().endswith(
            ".db"
        )

        if state.context.mode == "dry-run":
            self._dry_run_create_step(
                state,
                step_name,
                resolved_inputs,
                output_path,
                is_cache_output,
            )
            return False
        if self._prepare_step_cache(
            state, step_name, resolved_inputs, output_path, is_cache_output
        ):
            return False

        if has_output and not is_cache_output:
            resolved_inputs["output"] = output_path

        step_result = self._execute_and_store(
            state, step_name, action_name, resolved_inputs
        )
        state.step_results[step_name] = step_result
        _record_step_outputs(state, step_name, step_result)
        return True

    def _dry_run_create_step(
        self,
        state: _JobState,
        step_name: str,
        resolved_inputs: Dict[str, Any],
        output_path: Any,
        is_cache_output: bool,
    ) -> None:
        """Preview a CREATE/AGGREGATE step without executing it."""
        would_skip = _cache_entry_exists(
            is_cache_output, output_path, state.context.matrix_values
        )
        status = "WOULD SKIP" if would_skip else "WOULD EXECUTE"
        _log_step_status(state, step_name, resolved_inputs, status)
        state.step_results[step_name] = {
            "status": "would_skip" if would_skip else "would_execute"
        }

    def _prepare_step_cache(
        self,
        state: _JobState,
        step_name: str,
        resolved_inputs: Dict[str, Any],
        output_path: Any,
        is_cache_output: bool,
    ) -> bool:
        """Open the output cache and detect a conservative skip.

        Returns True when the step should be skipped because the entry
        already exists (the cache is closed again). Otherwise the cache
        is left open on the context for the action to write into.
        """
        should_cache = is_cache_output and state.context.mode in (
            "run",
            "force",
        )
        if not should_cache:
            return False

        from causaliq_workflow.cache import WorkflowCache

        step_cache = WorkflowCache(output_path)
        step_cache.open()
        state.context.cache = step_cache

        if state.context.mode == "force" or not step_cache.exists(
            state.context.matrix_values
        ):
            return False

        _log_step_status(state, step_name, resolved_inputs, "SKIPPED")
        state.step_results[step_name] = {"status": "skipped"}
        step_cache.close()
        state.context.cache = None
        return True

    def _execute_and_store(
        self,
        state: _JobState,
        step_name: str,
        action_name: str,
        resolved_inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the action, then store, check and log its result."""
        try:
            step_result, provenance = execute_with_provenance(
                self.action_registry,
                action_name,
                resolved_inputs,
                state.context,
                self._get_environment(),
            )
            self._store_step_result(
                state,
                step_result,
                provenance,
            )
            _raise_unstored_objects(
                state, step_name, resolved_inputs, step_result
            )
            self._log_step_completion(
                state, step_name, resolved_inputs, step_result
            )
            return step_result
        finally:
            if state.context.cache is not None:
                state.context.cache.close()
                state.context.cache = None


def _has_output(output_path: Any) -> bool:
    """Return True when an output parameter names a real destination."""
    return output_path is not None and str(output_path).lower() != "none"


def _raise_unstored_objects(
    state: _JobState,
    step_name: str,
    resolved_inputs: Dict[str, Any],
    step_result: Dict[str, Any],
) -> None:
    """Raise when a step produced objects with no cache to store them."""
    if state.context.cache is not None:
        return
    if step_result.get("status") != "success" or not step_result.get(
        "objects"
    ):
        return

    action_method = resolved_inputs.get("action", "default")
    raise WorkflowExecutionError(
        f"Step '{step_name}' (action '{action_method}') "
        f"produced objects but no workflow cache is open "
        f"to store them. Use 'output: path/to/cache.db' "
        f"to specify a workflow cache destination."
    )


def _record_step_outputs(
    state: _JobState, step_name: str, step_result: Dict[str, Any]
) -> None:
    """Expose a step's outputs to later steps via template variables."""
    if "outputs" in step_result:
        state.variables[f"steps.{step_name}.outputs"] = step_result["outputs"]


def _log_step_status(
    state: _JobState,
    step_name: str,
    resolved_inputs: Dict[str, Any],
    status: str,
) -> None:
    """Log a step status when a step logger is present."""
    if state.step_logger:
        action_method = resolved_inputs.get("action", "default")
        state.step_logger(
            action_method,
            step_name,
            status,
            state.context.matrix_values,
            depth=state.depth,
        )
