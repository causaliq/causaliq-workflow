"""Template variable extraction, resolution and validation."""

from typing import Any, Dict, List, Optional, Set, Tuple

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.matrix import (
    _cache_input_paths,
    _derive_matrix_from_caches,
)
from causaliq_workflow.workflow.parameters import (
    _declared_parameters,
    _extract_tokens,
    _parameter_declaration_errors,
    _single_token,
    _substitute_text,
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

        Performs four validations:

        1. All template variables must exist in the available context
           (declared parameters, supplied parameter names, matrix
           variables, or keys derived from an AGGREGATE step's input
           cache). A variable with no value is a required parameter.
        2. All matrix variables must be used in at least one CREATE step's
           template. AGGREGATE steps use matrix for grouping (not
           templating).
        3. A name may not be declared as both a parameter and a matrix
           variable.
        4. A declared parameter must be used as a ``{{placeholder}}``, and
           a null-default parameter may only be a whole-value
           placeholder.

        Variables used only by an AGGREGATE step whose input cache does not
        exist yet (it may be produced by an earlier step) are deferred to
        runtime resolution.

        Args:
            workflow: Parsed workflow dictionary
            parameters: Parameter names supplied by a caller or the CLI

        Raises:
            WorkflowExecutionError: If unknown template variables found,
                a parameter declaration is ineffective, or matrix
                variables are not used in any CREATE step
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

    def _missing_variable_errors(
        self, workflow: Dict[str, Any], parameters: Any = None
    ) -> List[str]:
        """Return errors for template variables that have no value.

        A ``{{name}}`` token that is not a declared parameter, matrix
        variable, supplied parameter or cache-derived name has no value,
        so an undeclared placeholder is effectively a required
        parameter. Variables of an AGGREGATE step whose input cache does
        not exist yet are resolved at run time and are not reported.

        Args:
            workflow: Parsed workflow dictionary.
            parameters: Parameter names supplied by a caller or the CLI.

        Returns:
            One error listing every unresolved variable, or an empty
            list.
        """
        matrix_vars = set(workflow.get("matrix", {}).keys())
        derived, deferred = self._aggregate_template_scope(workflow)
        available = _collect_available_variables(
            workflow, matrix_vars, set(parameters or ())
        )
        available.update(derived)
        all_vars, _ = self._scan_step_variables(workflow)
        missing = (all_vars - deferred) - available
        if not missing:
            return []
        return [_missing_variables_message(missing, available)]

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
        return _substitute_text(text, variables)

    def _resolve_step_name(
        self,
        step: Dict[str, Any],
        variables: Dict[str, Any],
        index: int,
        recorded: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Return a step's name with its template tokens expanded as text.

        A name is always text, so a ``{{name}}`` token in it is replaced
        by the value's text form rather than by its native value.
        Resolution happens per job, so a matrix variable yields a
        different name for each combination.

        Step results are recorded by name, so an expanded name that
        already holds a result would overwrite it.

        Args:
            step: Step configuration dictionary.
            variables: Variable values for the current job.
            index: Position of the step, used when the step has no name.
            recorded: Results already recorded for this job.

        Returns:
            The expanded step name.

        Raises:
            WorkflowExecutionError: If the expanded name is already
                recorded for this job.
        """
        name = step.get("name")
        text = f"step-{index}" if not isinstance(name, str) else name
        resolved = _substitute_text(text, variables)
        if resolved in (recorded or {}):
            raise WorkflowExecutionError(
                f"Step name '{resolved}' is already used by an earlier "
                f"step in this job; step names must stay unique after "
                f"template expansion"
            )
        return resolved


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
    """Raise when a parameter declaration is invalid or ineffective."""
    errors = _parameter_declaration_errors(workflow)
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


def _missing_variables_message(
    used_vars: Set[str], available: Set[str]
) -> str:
    """Return the message for template variables that have no value."""
    return (
        f"Unknown template variables: {sorted(used_vars - available)}. "
        f"Available variables: {sorted(available)}. "
        f"Declare a default value for each missing name as a top-level "
        f"workflow key, or supply it with 'with:' in the calling "
        f"workflow or --param."
    )


def _raise_unknown_variables(used_vars: Set[str], available: Set[str]) -> None:
    """Raise when template variables are not in the available context."""
    if not used_vars - available:
        return
    raise WorkflowExecutionError(
        _missing_variables_message(used_vars, available)
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
