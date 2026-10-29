"""Workflow parsing and execution entry points."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from causaliq_workflow.registry import WorkflowContext
from causaliq_workflow.schema import WorkflowValidationError
from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.aggregation import AggregationConfig
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.filters import relax_step_filter_literals
from causaliq_workflow.workflow.frames import (
    WorkflowFrame,
    is_workflow_call_step,
    root_frames,
)
from causaliq_workflow.workflow.matrix import (
    _bind_parameters,
    _cache_entry_exists,
)
from causaliq_workflow.workflow.provenance import (
    build_result_metadata,
    collect_environment,
    execute_with_provenance,
)


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
    frames: Tuple[WorkflowFrame, ...] = ()


class ExecutionMixin(WorkflowExecutorBase):
    """Parsing and execution for WorkflowExecutor."""

    def parse_workflow(
        self,
        workflow_path: Union[str, Path],
        mode: str = "dry-run",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Parse workflow YAML file with validation.

        Args:
            workflow_path: Path to workflow YAML file
            mode: Execution mode for action validation
            parameters: Parameter names supplied by the CLI, so a workflow
                may reference them in its templates before execution

        Returns:
            Parsed and validated workflow dictionary

        Raises:
            WorkflowExecutionError: If workflow parsing or validation fails
        """
        from causaliq_workflow import workflow as _workflow_module

        try:
            workflow = relax_step_filter_literals(
                _workflow_module.load_workflow_file(workflow_path),
                parameters or (),
            )
            _workflow_module.validate_workflow(workflow)
            self._validate_template_variables(workflow, set(parameters or ()))

            # Validate all actions exist and can run
            self._validate_workflow_actions(workflow, mode)

            self._source_path = Path(workflow_path)
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
        validate: bool = True,
        source_path: Optional[Union[str, Path]] = None,
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
            validate: When True (default) run the validation pass first.
                Set False when the caller has already validated the same
                workflow to avoid a redundant pass.
            source_path: Path of the workflow file used to resolve
                relative calls to other workflows. Defaults to the last
                workflow parsed by this executor.

        Returns:
            List of job results from matrix expansion

        Raises:
            WorkflowExecutionError: If validation or execution fails
        """
        workflow, cli_params = _bind_parameters(workflow, cli_params or {})
        workflow = relax_step_filter_literals(workflow, cli_params or {})
        frames = root_frames(source_path or self._source_path)

        try:
            if validate:
                self._validate_execution(workflow, cli_params, frames)

            # Validate-only mode: skip execution pass
            if mode == "validate":
                return []

            return self._execute_jobs(
                workflow, mode, cli_params, step_logger, frames
            )

        except WorkflowExecutionError:
            # Re-raise our own errors without wrapping
            raise
        except Exception as e:
            raise WorkflowExecutionError(
                f"Workflow execution failed: {e}"
            ) from e

    def _validate_execution(
        self,
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
        frames: Tuple[WorkflowFrame, ...] = (),
    ) -> None:
        """Run the validation pass, raising on the first failure."""
        validation_errors = self._validate_all_entries(
            workflow, cli_params, frames
        )
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
        frames: Tuple[WorkflowFrame, ...] = (),
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
                    workflow, job, context, cli_params, step_logger, frames
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
        frames: Tuple[WorkflowFrame, ...] = (),
    ) -> Dict[str, Any]:
        """Execute single job with resolved matrix variables.

        Args:
            workflow: Base workflow configuration
            job: Job with resolved matrix variables
            context: Workflow context
            cli_params: CLI parameters
            step_logger: Optional function to log step execution
            frames: Call stack leading to this workflow

        Returns:
            Job execution results

        """
        # Combine all variable sources for template resolution
        state = _JobState(
            workflow=workflow,
            job=job,
            context=context,
            cli_params=cli_params,
            step_logger=step_logger,
            variables={**workflow, **job, **cli_params},
            frames=frames,
        )

        for step in workflow.get("steps", []):
            self._run_step(state, step)

        return {
            "job": job,
            "steps": state.step_results,
            "context": context,
        }

    def _run_step(self, state: _JobState, step: Dict[str, Any]) -> None:
        """Execute a single step, then restore the job's matrix values.

        The step name is expanded for the current job, so a matrix value
        in the name yields a distinct name for each combination.
        """
        step_name = self._resolve_step_name(
            step, state.variables, len(state.step_results), state.step_results
        )

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
            entry_type="graph",
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
            action_method, step_name, status, state.context.matrix_values
        )


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
            action_method, step_name, status, state.context.matrix_values
        )
