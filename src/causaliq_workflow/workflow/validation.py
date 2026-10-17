"""Workflow and action configuration validation."""

import re
from typing import Any, Dict, List, Optional, Set

from causaliq_core import ActionPattern

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.matrix import _runs_once

_SKIP_KEYS = {"id", "description", "matrix", "steps"}


def _is_required_variable(
    key: str, value: Any, cli_params: Dict[str, Any]
) -> bool:
    """Return True when a None workflow variable is missing from the CLI."""
    if key in _SKIP_KEYS:
        return False
    return value is None and key not in cli_params


def _check_filter_expression(
    step_name: str, filter_expr: Any
) -> Optional[str]:
    """Validate a filter expression, returning an error message or None."""
    from causaliq_core.utils import FilterSyntaxError, validate_filter

    try:
        validate_filter(filter_expr)
    except (FilterSyntaxError, TypeError) as e:
        return f"Step '{step_name}': {e}"
    return None


def _add_unique_error(
    error: str,
    pattern: re.Pattern[str],
    seen: Set[tuple[str, str]],
    result: List[str],
) -> None:
    """Append an error to result unless it duplicates an earlier one."""
    match = pattern.match(error)
    if match is None:
        if error not in result:
            result.append(error)
        return

    key = (match.group(1), match.group(2))
    if key in seen:
        return
    seen.add(key)
    result.append(f"Step '{key[0]}': {key[1]}")


def _check_create_pattern(
    step_name: str,
    step_inputs: Dict[str, Any],
    has_matrix: bool,
    has_cache_input: bool,
) -> List[str]:
    """Return CREATE pattern validation errors for one step."""
    errors: List[str] = []
    if "output" not in step_inputs:
        errors.append(
            f"Step '{step_name}': CREATE pattern requires "
            f"'output' parameter"
        )
    if not has_matrix:
        errors.append(
            f"Step '{step_name}': CREATE pattern requires "
            f"workflow 'matrix' definition"
        )
    if has_cache_input:
        errors.append(
            f"Step '{step_name}': CREATE pattern prohibits "
            f"cache input (.db files)"
        )
    return errors


def _check_aggregate_pattern(
    step_name: str,
    step_inputs: Dict[str, Any],
    has_matrix: bool,
    has_cache_input: bool,
) -> List[str]:
    """Return AGGREGATE pattern validation errors for one step."""
    errors: List[str] = []
    if "input" not in step_inputs:
        errors.append(
            f"Step '{step_name}': AGGREGATE pattern requires "
            f"'input' parameter"
        )
    if "output" not in step_inputs:
        errors.append(
            f"Step '{step_name}': AGGREGATE pattern requires "
            f"'output' parameter"
        )
    # Matrix can be explicit or derived from cache input
    if not has_matrix and not has_cache_input:
        errors.append(
            f"Step '{step_name}': AGGREGATE pattern requires "
            f"workflow 'matrix' definition or cache input"
        )
    return errors


_PATTERN_CHECKS = {
    ActionPattern.CREATE: _check_create_pattern,
    ActionPattern.AGGREGATE: _check_aggregate_pattern,
}


