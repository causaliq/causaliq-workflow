"""Shared type surface for the WorkflowExecutor functional mixins.

``WorkflowExecutor`` is composed from single-responsibility mixins (matrix,
templates, patterns, filters, aggregation, validation and
execution). Each mixin calls methods and attributes provided by the others;
this base declares that shared surface so every mixin type-checks on its
own. The declarations are never executed at runtime (the mixins override
them all) and are excluded from coverage.
"""

from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

from causaliq_core import ActionPattern

from causaliq_workflow.registry import ActionRegistry
from causaliq_workflow.reporting import StepLogger

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.workflow.aggregation import AggregationConfig
    from causaliq_workflow.workflow.frames import WorkflowFrame

_StepLogger = Optional[StepLogger]


class WorkflowExecutorBase:  # pragma: no cover
    """Declares the shared WorkflowExecutor surface for the mixins."""

    action_registry: ActionRegistry

    _scan_index: Dict[str, List[Dict[str, Any]]]

    _environment: Optional[Dict[str, Any]]

    _environment_ready: bool

    _source_path: Optional[Path]

    def _invalidate_scan_index(self, cache: Any) -> None:
        """Drop the memoised scan index for a cache that was written."""
        raise NotImplementedError

    def expand_matrix(
        self, matrix: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """Expand matrix variables into individual job configurations."""
        raise NotImplementedError

    def _derive_workflow_matrix(
        self, workflow: Dict[str, Any]
    ) -> Dict[str, List[Any]]:
        """Return the effective matrix for a workflow."""
        raise NotImplementedError

    def _expand_range_value(self, value: Any) -> List[Any]:
        """Expand a range string to a list of integers."""
        raise NotImplementedError

    def _expand_matrix_values(self, values: List[Any]) -> List[Any]:
        """Expand range strings in a list of matrix values."""
        raise NotImplementedError

    def _extract_template_variables(self, text: Any) -> Set[str]:
        """Extract template variable names from a string."""
        raise NotImplementedError

    def _validate_template_variables(
        self, workflow: Dict[str, Any], parameters: Any = None
    ) -> None:
        """Validate template variables in a workflow."""
        raise NotImplementedError

    def _collect_template_variables(
        self, obj: Any, used_variables: Set[str]
    ) -> None:
        """Collect template variables from a workflow object."""
        raise NotImplementedError

    def _resolve_template_variables(
        self, obj: Any, variables: Dict[str, Any]
    ) -> Any:
        """Resolve template variables in a workflow object."""
        raise NotImplementedError

    def _resolve_step_name(
        self,
        step: Dict[str, Any],
        variables: Dict[str, Any],
        index: int,
        recorded: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Return a step's name with its tokens expanded for the job."""
        raise NotImplementedError

    def _runs_once(self, step: Dict[str, Any], matrix: Dict[str, Any]) -> bool:
        """Return True when a step runs once rather than per matrix job."""
        raise NotImplementedError

    def _is_aggregate_pattern_step(
        self, step: Dict[str, Any], workflow: Dict[str, Any]
    ) -> bool:
        """Return True when a step declares the AGGREGATE pattern."""
        raise NotImplementedError

    def _get_step_action_pattern(
        self, step: Dict[str, Any]
    ) -> Optional[ActionPattern]:
        """Return the action pattern for a step, or None."""
        raise NotImplementedError

    def _is_aggregation_step(
        self, step: Dict[str, Any], matrix: Dict[str, List[Any]]
    ) -> bool:
        """Return True when a step runs in aggregation mode."""
        raise NotImplementedError

    def _has_cache_input(self, step_inputs: Dict[str, Any]) -> bool:
        """Return True when step inputs name any cache (.db) file."""
        raise NotImplementedError

    def _flatten_metadata(
        self,
        matrix_values: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Flatten nested metadata for filter evaluation."""
        raise NotImplementedError

    def _get_aggregation_config(
        self,
        step: Dict[str, Any],
        matrix: Dict[str, List[Any]],
    ) -> Optional["AggregationConfig"]:
        """Return the aggregation config for a step, or None."""
        raise NotImplementedError

    def _scan_aggregation_inputs(
        self,
        config: "AggregationConfig",
        matrix_values: Dict[str, Any],
        logger: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Scan input caches for entries matching matrix values."""
        raise NotImplementedError

    def _missing_variable_errors(
        self, workflow: Dict[str, Any], parameters: Any = None
    ) -> List[str]:
        """Return errors for template variables that have no value."""
        raise NotImplementedError

    def _validate_workflow_actions(
        self, workflow: Dict[str, Any], mode: str
    ) -> None:
        """Validate all actions in a workflow."""
        raise NotImplementedError

    def _validate_action_patterns(self, workflow: Dict[str, Any]) -> List[str]:
        """Validate action patterns against workflow configuration."""
        raise NotImplementedError

    def _validate_step_filters(self, workflow: Dict[str, Any]) -> List[str]:
        """Validate filter expressions in workflow steps."""
        raise NotImplementedError

    def _deduplicate_errors(self, errors: List[str]) -> List[str]:
        """Deduplicate validation errors by grouping similar messages."""
        raise NotImplementedError

    def _validate_all_entries(
        self,
        workflow: Dict[str, Any],
        cli_params: Optional[Dict[str, Any]] = None,
        frames: Tuple["WorkflowFrame", ...] = (),
    ) -> List[str]:
        """Validate all entries before the execution pass."""
        raise NotImplementedError

    def _skip_nocache_step(
        self,
        state: Any,
        step: Dict[str, Any],
        step_name: str,
        resolved_inputs: Dict[str, Any],
    ) -> bool:
        """Return True when a single-run step is skipped for this job."""
        raise NotImplementedError

    def _validate_create_entries(
        self,
        step: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
    ) -> List[str]:
        """Validate CREATE pattern entries by expanding the matrix."""
        raise NotImplementedError

    def _validate_single_run_entries(
        self,
        step: Dict[str, Any],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
    ) -> List[str]:
        """Validate single-run step entries once, without a matrix."""
        raise NotImplementedError

    def _validate_aggregation_entries(
        self,
        step: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
    ) -> List[str]:
        """Validate AGGREGATE pattern entries per matrix combo."""
        raise NotImplementedError

    def _execute_jobs(
        self,
        workflow: Dict[str, Any],
        mode: str,
        cli_params: Dict[str, Any],
        step_logger: _StepLogger,
        frames: Tuple["WorkflowFrame", ...] = (),
        depth: int = 0,
    ) -> List[Dict[str, Any]]:
        """Execute every matrix job and collect the results."""
        raise NotImplementedError

    def _run_workflow_call_step(
        self, state: Any, step: Dict[str, Any], step_name: str
    ) -> bool:
        """Execute a step that calls another workflow."""
        raise NotImplementedError

    def _validate_workflow_call_step(
        self,
        step: Dict[str, Any],
        step_name: str,
        frames: Tuple["WorkflowFrame", ...] = (),
        jobs: Optional[List[Dict[str, Any]]] = None,
        workflow: Optional[Dict[str, Any]] = None,
        cli_params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Validate a step that calls another workflow."""
        raise NotImplementedError
