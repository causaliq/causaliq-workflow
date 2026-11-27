"""Per-job execution state shared by the workflow execution mixins.

``_JobState`` is declared separately from the execution mixins so that the
orchestrator, the step runner and the step store all depend on the state
rather than on one another.
"""

from dataclasses import dataclass, field
from typing import Any

from causaliq_workflow.registry import WorkflowContext
from causaliq_workflow.reporting import StepLogger
from causaliq_workflow.workflow.frames import WorkflowFrame


@dataclass
class _JobState:
    """Mutable state for executing a single job's steps."""

    workflow: dict[str, Any]
    job: dict[str, Any]
    context: WorkflowContext
    cli_params: dict[str, Any]
    step_logger: StepLogger | None
    variables: dict[str, Any]
    step_results: dict[str, Any] = field(default_factory=dict)
    frames: tuple[WorkflowFrame, ...] = ()
    depth: int = 0
