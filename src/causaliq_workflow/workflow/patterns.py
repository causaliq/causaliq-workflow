"""Step pattern detection helpers."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.matrix import _has_db_input

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_core import ActionPattern


class PatternMixin(WorkflowExecutorBase):
    """Step pattern detection methods for WorkflowExecutor."""

    def _is_update_pattern_step(
        self,
        step: Dict[str, Any],
        workflow: Dict[str, Any],
    ) -> bool:
        """Check if a step uses UPDATE pattern (for validation purposes).

        Args:
            step: Step configuration dictionary
            workflow: Full workflow dictionary

        Returns:
            True if step declares UPDATE pattern
        """
        from causaliq_core import ActionPattern

        provider_name = step.get("uses")
        if not provider_name:
            return False

        step_inputs = step.get("with", {})
        action_name = step_inputs.get("action")
        if not action_name:
            return False

        # Check if action declares UPDATE pattern
        try:
            pattern = self.action_registry.get_action_pattern(
                provider_name, action_name
            )
            return pattern == ActionPattern.UPDATE
        except Exception:
            return False

    def _is_nocache_step(self, step: Dict[str, Any]) -> bool:
        """Check if a step uses the NOCACHES pattern.

        NOCACHES pattern steps operate on plain files (not workflow
        caches) and do not use the workflow matrix, so they run once
        regardless of the matrix.

        Args:
            step: Step configuration dictionary

        Returns:
            True if the action declares NOCACHES pattern
        """
        from causaliq_core import ActionPattern

        provider_name = step.get("uses")
        if not provider_name:
            return False

        step_inputs = step.get("with", {})
        action_name = step_inputs.get("action")
        if not action_name:
            return False

        # Check if action declares NOCACHES pattern
        try:
            pattern = self.action_registry.get_action_pattern(
                provider_name, action_name
            )
            return pattern == ActionPattern.NOCACHES
        except Exception:
            return False

    def _is_aggregate_pattern_step(
        self,
        step: Dict[str, Any],
        workflow: Dict[str, Any],
    ) -> bool:
        """Check if a step uses AGGREGATE pattern (for validation purposes).

        AGGREGATE pattern steps use matrix variables for grouping entries,
        not for templating parameters.

        Args:
            step: Step configuration dictionary
            workflow: Full workflow dictionary

        Returns:
            True if step has .db input and is AGGREGATE pattern
        """
        from causaliq_core import ActionPattern

        step_inputs = step.get("with", {})

        # Check if step has cache input (.db files)
        if not _has_db_input(step_inputs.get("input")):
            return False

        # Check if action declares AGGREGATE pattern
        provider_name = step.get("uses")
        action_name = step_inputs.get("action")
        if not provider_name or not action_name:
            return False

        try:
            pattern = self.action_registry.get_action_pattern(
                provider_name, action_name
            )
            return pattern == ActionPattern.AGGREGATE
        except Exception:
            return False

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

    def _is_aggregation_step(
        self,
        step: Dict[str, Any],
        matrix: Dict[str, List[Any]],
    ) -> bool:
        """Check if a step should execute in aggregation mode.

        Aggregation mode is activated when:
        1. The workflow has a matrix definition AND step has cache input, OR
        2. The action declares AGGREGATE pattern AND step has cache input
           (matrix will be derived from input cache)

        Args:
            step: Step configuration dictionary
            matrix: Workflow matrix definition

        Returns:
            True if step should run in aggregation mode
        """
        step_inputs = step.get("with", {})

        # Check if step has cache input (.db files in input parameter)
        if not _has_db_input(step_inputs.get("input")):
            return False

        declared = self._aggregation_from_pattern(step, step_inputs)
        if declared is not None:
            return declared

        # If matrix is provided with cache input and no explicit
        # pattern, treat as aggregation (legacy behaviour)
        return bool(matrix)

    def _aggregation_from_pattern(
        self,
        step: Dict[str, Any],
        step_inputs: Dict[str, Any],
    ) -> Optional[bool]:
        """Return the aggregation decision implied by the action pattern.

        Returns True for an AGGREGATE pattern, False for an UPDATE
        pattern and None when no relevant pattern is declared (or it
        cannot be determined).
        """
        from causaliq_core import ActionPattern

        provider_name = step.get("uses")
        action_name = step_inputs.get("action")
        if not provider_name or not action_name:
            return None

        try:
            pattern = self.action_registry.get_action_pattern(
                provider_name, action_name
            )
        except Exception:
            return None

        if pattern is None:
            return None

        flags = {ActionPattern.UPDATE: False, ActionPattern.AGGREGATE: True}
        return flags.get(pattern)

    def _is_update_step(
        self,
        step: Dict[str, Any],
        matrix: Dict[str, List[Any]],
    ) -> bool:
        """Check if a step should run in UPDATE pattern mode.

        UPDATE pattern is detected when:
        1. Action declares ActionPattern.UPDATE for the action name
        2. Step has input parameter pointing to .db cache file

        When the workflow has a matrix, the UPDATE step processes
        only the entry matching the current matrix combination.
        Without a matrix, all entries are processed.

        Args:
            step: Step configuration dictionary
            matrix: Workflow matrix definition

        Returns:
            True if step should run in UPDATE mode
        """
        input_param = step.get("with", {}).get("input")

        if not self._declares_update(step):
            return False

        # Must have input pointing to .db cache
        if not input_param:
            return False

        return str(input_param).lower().endswith(".db")

    def _declares_update(self, step: Dict[str, Any]) -> bool:
        """Return True when the step's action declares the UPDATE pattern."""
        from causaliq_core import ActionPattern

        provider_name = step.get("uses")
        step_inputs = step.get("with", {})
        action_name = step_inputs.get("action")
        if not provider_name or not action_name:
            return False

        # Check if action declares UPDATE pattern
        try:
            pattern = self.action_registry.get_action_pattern(
                provider_name, action_name
            )
        except (AttributeError, KeyError):
            return False
        return pattern == ActionPattern.UPDATE

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
