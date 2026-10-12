"""Composition of the WorkflowExecutor from its functional mixins."""

from causaliq_workflow.registry import ActionRegistry
from causaliq_workflow.workflow.aggregation import AggregationMixin
from causaliq_workflow.workflow.execution import ExecutionMixin
from causaliq_workflow.workflow.filters import FilterMixin
from causaliq_workflow.workflow.matrix import MatrixMixin
from causaliq_workflow.workflow.patterns import PatternMixin
from causaliq_workflow.workflow.templates import TemplateMixin
from causaliq_workflow.workflow.update import UpdateMixin
from causaliq_workflow.workflow.validation import ValidationMixin
from causaliq_workflow.workflow.validation_entries import (
    EntryValidationMixin,
)


class WorkflowExecutor(
    MatrixMixin,
    TemplateMixin,
    PatternMixin,
    FilterMixin,
    UpdateMixin,
    AggregationMixin,
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
