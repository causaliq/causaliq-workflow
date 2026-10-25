"""Per-entry validation for the execution pass."""

import warnings
from typing import Any, Dict, List, Optional, Tuple

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.aggregation import AggregationConfig
from causaliq_workflow.workflow.frames import (
    WorkflowFrame,
    is_workflow_call_step,
)
from causaliq_workflow.workflow.matrix import _runs_once
from causaliq_workflow.workflow.parameters import _parameter_errors


class EntryValidationMixin(WorkflowExecutorBase):
    """Per-entry validation for WorkflowExecutor."""

    def _validate_all_entries(
        self,
        workflow: Dict[str, Any],
        cli_params: Optional[Dict[str, Any]] = None,
        frames: Tuple[WorkflowFrame, ...] = (),
    ) -> List[str]:
        """Validate all entries (matrix combos/cache entries) before execution.

        This is the validation pass of two-pass execution. It iterates
        all entries that would be processed during execution and calls
        validate_parameters() on each. This catches:

        - Semantic filter errors (e.g., `network == asia` where 'asia'
          is undefined)
        - Invalid action parameters
        - Missing required parameters

        Pattern-specific validation:

        - CREATE: Expand matrix, validate each combination
        - AGGREGATE: Expand matrix, scan entries, validate each combo
        - single-run step: validate once, without a matrix

        Args:
            workflow: Parsed workflow dictionary
            cli_params: Additional parameters from CLI
            frames: Current workflow call stack

        Returns:
            List of validation error messages (empty if all valid)
        """
        if cli_params is None:
            cli_params = {}

        matrix = workflow.get("matrix", {})
        jobs = self.expand_matrix(matrix)
        errors: List[str] = _parameter_errors(workflow, cli_params)

        for step in workflow.get("steps", []):
            errors.extend(
                self._validate_step_entries(
                    step, jobs, matrix, workflow, cli_params, frames
                )
            )

        return errors

    def _validate_step_entries(
        self,
        step: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        matrix: Dict[str, Any],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
        frames: Tuple[WorkflowFrame, ...] = (),
    ) -> List[str]:
        """Dispatch per-entry validation for a single step by pattern."""
        step_name = step.get("name", "unnamed")
        if is_workflow_call_step(step):
            return self._validate_workflow_call_step(step, step_name, frames)
        if not step.get("uses"):
            return []

        step_inputs = step.get("with", {})
        if not step_inputs.get("action"):
            return [f"Step '{step_name}': Missing 'action' parameter"]

        if self._is_aggregation_step(step, matrix):
            return self._validate_aggregation_entries(
                step, jobs, workflow, cli_params
            )
        if _runs_once(step, matrix):
            return self._validate_single_run_entries(
                step, workflow, cli_params
            )
        return self._validate_create_entries(step, jobs, workflow, cli_params)

    def _validate_create_entries(
        self,
        step: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
    ) -> List[str]:
        """Validate CREATE pattern entries by expanding matrix.

        Validates parameters for each matrix combination.

        Args:
            step: Step configuration dictionary
            jobs: Expanded matrix combinations
            workflow: Full workflow dictionary
            cli_params: CLI parameters

        Returns:
            List of validation error messages
        """
        errors: List[str] = []
        step_name = step.get("name", "unnamed")
        provider_name = str(step.get("uses", ""))
        step_inputs = step.get("with", {})

        for job in jobs:
            error = self._validate_create_entry(
                step_name,
                provider_name,
                step_inputs,
                job,
                workflow,
                cli_params,
            )
            if error:
                errors.append(error)

        return errors

    def _validate_create_entry(
        self,
        step_name: str,
        provider_name: str,
        step_inputs: Dict[str, Any],
        job: Dict[str, Any],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
    ) -> Optional[str]:
        """Validate one CREATE entry, returning an error message or None."""
        from causaliq_core import ActionValidationError

        variables = {**workflow, **job, **cli_params}
        resolved_inputs = self._resolve_template_variables(
            step_inputs, variables
        )

        # Add implicit matrix variables
        for matrix_var, matrix_val in job.items():
            if matrix_var not in resolved_inputs:
                resolved_inputs[matrix_var] = matrix_val

        try:
            self.action_registry.validate_action_parameters(
                provider_name, resolved_inputs
            )
        except ActionValidationError as e:
            return f"Step '{step_name}': {e}"
        return None

    def _validate_single_run_entries(
        self,
        step: Dict[str, Any],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
    ) -> List[str]:
        """Validate single-run step entries (once, without matrix).

        Single-run steps write no workflow cache and do not use the
        workflow matrix, so their parameters are validated a single time
        with no implicit matrix variables added.

        Args:
            step: Step configuration dictionary
            workflow: Full workflow dictionary
            cli_params: CLI parameters

        Returns:
            List of validation error messages
        """
        from causaliq_core import ActionValidationError

        errors: List[str] = []
        step_name = step.get("name", "unnamed")
        provider_name = str(step.get("uses", ""))
        step_inputs = step.get("with", {})

        variables = {**workflow, **cli_params}
        resolved_inputs = self._resolve_template_variables(
            step_inputs, variables
        )

        try:
            self.action_registry.validate_action_parameters(
                provider_name, resolved_inputs
            )
        except ActionValidationError as e:
            errors.append(f"Step '{step_name}': {e}")

        return errors

    def _validate_aggregation_entries(
        self,
        step: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
    ) -> List[str]:
        """Validate AGGREGATE pattern entries.

        Validates parameters for each matrix combination, scanning input
        caches for matching entries.

        Args:
            step: Step configuration dictionary
            jobs: Expanded matrix combinations
            workflow: Full workflow dictionary
            cli_params: CLI parameters

        Returns:
            List of validation error messages
        """
        errors: List[str] = []
        step_name = step.get("name", "unnamed")
        matrix = workflow.get("matrix", {})
        agg_config = self._get_aggregation_config(step, matrix)

        # Track entry fingerprints per output matrix combo to
        # detect silent duplication (different combos producing
        # identical aggregation input sets).
        fingerprints: Dict[frozenset, Dict[str, Any]] = {}

        for job in jobs:
            variables = {**workflow, **job, **cli_params}
            resolved_inputs = self._resolve_template_variables(
                step.get("with", {}), variables
            )
            self._apply_aggregation_scan(
                agg_config, resolved_inputs, job, step_name, fingerprints
            )
            error = self._step_parameter_error(
                str(step.get("uses", "")), resolved_inputs, step_name
            )
            if error:
                errors.append(error)

        return errors

    def _apply_aggregation_scan(
        self,
        agg_config: Optional[AggregationConfig],
        resolved_inputs: Dict[str, Any],
        job: Dict[str, Any],
        step_name: str,
        fingerprints: Dict[frozenset, Dict[str, Any]],
    ) -> None:
        """Scan inputs for a matrix combo and record its fingerprint.

        AGGREGATE steps receive their matched entries through the
        ``_aggregation_entries`` parameter rather than implicit matrix
        variables.
        """
        if agg_config is None:  # pragma: no cover - always set here
            return
        matching_entries = self._scan_aggregation_for(
            agg_config, resolved_inputs, job
        )
        resolved_inputs["_aggregation_entries"] = matching_entries
        resolved_inputs.pop("aggregate", None)
        _check_aggregation_fingerprint(
            step_name, job, matching_entries, fingerprints
        )

    def _scan_aggregation_for(
        self,
        agg_config: AggregationConfig,
        resolved_inputs: Dict[str, Any],
        job: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Scan aggregation inputs using the resolved filter expression."""
        resolved_filter = resolved_inputs.get("filter")
        scan_config = agg_config
        if resolved_filter != agg_config.filter_expr:
            scan_config = AggregationConfig(
                input_caches=agg_config.input_caches,
                filter_expr=resolved_filter,
                matrix_vars=agg_config.matrix_vars,
            )
        return self._scan_aggregation_inputs(scan_config, job)

    def _step_parameter_error(
        self,
        provider_name: str,
        inputs: Dict[str, Any],
        step_name: str,
    ) -> Optional[str]:
        """Return an action parameter validation error, or None."""
        from causaliq_core import ActionValidationError

        try:
            self.action_registry.validate_action_parameters(
                provider_name, inputs
            )
        except ActionValidationError as e:
            return f"Step '{step_name}': {e}"
        return None


def _check_aggregation_fingerprint(
    step_name: str,
    job: Dict[str, Any],
    matching_entries: List[Dict[str, Any]],
    fingerprints: Dict[frozenset, Dict[str, Any]],
) -> None:
    """Warn when different matrix combos select identical entries.

    Builds a fingerprint from matched entry hashes. Empty sets are
    skipped — the input cache may not exist yet (created by an earlier
    step). A repeated fingerprint warns that the differing dimension(s)
    may need a filter or should be removed from the matrix.
    """
    fp = frozenset(
        entry.get("entry_hash", id(entry)) for entry in matching_entries
    )
    if not fp:
        return
    if fp not in fingerprints:
        fingerprints[fp] = job
        return

    prev = fingerprints[fp]
    diff = {
        key: (prev[key], job[key]) for key in job if job[key] != prev.get(key)
    }
    warnings.warn(
        f"Step '{step_name}': matrix combos"
        f" differ only in {diff} but"
        f" select identical aggregation"
        f" entries — the differing"
        f" dimension(s) may need a filter"
        f" or should be removed from the"
        f" matrix",
        stacklevel=1,
    )
