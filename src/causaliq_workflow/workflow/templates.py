"""Template variable extraction, resolution and validation."""

import re
from typing import Any, Dict, Set, Tuple

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.errors import WorkflowExecutionError


class TemplateMixin(WorkflowExecutorBase):
    """Template variable methods for WorkflowExecutor."""

    def _extract_template_variables(self, text: Any) -> Set[str]:
        """Extract template variables from a string.

        Finds all {{variable}} patterns and returns variable names.

        Args:
            text: String that may contain {{variable}} patterns

        Returns:
            Set of variable names found in templates
        """
        if not isinstance(text, str):
            return set()

        # Pattern matches {{variable_name}} with alphanumeric, _, -
        pattern = r"\{\{([a-zA-Z_][a-zA-Z0-9_-]*)\}\}"
        matches = re.findall(pattern, text)
        return set(matches)

    def _validate_template_variables(self, workflow: Dict[str, Any]) -> None:
        """Validate template variables in workflow.

        Performs two validations:
        1. All template variables must exist in the available context
           (workflow variables, matrix variables, or built-ins).
        2. All matrix variables must be used in at least one CREATE step's
           template. AGGREGATE steps use matrix for grouping (not
           templating).

        Args:
            workflow: Parsed workflow dictionary

        Raises:
            WorkflowExecutionError: If unknown template variables found
                or if matrix variables are not used in any CREATE step
        """
        matrix_vars = set(workflow.get("matrix", {}).keys())
        available = _collect_available_variables(workflow, matrix_vars)
        all_vars, has_create_steps = self._scan_step_variables(workflow)
        create_vars = self._collect_create_variables(workflow)

        _raise_unknown_variables(all_vars, available)
        if matrix_vars and has_create_steps:
            _raise_unused_matrix_variables(
                matrix_vars, create_vars, workflow.get("matrix", {})
            )

    def _collect_create_variables(self, workflow: Dict[str, Any]) -> Set[str]:
        """Collect template variables used by CREATE steps.

        AGGREGATE step variables are intentionally not collected: their
        matrix variables group entries rather than templating parameters.
        """
        create_vars: Set[str] = set()

        for step in workflow.get("steps", []):
            if self._is_aggregate_pattern_step(step, workflow):
                continue
            step_vars: Set[str] = set()
            self._collect_template_variables(step, step_vars)
            create_vars.update(step_vars)

        return create_vars

    def _scan_step_variables(
        self, workflow: Dict[str, Any]
    ) -> Tuple[Set[str], bool]:
        """Collect template variables and detect CREATE steps.

        Returns a tuple of (all_vars, has_create_steps).
        """
        from causaliq_core import ActionPattern

        all_vars: Set[str] = set()
        has_create_steps = False

        for step in workflow.get("steps", []):
            step_vars: Set[str] = set()
            self._collect_template_variables(step, step_vars)
            all_vars.update(step_vars)

            if self._get_step_action_pattern(step) == ActionPattern.CREATE:
                has_create_steps = True

        return all_vars, has_create_steps

    def _collect_template_variables(
        self, obj: Any, used_variables: Set[str]
    ) -> None:
        """Recursively collect template variables from workflow object.

        Args:
            obj: Workflow object (dict, list, or string) to scan
            used_variables: Set to collect found variables into
        """
        if isinstance(obj, dict):
            for value in obj.values():
                self._collect_template_variables(value, used_variables)
            return
        if isinstance(obj, list):
            for item in obj:
                self._collect_template_variables(item, used_variables)
            return
        if isinstance(obj, str):
            used_variables.update(self._extract_template_variables(obj))

    def _resolve_template_variables(
        self, obj: Any, variables: Dict[str, Any]
    ) -> Any:
        """Recursively resolve template variables in workflow object.

        Args:
            obj: Workflow object (dict, list, or string) to resolve
            variables: Variable values to substitute

        Returns:
            Resolved object with template variables substituted
        """
        if isinstance(obj, dict):
            return {
                key: self._resolve_template_variables(value, variables)
                for key, value in obj.items()
            }
        if isinstance(obj, list):
            return [
                self._resolve_template_variables(item, variables)
                for item in obj
            ]
        if isinstance(obj, str):
            return self._substitute_variables(obj, variables)
        return obj

    def _substitute_variables(
        self, text: str, variables: Dict[str, Any]
    ) -> str:
        """Substitute known ``{{variable}}`` tokens in a single string."""
        result = text
        for var in self._extract_template_variables(text):
            if var in variables:
                result = result.replace(f"{{{{{var}}}}}", str(variables[var]))
        return result


def _collect_available_variables(
    workflow: Dict[str, Any], matrix_vars: Set[str]
) -> Set[str]:
    """Return the set of template variables available to a workflow."""
    available = {"id", "description"}
    workflow_vars = {
        key
        for key in workflow
        if key not in {"id", "description", "matrix", "steps"}
    }
    available.update(workflow_vars)
    available.update(matrix_vars)
    return available


def _raise_unknown_variables(
    all_non_update_vars: Set[str], available: Set[str]
) -> None:
    """Raise when template variables are not in the available context."""
    unknown = all_non_update_vars - available
    if not unknown:
        return
    raise WorkflowExecutionError(
        f"Unknown template variables: {sorted(unknown)}. "
        f"Available variables: {sorted(available)}"
    )


def _raise_unused_matrix_variables(
    matrix_vars: Set[str],
    create_vars: Set[str],
    matrix_def: Dict[str, Any],
) -> None:
    """Raise when matrix variables are unused by any CREATE step."""
    unused = {
        var
        for var in matrix_vars - create_vars
        if not all(v is None for v in matrix_def.get(var, []))
    }
    if not unused:
        return
    raise WorkflowExecutionError(
        f"Matrix variables not used in any step: {sorted(unused)}. "
        f"Each matrix variable must appear in at least one "
        f"{{{{variable}}}} template in CREATE pattern steps."
    )
