"""Workflow parsing and execution entry points."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from causaliq_workflow.registry import WorkflowContext
from causaliq_workflow.schema import WorkflowValidationError
from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.aggregation import AggregationConfig
from causaliq_workflow.workflow.errors import WorkflowExecutionError


@dataclass
class _JobState:
    """Mutable state for executing a single job's steps."""

    workflow: Dict[str, Any]
    job: Dict[str, Any]
    context: WorkflowContext
    cli_params: Dict[str, Any]
    step_logger: Optional[Callable[[str, str, str, Dict[str, Any]], None]]
    variables: Dict[str, Any]
    step_results: Dict[str, Any] = field(default_factory=dict)


class ExecutionMixin(WorkflowExecutorBase):
    """Parsing and execution for WorkflowExecutor."""

    def parse_workflow(
        self, workflow_path: Union[str, Path], mode: str = "dry-run"
    ) -> Dict[str, Any]:
        """Parse workflow YAML file with validation.

        Args:
            workflow_path: Path to workflow YAML file
            mode: Execution mode for action validation

        Returns:
            Parsed and validated workflow dictionary

        Raises:
            WorkflowExecutionError: If workflow parsing or validation fails
        """
        from causaliq_workflow import workflow as _workflow_module

        try:
            workflow = _workflow_module.load_workflow_file(workflow_path)
            _workflow_module.validate_workflow(workflow)
            self._validate_template_variables(workflow)

            # Validate all actions exist and can run
            self._validate_workflow_actions(workflow, mode)

            return workflow

        except WorkflowExecutionError:
            # Re-raise our own errors without wrapping
            raise
        except (WorkflowValidationError, FileNotFoundError) as e:
            raise WorkflowExecutionError(f"Workflow parsing failed: {e}")
        except Exception as e:
            raise WorkflowExecutionError(
                f"Unexpected error parsing workflow: {e}"
            ) from e

    def execute_workflow(
        self,
        workflow: Dict[str, Any],
        mode: str = "dry-run",
        cli_params: Optional[Dict[str, Any]] = None,
        step_logger: Optional[
            Callable[[str, str, str, Dict[str, Any]], None]
        ] = None,
    ) -> List[Dict[str, Any]]:
        """Execute complete workflow with matrix expansion.

        Uses two-pass execution:

        1. Validation pass: Iterates all entries (matrix combos/cache
           entries) and validates action parameters. This catches semantic
           errors like undefined filter variables before any execution.
        2. Execution pass: If validation passes, executes the workflow.

        Caching is controlled at the step level via the 'output' parameter
        in each step's 'with' block. Each step can write to its own cache.

        Args:
            workflow: Parsed workflow dictionary
            mode: Execution mode ('dry-run', 'run', 'compare')
            cli_params: Additional parameters from CLI
            step_logger: Optional function to log step execution
                (action_method, step_name, status, matrix_values)

        Returns:
            List of job results from matrix expansion

        Raises:
            WorkflowExecutionError: If validation or execution fails
        """
        if cli_params is None:
            cli_params = {}

        try:
            self._validate_execution(workflow, cli_params)

            # Validate-only mode: skip execution pass
            if mode == "validate":
                return []

            return self._execute_jobs(workflow, mode, cli_params, step_logger)

        except WorkflowExecutionError:
            # Re-raise our own errors without wrapping
            raise
        except Exception as e:
            raise WorkflowExecutionError(
                f"Workflow execution failed: {e}"
            ) from e

    def _validate_execution(
        self, workflow: Dict[str, Any], cli_params: Dict[str, Any]
    ) -> None:
        """Run the validation pass, raising on the first failure."""
        validation_errors = self._validate_all_entries(workflow, cli_params)
        if not validation_errors:
            return
        raise WorkflowExecutionError(
            "; ".join(self._deduplicate_errors(validation_errors))
        )

    def _execute_jobs(
        self,
        workflow: Dict[str, Any],
        mode: str,
        cli_params: Dict[str, Any],
        step_logger: Optional[Callable[[str, str, str, Dict[str, Any]], None]],
    ) -> List[Dict[str, Any]]:
        """Execute every matrix job and collect the results."""
        # Derive matrix from explicit definition or from input caches
        matrix = self._derive_workflow_matrix(workflow)
        jobs = self.expand_matrix(matrix)
        total_jobs = len(jobs)
        results = []

        for job_index, job in enumerate(jobs):
            # Create workflow context (cache set per-step)
            context = WorkflowContext(
                mode=mode,
                matrix=matrix,
                matrix_values=job,
                cache=None,
                job_index=job_index,
                total_jobs=total_jobs,
            )
            results.append(
                self._execute_job(
                    workflow, job, context, cli_params, step_logger
                )
            )

        return results

    def _execute_job(
        self,
        workflow: Dict[str, Any],
        job: Dict[str, Any],
        context: WorkflowContext,
        cli_params: Dict[str, Any],
        step_logger: Optional[
            Callable[[str, str, str, Dict[str, Any]], None]
        ] = None,
    ) -> Dict[str, Any]:
        """Execute single job with resolved matrix variables.

        Args:
            workflow: Base workflow configuration
            job: Job with resolved matrix variables
            context: Workflow context
            cli_params: CLI parameters
            step_logger: Optional function to log step execution

        Returns:
            Job execution results

        """
        # Validate required workflow variables (None values must be provided)
        self._validate_required_variables(workflow, cli_params)

        # Combine all variable sources for template resolution
        state = _JobState(
            workflow=workflow,
            job=job,
            context=context,
            cli_params=cli_params,
            step_logger=step_logger,
            variables={**workflow, **job, **cli_params},
        )

        for step in workflow.get("steps", []):
            self._run_step(state, step)

        return {
            "job": job,
            "steps": state.step_results,
            "context": context,
        }

    def _run_step(self, state: _JobState, step: Dict[str, Any]) -> None:
        """Execute a single step, then restore the job's matrix values."""
        step_name = step.get("name", f"step-{len(state.step_results)}")

        if "uses" in step:
            if self._run_action_step(state, step, step_name):
                # Restore original matrix values after a completed step so
                # that dedup projection for one step does not leak into
                # the next step in the same job.
                state.context.matrix_values = state.job
        elif "run" in step:
            # TODO: Shell command execution
            raise WorkflowExecutionError(
                f"Shell command execution not yet implemented: "
                f"{step['run']}"
            )
        else:
            raise WorkflowExecutionError(
                f"Step '{step_name}' must have 'uses' or 'run'"
            )

    def _run_action_step(
        self, state: _JobState, step: Dict[str, Any], step_name: str
    ) -> bool:
        """Execute an action ('uses') step.

        Returns True when the step reached normal execution (so the job's
        matrix values should be restored), False when it was skipped.
        """
        action_name = step["uses"]
        resolved_inputs = self._resolve_template_variables(
            step.get("with", {}), state.variables
        )
        if self._skip_nocache_step(state, step, step_name, resolved_inputs):
            return False

        self._apply_aggregation(state, step, resolved_inputs)
        if self._run_update_step(state, step, step_name, resolved_inputs):
            return False

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
        """Skip NOCACHES steps on every matrix job after the first."""
        if not self._is_nocache_step(step) or state.context.job_index <= 0:
            return False

        _log_step_status(state, step_name, resolved_inputs, "SKIPPED")
        state.step_results[step_name] = {
            "status": "skipped",
            "reason": "nocache-step-runs-once",
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

    def _run_update_step(
        self,
        state: _JobState,
        step: Dict[str, Any],
        step_name: str,
        resolved_inputs: Dict[str, Any],
    ) -> bool:
        """Handle an UPDATE step; return True when it was handled here."""
        matrix = state.workflow.get("matrix", {})
        if not self._is_update_step(step, matrix):
            return False

        # Dry-run for UPDATE steps - scan cache and log per-entry
        if state.context.mode == "dry-run":
            entry_counts = self._scan_update_step_entries(
                step, resolved_inputs, state.context, state.step_logger
            )
            has_work = entry_counts.get("would_process", 0) > 0
            state.step_results[step_name] = {
                "status": "would_execute" if has_work else "would_skip",
                **entry_counts,
            }
            return True

        # Execute UPDATE step (processes all cache entries).
        # Per-entry logging happens inside _execute_update_step.
        state.step_results[step_name] = self._execute_update_step(
            step, resolved_inputs, state.context, state.step_logger
        )
        return True

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
            step_result = self.action_registry.execute_action(
                action_name, resolved_inputs, state.context
            )
            self._store_step_result(
                state, action_name, resolved_inputs, step_result
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

    def _store_step_result(
        self,
        state: _JobState,
        action_name: str,
        resolved_inputs: Dict[str, Any],
        step_result: Dict[str, Any],
    ) -> None:
        """Store a step result to the open cache when appropriate.

        Successful actions are stored with their objects; actions that
        return an "error" status together with structured failure metadata
        (status + error) are stored metadata-only so their _meta.json can
        be produced on export.
        """
        if state.context.cache is None:
            return

        raw_metadata = step_result.get("_action_metadata", {})
        recorded_failure = (
            step_result.get("status") == "error"
            and "status" in raw_metadata
            and "error" in raw_metadata
        )
        successful = step_result.get(
            "status"
        ) == "success" and step_result.get("objects")
        if not successful and not recorded_failure:
            return

        self._store_action_result(
            state, action_name, resolved_inputs, step_result, raw_metadata
        )

    def _store_action_result(
        self,
        state: _JobState,
        action_name: str,
        resolved_inputs: Dict[str, Any],
        step_result: Dict[str, Any],
        raw_metadata: Dict[str, Any],
    ) -> None:
        """Write a step result (objects and metadata) to the open cache."""
        from causaliq_workflow.cache import store_action_result

        action_class = self.action_registry.get_action_class(action_name)
        provider_name = getattr(action_class, "name", action_name)
        action_method = resolved_inputs.get("action", "default")
        metadata = {provider_name: {action_method: raw_metadata}}

        # Pass matrix key order for export directory structure
        store_action_result(
            cache=state.context.cache,
            context=state.context,
            entry_type="graph",
            metadata=metadata,
            objects=step_result.get("objects", []),
            matrix_key_order=list(state.context.matrix.keys()),
        )

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
        if step_result.get("status", "unknown") == "success":
            status = "FORCED" if state.context.mode == "force" else "EXECUTED"
        else:
            status = "FAILED"
        state.step_logger(
            action_method, step_name, status, state.context.matrix_values
        )


def _has_output(output_path: Any) -> bool:
    """Return True when an output parameter names a real destination."""
    return output_path is not None and str(output_path).lower() != "none"


def _cache_entry_exists(
    is_cache_output: bool,
    output_path: Any,
    matrix_values: Dict[str, Any],
) -> bool:
    """Return True when a .db output cache already holds the entry."""
    from pathlib import Path

    from causaliq_workflow.cache import WorkflowCache

    if not is_cache_output or not Path(output_path).exists():
        return False
    with WorkflowCache(output_path) as cache:
        return cache.exists(matrix_values)


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
            action_method, step_name, status, state.context.matrix_values
        )
