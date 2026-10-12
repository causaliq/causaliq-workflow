"""Workflow execution engine for CausalIQ Workflow.

Provides parsing and execution of GitHub Actions-style YAML workflows
with matrix strategy support for causal discovery experiments. The
engine is decomposed into functional mixins composed into
``WorkflowExecutor``; this package re-exports the public names and the
helpers imported by tests so existing imports keep resolving.
"""

from causaliq_workflow.schema import load_workflow_file, validate_workflow
from causaliq_workflow.workflow.aggregation import AggregationConfig
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.executor import WorkflowExecutor
from causaliq_workflow.workflow.matrix import (
    _derive_matrix_from_caches,
    _matrix_values_match,
    _normalise_matrix_value,
)

__all__ = [
    "AggregationConfig",
    "WorkflowExecutionError",
    "WorkflowExecutor",
    "load_workflow_file",
    "validate_workflow",
    "_derive_matrix_from_caches",
    "_matrix_values_match",
    "_normalise_matrix_value",
]
