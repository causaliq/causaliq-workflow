"""Calling another CausalIQ workflow from a step.

A step whose ``uses`` value is a relative path invokes the named YAML
workflow instead of an action provider. Values in the caller's ``with``
block become parameters of the called workflow; see
``docs/userguide/subworkflows.md``.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from causaliq_workflow.schema import (
    WorkflowValidationError,
    load_workflow_file,
    validate_workflow,
)
from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.filters import relax_step_filter_literals
from causaliq_workflow.workflow.frames import (
    WorkflowFrame,
    find_recursive_frame,
    format_call_chain,
    has_workflow_suffix,
    resolve_call_target,
    workflow_frame,
)
from causaliq_workflow.workflow.matrix import _bind_parameters
from causaliq_workflow.workflow.parameters import (
    _single_token,
    _unknown_parameter_errors,
)

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.workflow.execution import _JobState

_RESERVED_PARAMETERS = ("action", "output")
_FAILURE_STATUSES = ("error", "failed")


class SubWorkflowMixin(WorkflowExecutorBase):
    """Workflow-call steps for WorkflowExecutor."""

    def _run_workflow_call_step(
        self, state: "_JobState", step: Dict[str, Any], step_name: str
    ) -> bool:
        """Execute a called workflow and record its summary.

        The step runs once per workflow unless its parameters reference a
        matrix variable of the calling workflow, in which case it runs
        once per matrix combination.

        Args:
            state: Per-job execution state.
            step: Step configuration declaring the call.
            step_name: Step name used in logs and results.

        Returns:
            True when the child workflow ran, False when the step was
            skipped for this matrix job.
        """
        label = {"action": str(step.get("uses", ""))}
        if self._skip_nocache_step(state, step, step_name, label):
            return False
        target = self._workflow_call_target(step, step_name, state.frames)
        _log_call_start(state, step, step_name)
        parameters = self._resolve_parameter_values(
            step.get("with", {}), state.variables
        )
        child = self._load_child_workflow(target, step_name, set(parameters))
        child, variables = _bind_parameters(child, parameters)
        results = self._execute_child_workflow(child, target, state, variables)
        summary = _summarise_call(
            target, results, state.context.mode, parameters
        )
        state.step_results[step_name] = summary
        return True

    def _resolve_parameter_values(
        self, values: Dict[str, Any], variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve a call step's ``with`` values in the caller's context.

        A value that is exactly one ``{{name}}`` token keeps the bound
        value's native type, so a matrix override does not turn a number
        into a string.

        Args:
            values: Raw parameter values from the call step.
            variables: Caller variables used for substitution.

        Returns:
            Resolved parameter values.
        """
        return {
            name: self._resolve_parameter_value(value, variables)
            for name, value in values.items()
        }

    def _resolve_parameter_value(
        self, value: Any, variables: Dict[str, Any]
    ) -> Any:
        """Resolve one parameter value in the caller's context."""
        token = _single_token(value)
        if token is not None and token in variables:
            return variables[token]
        return self._resolve_template_variables(value, variables)

    def _execute_child_workflow(
        self,
        child: Dict[str, Any],
        target: Path,
        state: "_JobState",
        variables: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Execute a called workflow's jobs with an extended call stack.

        Args:
            child: Parsed and validated child workflow.
            target: Canonical path of the child workflow.
            state: Per-job execution state of the calling workflow.
            variables: Bound parameters that are not matrix overrides.

        Returns:
            Job results produced by the child workflow.
        """
        frames = state.frames + (workflow_frame(target),)
        return self._execute_jobs(
            child, state.context.mode, variables, state.step_logger, frames
        )

    def _workflow_call_target(
        self,
        step: Dict[str, Any],
        step_name: str,
        frames: Tuple[WorkflowFrame, ...],
    ) -> Path:
        """Resolve a call step's target and reject recursive calls.

        Args:
            step: Step configuration declaring the call.
            step_name: Step name used in error messages.
            frames: Current call stack.

        Returns:
            Canonical path of the called workflow.

        Raises:
            WorkflowExecutionError: If the target is not a YAML workflow
                or the call would recurse.
        """
        uses = str(step.get("uses", ""))
        if not has_workflow_suffix(uses):
            raise WorkflowExecutionError(
                f"Step '{step_name}': workflow call target must be a "
                f".yml or .yaml file, got '{uses}'"
            )
        target = resolve_call_target(uses, frames)
        if find_recursive_frame(target, frames) is not None:
            raise WorkflowExecutionError(
                f"Step '{step_name}': recursive workflow call detected: "
                f"{format_call_chain(frames, target)}"
            )
        return target

    def _load_child_workflow(
        self,
        target: Path,
        step_name: str,
        parameter_names: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Load and structurally validate a called workflow.

        Args:
            target: Canonical path of the called workflow.
            step_name: Step name used in error messages.
            parameter_names: Parameter names the caller supplies, which
                the child may reference in its templates.

        Returns:
            Parsed and validated child workflow.

        Raises:
            WorkflowExecutionError: If the child cannot be loaded or is
                not a valid CausalIQ workflow.
        """
        try:
            child = load_workflow_file(target)
            child = relax_step_filter_literals(child, parameter_names or ())
            validate_workflow(child)
            self._validate_template_variables(
                child, set(parameter_names or ())
            )
            self._validate_workflow_actions(child, "validate")
        except (WorkflowValidationError, WorkflowExecutionError) as e:
            raise WorkflowExecutionError(
                f"Step '{step_name}' (workflow '{target.name}'): {e}"
            ) from e
        return child

    def _validate_workflow_call_step(
        self,
        step: Dict[str, Any],
        step_name: str,
        frames: Tuple[WorkflowFrame, ...] = (),
        jobs: Optional[List[Dict[str, Any]]] = None,
        workflow: Optional[Dict[str, Any]] = None,
        cli_params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Validate a call step, recursing into the called workflow.

        The call's ``with`` values are resolved in the caller's context
        first, so a forwarded matrix value or declared parameter reaches
        the child as a value rather than as a ``{{placeholder}}``.

        Args:
            step: Step configuration declaring the call.
            step_name: Step name used in error messages.
            frames: Current call stack.
            jobs: Expanded matrix combinations of the calling workflow.
            workflow: Calling workflow dictionary.
            cli_params: Parameters supplied by the CLI.

        Returns:
            Validation errors, empty when the call is valid.
        """
        errors = _reserved_parameter_errors(step, step_name)
        if errors:
            return errors
        raw = step.get("with", {})
        try:
            target = self._workflow_call_target(step, step_name, frames)
            child = self._load_child_workflow(target, step_name, set(raw))
        except WorkflowExecutionError as exc:
            return [str(exc)]
        parameters = self._resolve_call_parameters(
            raw, jobs, workflow, cli_params
        )
        errors = _call_parameter_errors(
            step_name, target.name, parameters, child
        )
        if errors:
            return errors
        return self._validate_bound_child(child, parameters, target, frames)

    def _resolve_call_parameters(
        self,
        raw: Dict[str, Any],
        jobs: Optional[List[Dict[str, Any]]],
        workflow: Optional[Dict[str, Any]],
        cli_params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Resolve a call's parameters as the first job will pass them.

        Args:
            raw: Unresolved ``with`` values from the call step.
            jobs: Expanded matrix combinations of the calling workflow.
            workflow: Calling workflow dictionary.
            cli_params: Parameters supplied by the CLI.

        Returns:
            Resolved parameter values, one mapping per validation pass.
        """
        job = jobs[0] if jobs else {}
        variables = {**(workflow or {}), **job, **(cli_params or {})}
        return self._resolve_parameter_values(raw, variables)

    def _validate_bound_child(
        self,
        child: Dict[str, Any],
        parameters: Dict[str, Any],
        target: Path,
        frames: Tuple[WorkflowFrame, ...],
    ) -> List[str]:
        """Validate a called workflow as the call will bind it."""
        bound, variables = _bind_parameters(child, parameters)
        child_frames = frames + (workflow_frame(target),)
        return self._validate_all_entries(bound, variables, child_frames)


def _call_parameter_errors(
    step_name: str,
    target_name: str,
    parameters: Dict[str, Any],
    child: Dict[str, Any],
) -> List[str]:
    """Return parameter binding errors for a call step.

    A child placeholder that the caller does not satisfy is reported
    when the child workflow is loaded, because an undeclared placeholder
    is a required parameter.

    Args:
        step_name: Calling step name used in error messages.
        target_name: Called workflow file name used in error messages.
        parameters: Parameter values from the call step.
        child: Parsed child workflow.

    Returns:
        Validation errors, empty when every parameter binds.
    """
    errors = _unknown_parameter_errors(
        parameters, child, workflow_label=target_name
    )
    return [f"Step '{step_name}': {error}" for error in errors]


def _reserved_parameter_errors(
    step: Dict[str, Any], step_name: str
) -> List[str]:
    """Return errors for parameters reserved by the executor.

    Args:
        step: Step configuration declaring the call.
        step_name: Step name used in error messages.

    Returns:
        One error per reserved parameter present in ``with``.
    """
    parameters = step.get("with", {})
    return [
        f"Step '{step_name}': workflow calls do not support "
        f"'{key}' in 'with'"
        for key in _RESERVED_PARAMETERS
        if key in parameters
    ]


def _collect_child_steps(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Collect a summary of every step run by the child workflow."""
    steps: List[Dict[str, Any]] = []
    for result in results:
        for name, step in result.get("steps", {}).items():
            steps.append({"name": name, **_step_summary(step)})
    return steps


def _step_summary(step: Dict[str, Any]) -> Dict[str, Any]:
    """Return the reporting fields of a child step result."""
    fields = ("status", "reason", "errors")
    return {key: step[key] for key in fields if key in step}


def _call_errors(steps: List[Dict[str, Any]]) -> List[str]:
    """Return failure messages from child step results."""
    return [
        f"{step.get('name')}: {step.get('reason', 'failed')}"
        for step in steps
        if step.get("status") in _FAILURE_STATUSES
    ]


def _dry_run_status(steps: List[Dict[str, Any]]) -> str:
    """Return the dry-run status implied by child step results."""
    statuses = {step.get("status") for step in steps}
    return "would_execute" if "would_execute" in statuses else "would_skip"


def _call_status(
    steps: List[Dict[str, Any]], errors: List[str], mode: str
) -> str:
    """Return the overall status of a workflow call step."""
    if errors:
        return "error"
    if mode == "dry-run":
        return _dry_run_status(steps)
    return "success"


def _summarise_call(
    target: Path,
    results: List[Dict[str, Any]],
    mode: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the step result recorded for a workflow call.

    Args:
        target: Canonical path of the called workflow.
        results: Job results produced by the child workflow.
        mode: Caller's execution mode.
        parameters: Parameters bound for this call.

    Returns:
        Step result dictionary describing the call.
    """
    steps = _collect_child_steps(results)
    errors = _call_errors(steps)
    summary: Dict[str, Any] = {
        "status": _call_status(steps, errors, mode),
        "workflow": str(target),
        "jobs": len(results),
        "steps": steps,
    }
    if parameters:
        summary["parameters"] = parameters
    if errors:
        summary["errors"] = errors
    return summary


def _log_call_start(
    state: "_JobState", step: Dict[str, Any], step_name: str
) -> None:
    """Announce a workflow call before its steps are logged."""
    if not state.step_logger:
        return
    state.step_logger(str(step.get("uses", "")), step_name, "CALLING", {})
