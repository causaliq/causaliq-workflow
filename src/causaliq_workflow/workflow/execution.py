"""Workflow parsing and job execution entry points.

The execution mixin parses, validates and sequences a workflow's jobs.
Running one step lives in :mod:`causaliq_workflow.workflow.step_runner` and
cache writes in :mod:`causaliq_workflow.workflow.step_store`; the state they
share is declared in :mod:`causaliq_workflow.workflow.job_state`.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from causaliq_workflow.registry import WorkflowContext
from causaliq_workflow.reporting import StepLogger
from causaliq_workflow.schema import WorkflowValidationError
from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.filters import relax_step_filter_literals
from causaliq_workflow.workflow.frames import WorkflowFrame, root_frames
from causaliq_workflow.workflow.job_state import _JobState
from causaliq_workflow.workflow.matrix import _bind_parameters


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
        step_logger: Optional[StepLogger] = None,
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
                (action_method, step_name, status, matrix_values). The
                optional ``depth`` and ``detail`` keyword arguments carry
                the workflow nesting depth and a trailing detail fragment.
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
        step_logger: Optional[StepLogger],
        frames: Tuple[WorkflowFrame, ...] = (),
        depth: int = 0,
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
                    workflow,
                    job,
                    context,
                    cli_params,
                    step_logger,
                    frames,
                    depth=depth,
                )
            )

        return results

    def _execute_job(
        self,
        workflow: Dict[str, Any],
        job: Dict[str, Any],
        context: WorkflowContext,
        cli_params: Dict[str, Any],
        step_logger: Optional[StepLogger] = None,
        frames: Tuple[WorkflowFrame, ...] = (),
        depth: int = 0,
    ) -> Dict[str, Any]:
        """Execute single job with resolved matrix variables.

        Args:
            workflow: Base workflow configuration
            job: Job with resolved matrix variables
            context: Workflow context
            cli_params: CLI parameters
            step_logger: Optional function to log step execution
            frames: Call stack leading to this workflow
            depth: Workflow nesting depth (0 for the top-level workflow)

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
            depth=depth,
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
