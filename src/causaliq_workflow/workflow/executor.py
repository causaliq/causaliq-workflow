"""Composition of the WorkflowExecutor from its functional mixins."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from causaliq_workflow.registry import ActionRegistry
from causaliq_workflow.workflow.aggregation import AggregationMixin
from causaliq_workflow.workflow.execution import ExecutionMixin
from causaliq_workflow.workflow.matrix import MatrixMixin
from causaliq_workflow.workflow.patterns import PatternMixin
from causaliq_workflow.workflow.step_runner import StepRunnerMixin
from causaliq_workflow.workflow.step_store import StepStoreMixin
from causaliq_workflow.workflow.subworkflow import SubWorkflowMixin
from causaliq_workflow.workflow.templates import TemplateMixin
from causaliq_workflow.workflow.validation import ValidationMixin
from causaliq_workflow.workflow.validation_entries import (
    EntryValidationMixin,
)


class WorkflowExecutor(
    MatrixMixin,
    TemplateMixin,
    PatternMixin,
    SubWorkflowMixin,
    AggregationMixin,
    StepRunnerMixin,
    StepStoreMixin,
    ValidationMixin,
    EntryValidationMixin,
    ExecutionMixin,
):
    """Parse and execute GitHub Actions-style workflows.

    This class handles the parsing of YAML workflow files and expansion
    of matrix strategies into individual experiment jobs. It provides
    the foundation for executing multi-step causal discovery workflows
    with parameterised experiments using flexible action parameter
    templating.
    """

    def __init__(self) -> None:
        """Initialize workflow executor with action registry."""
        self.action_registry = ActionRegistry()
        self._scan_index: Dict[str, List[Dict[str, Any]]] = {}
        self._environment: Optional[Dict[str, Any]] = None
        self._environment_ready = False
        self._source_path: Optional[Path] = None

    def _invalidate_scan_index(self, cache: Any) -> None:
        """Drop the memoised scan index for a cache that was written.

        The aggregation scan caches each input cache's entry summaries
        for the duration of a run. Writing new entries invalidates that
        cache so any later scan observes the update.

        Args:
            cache: Open workflow cache that was written to, or None.
        """
        path = getattr(cache, "db_path", None)
        if path is not None:
            self._scan_index.pop(str(path), None)
