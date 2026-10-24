"""Calling another CausalIQ workflow from a step.

A step whose ``uses`` value is a relative path invokes the named YAML
workflow instead of an action provider. Parameters are accepted in the
caller's ``with`` block but are not yet forwarded to the called
workflow; see ``docs/userguide/subworkflows.md``.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from causaliq_workflow.schema import (
    WorkflowValidationError,
    load_workflow_file,
    validate_workflow,
)
from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.frames import (
    WorkflowFrame,
    find_recursive_frame,
    format_call_chain,
    has_workflow_suffix,
    resolve_call_target,
    workflow_frame,
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

        The step runs once per workflow: a call has no cache output of
        its own, and parameters are not yet forwarded, so repeating it
        for every matrix job would produce identical results.

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
        child = self._load_child_workflow(target, step_name)
        results = self._execute_child_workflow(child, target, state)
        summary = _summarise_call(target, results, state.context.mode)
        state.step_results[step_name] = summary
        return True

    def _execute_child_workflow(
        self,
        child: Dict[str, Any],
        target: Path,
        state: "_JobState",
    ) -> List[Dict[str, Any]]:
        """Execute a called workflow's jobs with an extended call stack.

        Args:
            child: Parsed and validated child workflow.
            target: Canonical path of the child workflow.
            state: Per-job execution state of the calling workflow.

        Returns:
            Job results produced by the child workflow.
        """
        frames = state.frames + (workflow_frame(target),)
        return self._execute_jobs(
            child, state.context.mode, {}, state.step_logger, frames
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
        self, target: Path, step_name: str
    ) -> Dict[str, Any]:
        """Load and structurally validate a called workflow.

        Args:
            target: Canonical path of the called workflow.
            step_name: Step name used in error messages.

        Returns:
            Parsed and validated child workflow.

        Raises:
            WorkflowExecutionError: If the child cannot be loaded or is
                not a valid CausalIQ workflow.
        """
        try:
            child = load_workflow_file(target)
            validate_workflow(child)
            self._validate_template_variables(child)
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
    ) -> List[str]:
        """Validate a call step, recursing into the called workflow.

        Args:
            step: Step configuration declaring the call.
            step_name: Step name used in error messages.
            frames: Current call stack.

        Returns:
            Validation errors, empty when the call is valid.
        """
        errors = _reserved_parameter_errors(step, step_name)
        if errors:
            return errors
        try:
            target = self._workflow_call_target(step, step_name, frames)
            child = self._load_child_workflow(target, step_name)
        except WorkflowExecutionError as e:
            return [str(e)]
        child_frames = frames + (workflow_frame(target),)
        required_errors = self._required_variable_errors(child, step_name)
        if required_errors:
            return required_errors
        return self._validate_all_entries(child, {}, child_frames)

    def _required_variable_errors(
        self, child: Dict[str, Any], step_name: str
    ) -> List[str]:
        """Return errors for child variables the caller must provide.

        Parameters are not forwarded yet, so a called workflow cannot
        satisfy a required (``None``) variable.

        Args:
            child: Parsed child workflow.
            step_name: Step name used in error messages.

        Returns:
            Validation errors, empty when the child is self-contained.
        """
        try:
            self._validate_required_variables(child, {})
        except WorkflowExecutionError as e:
            return [f"Step '{step_name}': {e}"]
        return []


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
    target: Path, results: List[Dict[str, Any]], mode: str
) -> Dict[str, Any]:
    """Build the step result recorded for a workflow call."""
    steps = _collect_child_steps(results)
    errors = _call_errors(steps)
    summary: Dict[str, Any] = {
        "status": _call_status(steps, errors, mode),
        "workflow": str(target),
        "jobs": len(results),
        "steps": steps,
    }
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
