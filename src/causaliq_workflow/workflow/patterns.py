"""Step pattern detection helpers."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.matrix import _has_db_input, _runs_once

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_core import ActionPattern


class PatternMixin(WorkflowExecutorBase):
    """Step pattern detection methods for WorkflowExecutor."""

    def _runs_once(self, step: Dict[str, Any], matrix: Dict[str, Any]) -> bool:
        """Return True when a step runs once rather than per matrix job.

        A step that writes a file rather than a workflow cache has no
        output dimensionality, so it runs once. A workflow-call step runs
        once unless its parameters vary across the calling matrix.

        Args:
            step: Step configuration dictionary.
            matrix: The workflow's matrix definition (empty when absent).

        Returns:
            True when the step runs once rather than per job.
        """
        return _runs_once(step, matrix)

    def _is_aggregate_pattern_step(
        self,
        step: Dict[str, Any],
        workflow: Dict[str, Any],
    ) -> bool:
        """Check if a step groups input cache entries.

        An AGGREGATE step uses its matrix variables for grouping entries
        rather than for templating parameters.

        Args:
            step: Step configuration dictionary
            workflow: Full workflow dictionary

        Returns:
            True if step has .db input and a grouping action pattern
        """
        from causaliq_core import ActionPattern

        step_inputs = step.get("with", {})

        # Check if step has cache input (.db files)
        if not _has_db_input(step_inputs.get("input")):
            return False

        return self._get_step_action_pattern(step) == ActionPattern.AGGREGATE

    def _get_step_action_pattern(
        self, step: Dict[str, Any]
    ) -> Optional["ActionPattern"]:
        """Get the action pattern for a step, if determinable.

        This method checks only the action pattern, ignoring workflow context
        like matrix presence. Used for matrix variable usage validation.

        Args:
            step: Step configuration dictionary

        Returns:
            The ActionPattern if determinable, None otherwise
        """
        provider_name = step.get("uses")
        step_inputs = step.get("with", {})
        action_name = step_inputs.get("action")

        if not provider_name or not action_name:
            return None

        try:
            return self.action_registry.get_action_pattern(
                provider_name, action_name
            )
        except Exception:
            return None

    def _is_entry_scan_step(
        self,
        step: Dict[str, Any],
        matrix: Dict[str, List[Any]],
        variables: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if a step should be given matched input cache entries.

        A step receives entries when it reads a workflow cache and either
        declares a cache-reading pattern (MAP or AGGREGATE) or a matrix is
        defined, in which case the entries for the current job are
        selected.

        Args:
            step: Step configuration dictionary
            matrix: Workflow matrix definition
            variables: Values available before matrix expansion, used to
                resolve a templated ``input`` path before checking it

        Returns:
            True if the step should receive matched input entries
        """
        step_inputs = self._resolved_step_inputs(step, variables)

        # Check if step has cache input (.db files in input parameter)
        if not _has_db_input(step_inputs.get("input")):
            return False

        from causaliq_core import ActionPattern

        pattern = self._get_step_action_pattern(step)
        if pattern in (ActionPattern.MAP, ActionPattern.AGGREGATE):
            return True

        # If matrix is provided with cache input and no explicit
        # pattern, treat as aggregation (legacy behaviour)
        return bool(matrix)

    def _map_arity_error(
        self,
        step_name: str,
        step: Dict[str, Any],
        entries: List[Any],
        allow_empty: bool = False,
    ) -> Optional[str]:
        """Return an error when a MAP step did not match one entry.

        A MAP action maps one input entry to one output entry, so a job
        must match exactly one. An empty match is tolerated when
        ``allow_empty`` is set, because the validation pass runs before
        an earlier step may have created the input cache.

        Args:
            step_name: Step name for the error message.
            step: Step configuration dictionary.
            entries: Cache entries matched for the current job.
            allow_empty: Treat no matches as acceptable.

        Returns:
            An error message, or None when the match is acceptable.
        """
        from causaliq_core import ActionPattern

        if self._get_step_action_pattern(step) != ActionPattern.MAP:
            return None
        if not entries:
            if allow_empty:
                return None
            return (
                f"Step '{step_name}': no input cache entry matches this "
                f"job; check that the input cache exists and uses the "
                f"same dimensions as the workflow matrix"
            )
        if len(entries) > 1:
            return (
                f"Step '{step_name}': this action maps one input entry to "
                f"one output entry but matched {len(entries)}; add a matrix "
                f"key to distinguish them"
            )
        return None

    def _has_cache_input(self, step_inputs: Dict[str, Any]) -> bool:
        """Check if step inputs include cache file (.db) inputs.

        Args:
            step_inputs: Step 'with' parameters

        Returns:
            True if any input parameter points to .db files
        """
        input_param = step_inputs.get("input")
        if not input_param:
            return False

        inputs = (
            [input_param]
            if isinstance(input_param, str)
            else (list(input_param) if input_param else [])
        )
        return any(str(p).lower().endswith(".db") for p in inputs)
