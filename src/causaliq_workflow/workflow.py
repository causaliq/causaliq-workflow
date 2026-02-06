"""
Workflow execution engine for CausalIQ Workflow.

Provides parsing and execution of GitHub Actions-style YAML workflows with
matrix strategy support for causal discovery experiments.
"""

import itertools
import re
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Union,
)

from causaliq_workflow.registry import ActionRegistry, WorkflowContext
from causaliq_workflow.schema import (
    WorkflowValidationError,
    load_workflow_file,
    validate_workflow,
)

if TYPE_CHECKING:  # pragma: no cover
    from causaliq_workflow.cache import WorkflowCache


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

    def __init__(self) -> None:
        """Initialize workflow executor with action registry."""
        self.action_registry = ActionRegistry()

    def parse_workflow(
        self, workflow_path: Union[str, Path], mode: str = "dry-run"
    ) -> Dict[str, Any]:
        """Parse workflow YAML file with validation.

        Args:
            workflow_path: Path to workflow YAML file
            mode: Execution mode for action validation

        Returns:
            Parsed and validated workflow dictionary

        Raises:
            WorkflowExecutionError: If workflow parsing or validation fails
        """
        try:
            workflow = load_workflow_file(workflow_path)
            validate_workflow(workflow)
            self._validate_template_variables(workflow)

            # Validate all actions exist and can run
            self._validate_workflow_actions(workflow, mode)

            return workflow

        except (WorkflowValidationError, FileNotFoundError) as e:
            raise WorkflowExecutionError(f"Workflow parsing failed: {e}")
        except Exception as e:
            raise WorkflowExecutionError(
                f"Unexpected error parsing workflow: {e}"
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
        """Validate that all template variables in workflow exist in context.

        Args:
            workflow: Parsed workflow dictionary

        Raises:
            WorkflowExecutionError: If unknown template variables found
        """
        # Build available context
        available_variables = {"id", "description"}

        # Add workflow variables (excluding workflow metadata fields)
        workflow_vars = {
            k
            for k, v in workflow.items()
            if k not in {"id", "description", "matrix", "steps"}
        }
        available_variables.update(workflow_vars)

        # Add matrix variables if present
        if "matrix" in workflow:
            available_variables.update(workflow["matrix"].keys())

        # Collect all template variables used in workflow
        used_variables: Set[str] = set()
        self._collect_template_variables(workflow, used_variables)

        # Check for unknown variables
        unknown_variables = used_variables - available_variables
        if unknown_variables:
            unknown_list = sorted(unknown_variables)
            available_list = sorted(available_variables)
            raise WorkflowExecutionError(
                f"Unknown template variables: {unknown_list}. "
                f"Available variables: {available_list}"
            )

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
        elif isinstance(obj, list):
            for item in obj:
                self._collect_template_variables(item, used_variables)
        elif isinstance(obj, str):
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
        elif isinstance(obj, list):
            return [
                self._resolve_template_variables(item, variables)
                for item in obj
            ]
        elif isinstance(obj, str):
            result = obj
            for var in self._extract_template_variables(obj):
                if var in variables:
                    result = result.replace(
                        f"{{{{{var}}}}}", str(variables[var])
                    )
            return result
        else:
            return obj

    def _validate_required_variables(
        self, workflow: Dict[str, Any], cli_params: Dict[str, Any]
    ) -> None:
        """Validate that required workflow variables (None values) provided.

        Args:
            workflow: Parsed workflow dictionary
            cli_params: CLI parameters that can override workflow variables

        Raises:
            WorkflowExecutionError: If required variables are not provided
        """
        required_vars = []

        for key, value in workflow.items():
            # Skip workflow metadata fields
            if key in {"id", "description", "matrix", "steps"}:
                continue

            # Check for None values (required variables)
            if value is None:
                # Check if provided via CLI
                if key not in cli_params:
                    required_vars.append(key)

        if required_vars:
            sorted_vars = sorted(required_vars)
            raise WorkflowExecutionError(
                f"Required workflow variables not provided: {sorted_vars}. "
                f"These variables have 'None' values and must be specified "
                f"via CLI parameters or calling workflow."
            )

    def _validate_workflow_actions(
        self, workflow: Dict[str, Any], mode: str
    ) -> None:
        """Validate all actions in workflow by running in dry-run mode.

        Args:
            workflow: Parsed workflow dictionary
            mode: Base execution mode for validation

        Raises:
            WorkflowExecutionError: If action validation fails
        """
        # Get action validation errors
        action_errors = self.action_registry.validate_workflow_actions(
            workflow
        )
        if action_errors:
            raise WorkflowExecutionError(
                f"Action validation failed: {'; '.join(action_errors)}"
            )

        # Run full workflow validation in dry-run mode if requested
        if mode != "dry-run":
            try:
                self.execute_workflow(workflow, mode="dry-run")
            except Exception as e:
                raise WorkflowExecutionError(
                    f"Workflow dry-run validation failed: {e}"
                ) from e

    def execute_workflow(
        self,
        workflow: Dict[str, Any],
        mode: str = "dry-run",
        cli_params: Optional[Dict[str, Any]] = None,
        step_logger: Optional[Callable[[str, str, str], None]] = None,
        cache: Optional["WorkflowCache"] = None,
    ) -> List[Dict[str, Any]]:
        """Execute complete workflow with matrix expansion.

        Args:
            workflow: Parsed workflow dictionary
            mode: Execution mode ('dry-run', 'run', 'compare')
            cli_params: Additional parameters from CLI
            step_logger: Optional function to log step execution
            cache: Optional WorkflowCache for storing step results

        Returns:
            List of job results from matrix expansion

        Raises:
            WorkflowExecutionError: If workflow execution fails
        """
        if cli_params is None:
            cli_params = {}

        try:
            # Expand matrix into individual jobs
            matrix = workflow.get("matrix", {})
            jobs = self.expand_matrix(matrix)

            results = []
            for job_index, job in enumerate(jobs):
                # Create workflow context
                context = WorkflowContext(
                    mode=mode,
                    matrix=matrix,
                    matrix_values=job,
                    cache=cache,
                )

                # Execute job steps
                job_result = self._execute_job(
                    workflow, job, context, cli_params, step_logger
                )
                results.append(job_result)

            return results

        except Exception as e:
            raise WorkflowExecutionError(
                f"Workflow execution failed: {e}"
            ) from e

    def _execute_job(
        self,
        workflow: Dict[str, Any],
        job: Dict[str, Any],
        context: WorkflowContext,
        cli_params: Dict[str, Any],
        step_logger: Optional[Callable[[str, str, str], None]] = None,
    ) -> Dict[str, Any]:
        """Execute single job with resolved matrix variables.

        Args:
            workflow: Base workflow configuration
            job: Job with resolved matrix variables
            context: Workflow context
            cli_params: CLI parameters

        Returns:
            Job execution results

        """
        # Validate required workflow variables (None values must be provided)
        self._validate_required_variables(workflow, cli_params)

        # Combine all variable sources for template resolution
        variables = {
            **workflow,  # Workflow-level properties
            **job,  # Matrix variables
            **cli_params,  # CLI parameters
        }

        step_results: Dict[str, Any] = {}

        for step in workflow.get("steps", []):
            step_name = step.get("name", f"step-{len(step_results)}")

            if "uses" in step:
                # Execute action step
                action_name = step["uses"]
                action_inputs = step.get("with", {})

                # Resolve template variables in inputs
                resolved_inputs = self._resolve_template_variables(
                    action_inputs, variables
                )

                # Log step execution in real-time if logger provided
                if step_logger:
                    # Get action's display name from the class (with hyphens)
                    action_class = self.action_registry.get_action_class(
                        action_name
                    )
                    display_name = getattr(action_class, "name", action_name)
                    step_logger(display_name, step_name, "EXECUTING")

                # Execute action
                step_result = self.action_registry.execute_action(
                    action_name, resolved_inputs, context
                )

                # Log step completion in real-time if logger provided
                if step_logger:
                    # Use same display name for consistency
                    action_class = self.action_registry.get_action_class(
                        action_name
                    )
                    display_name = getattr(action_class, "name", action_name)
                    status = step_result.get("status", "unknown").upper()
                    step_logger(display_name, step_name, status)

                step_results[step_name] = step_result

                # Add step outputs to variables for subsequent steps
                if "outputs" in step_result:
                    variables[f"steps.{step_name}.outputs"] = step_result[
                        "outputs"
                    ]

            elif "run" in step:
                # TODO: Shell command execution
                raise WorkflowExecutionError(
                    f"Shell command execution not yet implemented: "
                    f"{step['run']}"
                )
            else:
                raise WorkflowExecutionError(
                    f"Step '{step_name}' must have 'uses' or 'run'"
                )

        return {
            "job": job,
            "steps": step_results,
            "context": context,
        }
