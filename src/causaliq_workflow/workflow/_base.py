"""Shared type surface for the WorkflowExecutor functional mixins.

``WorkflowExecutor`` is composed from single-responsibility mixins (matrix,
templates, patterns, filters, entry scan, step runner, step store,
validation and execution). Each mixin calls methods and attributes provided
by the others; this base declares that shared surface so every mixin
type-checks on its own. The declarations are never executed at runtime (the
mixins override them all) and are excluded from coverage.
"""

from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Set,
)

from causaliq_core import ActionPattern

from causaliq_workflow.registry import ActionRegistry
from causaliq_workflow.reporting import StepLogger

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.workflow.entry_scan import AggregationConfig
    from causaliq_workflow.workflow.frames import WorkflowFrame

_StepLogger = StepLogger | None


class WorkflowExecutorBase:  # pragma: no cover
    """Declares the shared WorkflowExecutor surface for the mixins."""

    action_registry: ActionRegistry

    _scan_index: dict[str, list[dict[str, Any]]]

    _environment: dict[str, Any] | None

    _environment_ready: bool

    _source_path: Path | None

    def _invalidate_scan_index(self, cache: Any) -> None:
        """Drop the memoised scan index for a cache that was written."""
        raise NotImplementedError

    def expand_matrix(
        self, matrix: dict[str, list[Any]]
    ) -> list[dict[str, Any]]:
        """Expand matrix variables into individual job configurations."""
        raise NotImplementedError

    def _derive_workflow_matrix(
        self,
        workflow: dict[str, Any],
        variables: dict[str, Any] | None = None,
    ) -> dict[str, list[Any]]:
        """Return the effective matrix for a workflow."""
        raise NotImplementedError

    def _expand_range_value(self, value: Any) -> list[Any]:
        """Expand a range string to a list of integers."""
        raise NotImplementedError

    def _expand_matrix_values(self, values: list[Any]) -> list[Any]:
        """Expand range strings in a list of matrix values."""
        raise NotImplementedError

    def _extract_template_variables(self, text: Any) -> Set[str]:
        """Extract template variable names from a string."""
        raise NotImplementedError

    def _validate_template_variables(
        self, workflow: dict[str, Any], parameters: Any = None
    ) -> None:
        """Validate template variables in a workflow."""
        raise NotImplementedError

    def _collect_template_variables(
        self, obj: Any, used_variables: Set[str]
    ) -> None:
        """Collect template variables from a workflow object."""
        raise NotImplementedError

    def _resolve_template_variables(
        self, obj: Any, variables: dict[str, Any]
    ) -> Any:
        """Resolve template variables in a workflow object."""
        raise NotImplementedError

    def _resolved_step_inputs(
        self, step: dict[str, Any], variables: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Return a step's inputs with known templates resolved."""
        raise NotImplementedError

    def _resolve_step_name(
        self,
        step: dict[str, Any],
        variables: dict[str, Any],
        index: int,
        recorded: dict[str, Any] | None = None,
    ) -> str:
        """Return a step's name with its tokens expanded for the job."""
        raise NotImplementedError

    def _runs_once(self, step: dict[str, Any], matrix: dict[str, Any]) -> bool:
        """Return True when a step runs once rather than per matrix job."""
        raise NotImplementedError

    def _is_aggregate_pattern_step(
        self, step: dict[str, Any], workflow: dict[str, Any]
    ) -> bool:
        """Return True when a step groups input cache entries."""
        raise NotImplementedError

    def _get_step_action_pattern(
        self, step: dict[str, Any]
    ) -> ActionPattern | None:
        """Return the action pattern for a step, or None."""
        raise NotImplementedError

    def _is_entry_scan_step(
        self,
        step: dict[str, Any],
        matrix: dict[str, list[Any]],
        variables: dict[str, Any] | None = None,
    ) -> bool:
        """Return True when a step is given matched cache entries."""
        raise NotImplementedError

    def _map_arity_error(
        self,
        step_name: str,
        step: dict[str, Any],
        entries: list[Any],
        allow_empty: bool = False,
    ) -> str | None:
        """Return an error when a MAP step did not match exactly one entry."""
        raise NotImplementedError

    def _map_input_key_error(
        self,
        step_name: str,
        step: dict[str, Any],
        agg_config: "AggregationConfig | None",
    ) -> str | None:
        """Return an error when a MAP step input caches disagree on keys."""
        raise NotImplementedError

    def _has_cache_input(self, step_inputs: dict[str, Any]) -> bool:
        """Return True when step inputs name any cache (.db) file."""
        raise NotImplementedError

    def _get_entry_scan_config(
        self,
        step: dict[str, Any],
        matrix: dict[str, list[Any]],
        variables: dict[str, Any] | None = None,
    ) -> "AggregationConfig | None":
        """Return the entry-scan config for a step, or None."""
        raise NotImplementedError

    def _scan_input_entries(
        self,
        config: "AggregationConfig",
        matrix_values: dict[str, Any],
        logger: Callable[[str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Scan input caches for entries matching matrix values."""
        raise NotImplementedError

    def _resolved_entry_scan_config(
        self,
        config: "AggregationConfig",
        resolved_inputs: dict[str, Any],
    ) -> "AggregationConfig":
        """Return the scan config with step templates substituted."""
        raise NotImplementedError

    def _missing_variable_errors(
        self, workflow: dict[str, Any], parameters: Any = None
    ) -> list[str]:
        """Return errors for template variables that have no value."""
        raise NotImplementedError

    def _validate_workflow_actions(
        self, workflow: dict[str, Any], mode: str
    ) -> None:
        """Validate all actions in a workflow."""
        raise NotImplementedError

    def _validate_action_patterns(self, workflow: dict[str, Any]) -> list[str]:
        """Validate action patterns against workflow configuration."""
        raise NotImplementedError

    def _validate_step_filters(self, workflow: dict[str, Any]) -> list[str]:
        """Validate filter expressions in workflow steps."""
        raise NotImplementedError

    def _deduplicate_errors(self, errors: list[str]) -> list[str]:
        """Deduplicate validation errors by grouping similar messages."""
        raise NotImplementedError

    def _validate_all_entries(
        self,
        workflow: dict[str, Any],
        cli_params: dict[str, Any] | None = None,
        frames: tuple["WorkflowFrame", ...] = (),
    ) -> list[str]:
        """Validate all entries before the execution pass."""
        raise NotImplementedError

    def _skip_nocache_step(
        self,
        state: Any,
        step: dict[str, Any],
        step_name: str,
        resolved_inputs: dict[str, Any],
    ) -> bool:
        """Return True when a single-run step is skipped for this job."""
        raise NotImplementedError

    def _run_action_step(
        self, state: Any, step: dict[str, Any], step_name: str
    ) -> bool:
        """Execute a step's action or workflow call."""
        raise NotImplementedError

    def _get_environment(self) -> dict[str, Any] | None:
        """Return the run environment, collecting it at most once."""
        raise NotImplementedError

    def _store_step_result(
        self,
        state: Any,
        step_result: dict[str, Any],
        provenance: dict[str, Any],
    ) -> None:
        """Store a step result in the open cache when appropriate."""
        raise NotImplementedError

    def _log_step_completion(
        self,
        state: Any,
        step_name: str,
        resolved_inputs: dict[str, Any],
        step_result: dict[str, Any],
        provenance: dict[str, Any],
    ) -> None:
        """Log a step's completion status when a logger is present."""
        raise NotImplementedError

    def _validate_create_entries(
        self,
        step: dict[str, Any],
        jobs: list[dict[str, Any]],
        workflow: dict[str, Any],
        cli_params: dict[str, Any],
    ) -> list[str]:
        """Validate templating step entries by expanding the matrix."""
        raise NotImplementedError

    def _validate_single_run_entries(
        self,
        step: dict[str, Any],
        workflow: dict[str, Any],
        cli_params: dict[str, Any],
    ) -> list[str]:
        """Validate single-run step entries once, without a matrix."""
        raise NotImplementedError

    def _validate_entry_scan_entries(
        self,
        step: dict[str, Any],
        jobs: list[dict[str, Any]],
        workflow: dict[str, Any],
        cli_params: dict[str, Any],
    ) -> list[str]:
        """Validate cache-reading step entries per matrix combination."""
        raise NotImplementedError

    def _execute_jobs(
        self,
        workflow: dict[str, Any],
        mode: str,
        cli_params: dict[str, Any],
        step_logger: _StepLogger,
        frames: tuple["WorkflowFrame", ...] = (),
        depth: int = 0,
    ) -> list[dict[str, Any]]:
        """Execute every matrix job and collect the results."""
        raise NotImplementedError

    def _run_workflow_call_step(
        self, state: Any, step: dict[str, Any], step_name: str
    ) -> bool:
        """Execute a step that calls another workflow."""
        raise NotImplementedError

    def _validate_workflow_call_step(
        self,
        step: dict[str, Any],
        step_name: str,
        frames: tuple["WorkflowFrame", ...] = (),
        jobs: list[dict[str, Any]] | None = None,
        workflow: dict[str, Any] | None = None,
        cli_params: dict[str, Any] | None = None,
    ) -> list[str]:
        """Validate a step that calls another workflow."""
        raise NotImplementedError
