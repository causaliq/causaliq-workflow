"""Template variable extraction, resolution and validation."""

from typing import Any, Dict, List, Optional, Set, Tuple

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.matrix import (
    _cache_input_paths,
    _derive_matrix_from_caches,
    _has_db_input,
)
from causaliq_workflow.workflow.parameters import (
    _declared_parameters,
    _extract_tokens,
    _parameter_declaration_errors,
    _single_token,
    _substitute_text,
    _supplied_parameter_names,
    _token_names,
    _workflow_variables,
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
           variables, or keys derived from a cache-reading step's input
           cache). A variable with no value is a required parameter.
        2. All matrix variables must be used in at least one step's
           templates. A grouping (AGGREGATE) step templates parameters as
           well as selecting entries, so its templates count as uses.
        3. A name may not be declared as both a parameter and a matrix
           variable.
        4. A declared parameter must be used as a ``{{placeholder}}``, and
           a null-default parameter may only be a whole-value
           placeholder.

        Variables used only by a cache-reading step whose input cache does
        not exist yet (it may be produced by an earlier step) are deferred
        to runtime resolution.

        Args:
            workflow: Parsed workflow dictionary
            parameters: Parameter names supplied by a caller or the CLI

        Raises:
            WorkflowExecutionError: If unknown template variables found,
                a parameter declaration is ineffective, or matrix
                variables are not used in any templating step
        """
        parameter_names = _supplied_parameter_names(parameters)
        variables = _workflow_variables(workflow, parameters)
        matrix_vars = set(workflow.get("matrix", {}).keys())
        derived_vars, deferred_vars = self._aggregate_template_scope(
            workflow, variables
        )
        available = _collect_available_variables(
            workflow, matrix_vars, parameter_names
        )
        available.update(derived_vars)
        all_vars, has_templating_steps = self._scan_step_variables(workflow)
        templating_vars = self._collect_templating_variables(workflow)

        _raise_parameter_errors(workflow)
        _raise_unknown_variables(all_vars - deferred_vars, available)
        if matrix_vars and has_templating_steps:
            _raise_unused_matrix_variables(
                matrix_vars, templating_vars, workflow.get("matrix", {})
            )

    def _missing_variable_errors(
        self, workflow: Dict[str, Any], parameters: Any = None
    ) -> List[str]:
        """Return errors for template variables that have no value.

        A ``{{name}}`` token that is not a declared parameter, matrix
        variable, supplied parameter or cache-derived name has no value,
        so an undeclared placeholder is effectively a required
        parameter. Variables of a cache-reading step whose input cache
        does not exist yet are resolved at run time and are not reported.

        Args:
            workflow: Parsed workflow dictionary.
            parameters: Parameter names supplied by a caller or the CLI.

        Returns:
            One error listing every unresolved variable, or an empty
            list.
        """
        parameter_names = _supplied_parameter_names(parameters)
        variables = _workflow_variables(workflow, parameters)
        matrix_vars = set(workflow.get("matrix", {}).keys())
        derived, deferred = self._aggregate_template_scope(workflow, variables)
        available = _collect_available_variables(
            workflow, matrix_vars, parameter_names
        )
        available.update(derived)
        all_vars, _ = self._scan_step_variables(workflow)
        missing = (all_vars - deferred) - available
        if not missing:
            return []
        return [_missing_variables_message(missing, available)]

    def _aggregate_template_scope(
        self,
        workflow: Dict[str, Any],
        variables: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Set[str], Set[str]]:
        """Return (matrix keys taken from caches, deferred variables).

        A cache-reading step without an explicit matrix takes its
        dimensionality from the entries of its input caches. Templated
        cache paths are resolved first from the workflow's parameter
        defaults and supplied values, so a cache reached through
        ``{{cache_dir}}`` contributes its keys. When a cache exists its
        keys are known now, so templates using them are validated
        strictly; when no cache exists yet the step's variables are
        deferred to runtime resolution.
        """
        derived: Set[str] = set()
        deferred: Set[str] = set()

        for step in workflow.get("steps", []):
            if not self._reads_cache_entries(step):
                continue
            step_inputs = self._resolved_step_inputs(step, variables)
            matrix_keys = _cached_matrix_keys(step_inputs)
            if matrix_keys:
                derived.update(matrix_keys)
            else:
                deferred.update(self._step_template_variables(step))

        return derived, deferred

    def _reads_cache_entries(self, step: Dict[str, Any]) -> bool:
        """Return True when a step reads entries from a workflow cache.

        MAP and AGGREGATE steps take their dimensionality from an input
        cache, so their matrix may be absent. A PRODUCE step has no input
        cache to inherit from.
        """
        from causaliq_core import ActionPattern

        step_inputs = step.get("with", {})
        return self._get_step_action_pattern(step) in (
            ActionPattern.MAP,
            ActionPattern.AGGREGATE,
        ) and _has_db_input(step_inputs.get("input"))

    def _step_template_variables(self, step: Dict[str, Any]) -> Set[str]:
        """Return the template variables used by a single step."""
        step_vars: Set[str] = set()
        self._collect_template_variables(step, step_vars)
        return step_vars

    def _collect_templating_variables(
        self, workflow: Dict[str, Any]
    ) -> Set[str]:
        """Collect template variables used by any workflow step.

        A matrix variable is used when it appears in any step's templates.
        A grouping (AGGREGATE) step templates parameters such as weights or
        thresholds as well as selecting entries, so its templates count
        too; the check only catches dimensions that do nothing at all.
        """
        templating_vars: Set[str] = set()

        for step in workflow.get("steps", []):
            step_vars: Set[str] = set()
            self._collect_template_variables(step, step_vars)
            templating_vars.update(step_vars)

        return templating_vars

    def _scan_step_variables(
        self, workflow: Dict[str, Any]
    ) -> Tuple[Set[str], bool]:
        """Collect template variables and detect templating steps.

        Returns a tuple of (all_vars, has_templating_steps). A templating
        step is a MAP or PRODUCE step, whose matrix values appear in
        ``{{variable}}`` templates.
        """
        from causaliq_core import ActionPattern

        templating_patterns = (ActionPattern.PRODUCE, ActionPattern.MAP)
        all_vars: Set[str] = set()
        has_templating_steps = False

        for step in workflow.get("steps", []):
            step_vars: Set[str] = set()
            self._collect_template_variables(step, step_vars)
            all_vars.update(step_vars)

            if self._get_step_action_pattern(step) in templating_patterns:
                has_templating_steps = True

        return all_vars, has_templating_steps

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

    def _resolved_step_inputs(
        self, step: Dict[str, Any], variables: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Return a step's ``with`` block with known templates resolved.

        Cache introspection runs before a job exists, so it needs the
        workflow's parameter defaults and the values a caller or the CLI
        supplies. An empty context leaves the block unchanged, which
        keeps the raw-definition behaviour for callers without values.

        Args:
            step: Step configuration dictionary.
            variables: Values available before matrix expansion.

        Returns:
            The step's ``with`` values, resolved where possible.
        """
        step_inputs: Dict[str, Any] = step.get("with", {})
        if not variables:
            return step_inputs
        resolved: Dict[str, Any] = self._resolve_template_variables(
            step_inputs, variables
        )
        return resolved

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


def _cached_matrix_keys(step_inputs: Dict[str, Any]) -> Set[str]:
    """Return matrix keys derivable from resolved step inputs.

    Returns an empty set when the step names no cache input or when none of
    its input caches exist yet.
    """
    cache_paths = _cache_input_paths(step_inputs.get("input"))
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
    templating_vars: Set[str],
    matrix_def: Dict[str, Any],
) -> None:
    """Raise when matrix variables are unused by any templating step."""
    unused = {
        var
        for var in matrix_vars - templating_vars
        if not all(v is None for v in matrix_def.get(var, []))
    }
    if not unused:
        return
    raise WorkflowExecutionError(
        f"Matrix variables not used in any step: {sorted(unused)}. "
        f"Each matrix variable must appear as a {{{{variable}}}} template "
        f"in at least one step."
    )
