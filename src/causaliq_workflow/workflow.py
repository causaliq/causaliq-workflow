"""
Workflow execution engine for CausalIQ Workflow.

Provides parsing and execution of GitHub Actions-style YAML workflows with
matrix strategy support for causal discovery experiments.
"""

import itertools
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
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


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails."""

    pass


@dataclass
class AggregationConfig:
    """Configuration for aggregation mode execution.

    Aggregation mode is activated when a workflow step has:
    - An `input` parameter specifying workflow cache(s)
    - A matrix definition in the workflow

    The matrix variables define the grouping dimensions for aggregation.
    """

    input_caches: List[str] = field(default_factory=list)
    """List of input workflow cache paths."""

    filter_expr: Optional[str] = None
    """Optional filter expression to restrict input entries."""

    matrix_vars: List[str] = field(default_factory=list)
    """Matrix variables defining grouping dimensions."""


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

    def _is_aggregation_step(
        self,
        step: Dict[str, Any],
        matrix: Dict[str, List[Any]],
    ) -> bool:
        """Check if a step should execute in aggregation mode.

        Aggregation mode is activated when:
        1. The workflow has a matrix definition, AND
        2. Either:
           a. The step has an `aggregate` parameter, OR
           b. The step has an `input` parameter pointing to .db file(s)

        Args:
            step: Step configuration dictionary
            matrix: Workflow matrix definition

        Returns:
            True if step should run in aggregation mode
        """
        if not matrix:
            return False

        step_inputs = step.get("with", {})

        # Explicit aggregate parameter
        if "aggregate" in step_inputs:
            return True

        # Check if input points to .db cache file(s)
        input_param = step_inputs.get("input")
        if input_param:
            inputs = (
                [input_param]
                if isinstance(input_param, str)
                else (list(input_param) if input_param else [])
            )
            # Aggregation if any input is a .db file
            if any(str(p).lower().endswith(".db") for p in inputs):
                return True

        return False

    def _get_aggregation_config(
        self,
        step: Dict[str, Any],
        matrix: Dict[str, List[Any]],
    ) -> Optional[AggregationConfig]:
        """Get aggregation configuration for a step.

        Returns None if the step is not an aggregation step.

        Args:
            step: Step configuration dictionary
            matrix: Workflow matrix definition

        Returns:
            AggregationConfig if aggregation mode, None otherwise
        """
        if not self._is_aggregation_step(step, matrix):
            return None

        step_inputs = step.get("with", {})

        # Get cache paths from either 'aggregate' or 'input' parameter
        aggregate_param = step_inputs.get("aggregate")
        input_param = step_inputs.get("input")

        # Collect cache paths (.db files only)
        input_caches: List[str] = []

        if aggregate_param:
            # Explicit aggregate parameter takes precedence
            if isinstance(aggregate_param, str):
                input_caches = [aggregate_param]
            elif isinstance(aggregate_param, list):
                input_caches = list(aggregate_param)
        elif input_param:
            # Implicit aggregation from input .db files
            inputs = (
                [input_param]
                if isinstance(input_param, str)
                else (list(input_param) if input_param else [])
            )
            # Filter to only .db files for cache scanning
            input_caches = [
                str(p) for p in inputs if str(p).lower().endswith(".db")
            ]

        return AggregationConfig(
            input_caches=input_caches,
            filter_expr=step_inputs.get("filter"),
            matrix_vars=list(matrix.keys()),
        )

    def _scan_aggregation_inputs(
        self,
        config: AggregationConfig,
        matrix_values: Dict[str, Any],
        logger: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Scan input caches and collect entries matching matrix values.

        This is the first phase of aggregation execution. It:
        1. Opens each input cache
        2. Iterates all entries
        3. Applies the filter expression (if any)
        4. Groups entries by matrix variable values
        5. Returns entries matching the current matrix combination

        Args:
            config: Aggregation configuration
            matrix_values: Current matrix variable values to match
            logger: Optional logging function for statistics

        Returns:
            List of entry dictionaries with keys:
            - matrix_values: The entry's matrix values
            - metadata: The entry's metadata (includes nested provider data)
            - cache_path: Source cache path for provenance
            - entry_hash: Entry hash for retrieval

        Note:
            Entries without all matrix variables in metadata are skipped.
        """
        from pathlib import Path

        from causaliq_core.utils import evaluate_filter

        from causaliq_workflow.cache import WorkflowCache

        matching_entries: List[Dict[str, Any]] = []
        total_scanned = 0
        total_filtered = 0
        total_matched = 0

        for cache_path in config.input_caches:
            # Skip non-existent caches with warning
            if not Path(cache_path).exists():
                if logger:
                    logger(f"Warning: Cache does not exist: {cache_path}")
                continue

            try:
                with WorkflowCache(cache_path) as cache:
                    entries = cache.list_entries()
                    total_scanned += len(entries)

                    for entry_info in entries:
                        entry_matrix = entry_info.get("matrix_values", {})

                        # Skip entries missing required matrix variables
                        if not all(
                            var in entry_matrix for var in config.matrix_vars
                        ):
                            continue

                        # Get full entry to access metadata
                        full_entry = cache.get(entry_matrix)
                        if full_entry is None:
                            continue

                        # Flatten metadata for filter evaluation
                        flat_meta = self._flatten_metadata(
                            entry_matrix, full_entry.metadata
                        )

                        # Apply filter expression if present
                        if config.filter_expr:
                            try:
                                if not evaluate_filter(
                                    config.filter_expr, flat_meta
                                ):
                                    total_filtered += 1
                                    continue
                            except Exception:
                                # Filter evaluation error - skip entry
                                total_filtered += 1
                                continue

                        # Check if entry matches current matrix values
                        matches = all(
                            entry_matrix.get(var) == matrix_values.get(var)
                            for var in config.matrix_vars
                        )

                        if matches:
                            total_matched += 1
                            matching_entries.append(
                                {
                                    "matrix_values": entry_matrix,
                                    "metadata": full_entry.metadata,
                                    "cache_path": str(cache_path),
                                    "entry_hash": entry_info.get("hash"),
                                    "entry": full_entry,
                                }
                            )

            except Exception as e:
                if logger:
                    logger(f"Warning: Failed to read cache {cache_path}: {e}")

        # Log statistics if logger provided
        if logger:
            filter_info = ""
            if config.filter_expr:
                filter_info = f", filtered={total_filtered}"
            logger(
                f"Aggregation scan: scanned={total_scanned}"
                f"{filter_info}, matched={total_matched}"
            )

        return matching_entries

    def _flatten_metadata(
        self,
        matrix_values: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Flatten metadata for filter expression evaluation.

        Combines matrix values with nested metadata structure into a flat
        dictionary suitable for filter expression evaluation.

        Args:
            matrix_values: Entry's matrix variable values
            metadata: Entry's nested metadata dictionary

        Returns:
            Flat dictionary with all metadata fields
        """
        flat: Dict[str, Any] = dict(matrix_values)

        # Flatten nested metadata (provider -> action -> fields)
        for provider_name, provider_data in metadata.items():
            if isinstance(provider_data, dict):
                for action_name, action_data in provider_data.items():
                    if isinstance(action_data, dict):
                        for key, value in action_data.items():
                            # Use simple key if no conflict
                            if key not in flat:
                                flat[key] = value
                            # Use fully qualified key as fallback
                            flat[f"{provider_name}.{action_name}.{key}"] = (
                                value
                            )
                    else:
                        flat[f"{provider_name}.{action_name}"] = action_data
            else:
                flat[provider_name] = provider_data

        return flat

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
    ) -> List[Dict[str, Any]]:
        """Execute complete workflow with matrix expansion.

        Caching is controlled at the step level via the 'output' parameter
        in each step's 'with' block. Each step can write to its own cache.

        Args:
            workflow: Parsed workflow dictionary
            mode: Execution mode ('dry-run', 'run', 'compare')
            cli_params: Additional parameters from CLI
            step_logger: Optional function to log step execution

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
                # Create workflow context (cache set per-step)
                context = WorkflowContext(
                    mode=mode,
                    matrix=matrix,
                    matrix_values=job,
                    cache=None,
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

                # Implicitly pass matrix variables to action if not specified
                # This allows actions to receive matrix values without
                # explicit {{variable}} templates in the workflow
                for matrix_var, matrix_val in job.items():
                    if matrix_var not in resolved_inputs:
                        resolved_inputs[matrix_var] = matrix_val

                # Handle aggregation mode: scan input caches for matching
                # entries. Aggregation mode is activated when step has 'input'
                # parameter and workflow has matrix definition.
                matrix = workflow.get("matrix", {})
                agg_config = self._get_aggregation_config(step, matrix)
                if agg_config is not None:
                    matching_entries = self._scan_aggregation_inputs(
                        agg_config,
                        job,  # Current matrix values
                    )
                    # Pass entries to action via special parameter
                    resolved_inputs["_aggregation_entries"] = matching_entries
                    # Remove 'aggregate' from resolved params (config only)
                    resolved_inputs.pop("aggregate", None)

                # Handle step-level cache from output parameter
                output_path = resolved_inputs.pop("output", None)
                step_cache = None

                # "none" is a special value meaning "no output"
                should_cache = (
                    output_path is not None
                    and str(output_path).lower() != "none"
                    and context.mode == "run"
                )
                if should_cache:
                    from causaliq_workflow.cache import WorkflowCache

                    step_cache = WorkflowCache(output_path)
                    step_cache.open()
                    context.cache = step_cache

                try:
                    # Log step execution in real-time if logger provided
                    if step_logger:
                        action_class = self.action_registry.get_action_class(
                            action_name
                        )
                        display_name = getattr(
                            action_class, "name", action_name
                        )
                        step_logger(display_name, step_name, "EXECUTING")

                    # Execute action
                    step_result = self.action_registry.execute_action(
                        action_name, resolved_inputs, context
                    )

                    # Store results to cache if successful and objects present
                    if (
                        context.cache is not None
                        and step_result.get("status") == "success"
                        and step_result.get("objects")
                    ):
                        from causaliq_workflow.cache import store_action_result

                        objects = step_result.get("objects", [])
                        raw_metadata = {
                            k: v
                            for k, v in step_result.items()
                            if k not in ("status", "objects")
                        }

                        # Structure metadata by provider/action
                        action_class = self.action_registry.get_action_class(
                            action_name
                        )
                        provider_name = getattr(
                            action_class, "name", action_name
                        )
                        action_method = resolved_inputs.get(
                            "action", "default"
                        )
                        metadata = {
                            provider_name: {action_method: raw_metadata}
                        }

                        # Pass matrix key order for export directory structure
                        matrix_key_order = list(context.matrix.keys())

                        store_action_result(
                            cache=context.cache,
                            context=context,
                            entry_type="graph",
                            metadata=metadata,
                            objects=objects,
                            matrix_key_order=matrix_key_order,
                        )

                    # Log step completion in real-time if logger provided
                    if step_logger:
                        action_class = self.action_registry.get_action_class(
                            action_name
                        )
                        display_name = getattr(
                            action_class, "name", action_name
                        )
                        status = step_result.get("status", "unknown").upper()
                        step_logger(display_name, step_name, status)

                finally:
                    # Close step cache and reset context
                    if step_cache is not None:
                        step_cache.close()
                        context.cache = None

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
