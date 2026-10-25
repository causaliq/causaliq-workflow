"""Template variable extraction, resolution and validation."""

from typing import Any, Dict, Set, Tuple

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.matrix import (
    _cache_input_paths,
    _derive_matrix_from_caches,
)
from causaliq_workflow.workflow.parameters import (
    _declared_parameters,
    _extract_tokens,
    _parameter_matrix_clash_errors,
    _single_token,
    _token_names,
)


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
        return _extract_tokens(text)

    def _validate_template_variables(
        self,
        workflow: Dict[str, Any],
        parameters: Any = None,
    ) -> None:
        """Validate template variables in workflow.

        Performs three validations:

        1. All template variables must exist in the available context
           (declared parameters, supplied parameter names, matrix
           variables, or keys derived from an AGGREGATE step's input
           cache).
        2. All matrix variables must be used in at least one CREATE step's
           template. AGGREGATE steps use matrix for grouping (not
           templating).
        3. A name may not be declared as both a parameter and a matrix
           variable.

        Variables used only by an AGGREGATE step whose input cache does not
        exist yet (it may be produced by an earlier step) are deferred to
        runtime resolution.

        Args:
            workflow: Parsed workflow dictionary
            parameters: Parameter names supplied by a caller or the CLI

        Raises:
            WorkflowExecutionError: If unknown template variables found,
                a name is declared twice, or matrix variables are not used
                in any CREATE step
        """
        parameters = set(parameters or ())
        matrix_vars = set(workflow.get("matrix", {}).keys())
        derived_vars, deferred_vars = self._aggregate_template_scope(workflow)
        available = _collect_available_variables(
            workflow, matrix_vars, parameters
        )
        available.update(derived_vars)
        all_vars, has_create_steps = self._scan_step_variables(workflow)
        create_vars = self._collect_create_variables(workflow)

        _raise_parameter_errors(workflow)
        _raise_unknown_variables(all_vars - deferred_vars, available)
        if matrix_vars and has_create_steps:
            _raise_unused_matrix_variables(
                matrix_vars, create_vars, workflow.get("matrix", {})
            )

    def _aggregate_template_scope(
        self, workflow: Dict[str, Any]
    ) -> Tuple[Set[str], Set[str]]:
        """Return (derived matrix keys, deferred variables).

        An AGGREGATE step without an explicit matrix takes its
        dimensionality from the entries of its input caches. When a cache
        exists its keys are known now, so templates using them are
        validated strictly; when no cache exists yet the step's variables
        are deferred to runtime resolution.
        """
        derived: Set[str] = set()
        deferred: Set[str] = set()

        for step in workflow.get("steps", []):
            if not self._is_aggregate_pattern_step(step, workflow):
                continue
            matrix_keys = _cached_matrix_keys(step)
            if matrix_keys:
                derived.update(matrix_keys)
            else:
                deferred.update(self._step_template_variables(step))

        return derived, deferred

    def _step_template_variables(self, step: Dict[str, Any]) -> Set[str]:
        """Return the template variables used by a single step."""
        step_vars: Set[str] = set()
        self._collect_template_variables(step, step_vars)
        return step_vars

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
        used_variables.update(_token_names(obj))

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
    ) -> Any:
        """Substitute known ``{{variable}}`` tokens in a single string.

        A string that is exactly one ``{{name}}`` token yields the
        variable's native value when that value is not a string, so a
        list, number, boolean or ``None`` parameter reaches the action
        unchanged. Text containing a token plus other characters is
        always substituted as text.

        Args:
            text: String that may contain ``{{variable}}`` tokens.
            variables: Variable values to substitute.

        Returns:
            The native value for a whole-value token, otherwise the
            substituted string.
        """
        token = _single_token(text)
        if token is not None and token in variables:
            value = variables[token]
            if not isinstance(value, str):
                return value
        result = text
        for var in self._extract_template_variables(text):
            if var in variables:
                result = result.replace(f"{{{{{var}}}}}", str(variables[var]))
        return result


def _collect_available_variables(
    workflow: Dict[str, Any],
    matrix_vars: Set[str],
    parameters: Set[str],
) -> Set[str]:
    """Return the set of template variables available to a workflow.

    Declared parameter defaults and supplied parameter names are
    available alongside the workflow's matrix variables.
    """
    available = set(_declared_parameters(workflow))
    available.update(matrix_vars)
    available.update(parameters)
    return available


def _raise_parameter_errors(workflow: Dict[str, Any]) -> None:
    """Raise when a parameter name is also a matrix variable."""
    errors = _parameter_matrix_clash_errors(workflow)
    if not errors:
        return
    raise WorkflowExecutionError("; ".join(errors))


def _cached_matrix_keys(step: Dict[str, Any]) -> Set[str]:
    """Return matrix keys derivable from a step's input caches.

    Returns an empty set when the step names no cache input or when none of
    its input caches exist yet.
    """
    cache_paths = _cache_input_paths(step.get("with", {}).get("input"))
    matrix_keys, _ = _derive_matrix_from_caches(cache_paths)
    return set(matrix_keys)


def _raise_unknown_variables(used_vars: Set[str], available: Set[str]) -> None:
    """Raise when template variables are not in the available context."""
    unknown = used_vars - available
    if not unknown:
        return
    raise WorkflowExecutionError(
        f"Unknown template variables: {sorted(unknown)}. "
        f"Available variables: {sorted(available)}. "
        f"Declare the name as a workflow parameter, or supply it with "
        f"'with:' in the calling workflow or --param."
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