class ValidationMixin(WorkflowExecutorBase):
    """Configuration validation for WorkflowExecutor."""

    def _validate_required_variables(
        self, workflow: Dict[str, Any], cli_params: Dict[str, Any]
    ) -> None:
        """Validate that required workflow variables (None values) provided.

        Args:
            workflow: Parsed workflow dictionary
            cli_params: CLI parameters that can override workflow variables

        Raises:
            WorkflowExecutionError: If required variables are not provided
        """
        required_vars = [
            key
            for key, value in workflow.items()
            if _is_required_variable(key, value, cli_params)
        ]

        if not required_vars:
            return

        sorted_vars = sorted(required_vars)
        raise WorkflowExecutionError(
            f"Required workflow variables not provided: {sorted_vars}. "
            f"These variables have 'None' values and must be specified "
            f"via CLI parameters or calling workflow."
        )

    def _validate_workflow_actions(
        self, workflow: Dict[str, Any], mode: str
    ) -> None:
        """Validate all actions in workflow.

        Args:
            workflow: Parsed workflow dictionary
            mode: Base execution mode for validation

        Raises:
            WorkflowExecutionError: If action validation fails
        """
        # Get action validation errors
        action_errors = self.action_registry.validate_workflow_actions(
            workflow
        )
        if action_errors:
            raise WorkflowExecutionError("; ".join(action_errors))

        # Validate action patterns
        pattern_errors = self._validate_action_patterns(workflow)
        if pattern_errors:
            raise WorkflowExecutionError("; ".join(pattern_errors))

        # Validate filter expressions in steps
        filter_errors = self._validate_step_filters(workflow)
        if filter_errors:
            raise WorkflowExecutionError(
                f"Filter validation failed: {'; '.join(filter_errors)}"
            )

    def _validate_action_patterns(self, workflow: Dict[str, Any]) -> List[str]:
        """Validate action patterns against workflow configuration.

        Checks that each step's input/output/matrix configuration matches
        the declared pattern for its action:
        - CREATE: output required, matrix required, cache input prohibited
        - AGGREGATE: input required, output required, matrix required

        Args:
            workflow: Parsed workflow dictionary

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: List[str] = []
        has_matrix = bool(workflow.get("matrix", {}))

        for step in workflow.get("steps", []):
            errors.extend(self._validate_step_pattern(step, has_matrix))

        return errors

    def _validate_step_pattern(
        self, step: Dict[str, Any], has_matrix: bool
    ) -> List[str]:
        """Validate one step's configuration against its action pattern."""
        step_name = step.get("name", "unnamed")
        step_inputs = step.get("with", {})
        if _runs_once(step, has_matrix):
            return []
        pattern = self._step_pattern(
            step.get("uses"), step_inputs.get("action")
        )
        if pattern is None:
            return []

        checker = _PATTERN_CHECKS.get(pattern)
        if checker is None:  # pragma: no cover - all patterns handled
            return []
        return checker(
            step_name,
            step_inputs,
            has_matrix,
            self._has_cache_input(step_inputs),
        )

    def _step_pattern(
        self, provider_name: Optional[str], action_name: Optional[str]
    ) -> Optional[ActionPattern]:
        """Return the declared action pattern, or None if indeterminable."""
        if not provider_name or not action_name:
            return None
        return self.action_registry.get_action_pattern(
            provider_name, action_name
        )

    def _validate_step_filters(self, workflow: Dict[str, Any]) -> List[str]:
        """Validate filter expressions in workflow steps.

        Checks that filter expressions are syntactically valid before
        execution. This catches errors like missing quotes around strings
        (e.g., `network == asia` instead of `network == 'asia'`).

        Args:
            workflow: Parsed workflow dictionary.

        Returns:
            List of validation error messages (empty if all valid).
        """
        errors: List[str] = []

        for step in workflow.get("steps", []):
            step_name = step.get("name", "unnamed")
            filter_expr = step.get("with", {}).get("filter")

            if not filter_expr:
                continue

            error = _check_filter_expression(step_name, filter_expr)
            if error:
                errors.append(error)

        return errors

    def _deduplicate_errors(self, errors: List[str]) -> List[str]:
        """Deduplicate validation errors by grouping similar messages.

        Groups errors that have the same core message (after the step
        prefix) and returns a unique list without repetition.

        Args:
            errors: List of validation error strings

        Returns:
            Deduplicated list of unique errors
        """
        # Pattern to extract step name and core message
        # Format: "Step 'name': message"
        pattern = re.compile(r"^Step '([^']+)':\s*(.+)$")

        # Track unique (step_name, message) pairs
        seen: Set[tuple[str, str]] = set()
        result: List[str] = []

        for error in errors:
            _add_unique_error(error, pattern, seen, result)

        return result
