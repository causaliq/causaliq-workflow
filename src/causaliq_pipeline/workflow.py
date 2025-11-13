"""
Workflow execution engine for CausalIQ Pipeline.

Provides parsing and execution of GitHub Actions-style YAML workflows with
matrix strategy support for causal discovery experiments.
"""

import itertools
from pathlib import Path
from typing import Any, Dict, List, Union

from causaliq_pipeline.schema import (
    WorkflowValidationError,
    load_workflow_file,
    validate_workflow,
)


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails."""

    pass


class WorkflowExecutor:
    """Parse and execute GitHub Actions-style workflows with matrix expansion.

    This class handles the parsing of YAML workflow files and expansion of
    matrix strategies into individual experiment jobs. It provides the
    foundation for executing multi-step causal discovery workflows with
    parameterised experiments using flexible action parameter templating.
    """

    def parse_workflow(
        self, workflow_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """Parse workflow YAML file with validation.

        Args:
            workflow_path: Path to workflow YAML file

        Returns:
            Parsed and validated workflow dictionary

        Raises:
            WorkflowExecutionError: If workflow parsing or validation fails
        """
        try:
            workflow = load_workflow_file(workflow_path)
            validate_workflow(workflow)
            return workflow
        except WorkflowValidationError as e:
            raise WorkflowExecutionError(
                f"Workflow validation failed: {e}"
            ) from e

    def expand_matrix(
        self, matrix: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """Expand matrix variables into individual job configurations.

        Generates all combinations from matrix variables using cartesian
        product. Each combination becomes a separate job configuration.

        Args:
            matrix: Dictionary mapping variable names to lists of values

        Returns:
            List of job configurations with matrix variables expanded

        Raises:
            WorkflowExecutionError: If matrix expansion fails
        """
        if not matrix:
            return [{}]

        try:
            # Get variable names and value lists
            variables = list(matrix.keys())
            value_lists = list(matrix.values())

            # Generate cartesian product of all combinations
            combinations = list(itertools.product(*value_lists))

            # Create job configurations
            jobs = []
            for combination in combinations:
                job = dict(zip(variables, combination))
                jobs.append(job)

            return jobs

        except Exception as e:
            raise WorkflowExecutionError(
                f"Matrix expansion failed: {e}"
            ) from e
