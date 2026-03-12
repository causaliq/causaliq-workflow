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

        For UPDATE pattern steps, template variables not in the workflow
        context are allowed as they will be resolved from entry metadata
        at runtime.

        Args:
            workflow: Parsed workflow dictionary

        Raises:
            WorkflowExecutionError: If unknown template variables found
                (excluding UPDATE step variables which are deferred)
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

        # Collect template variables per step, distinguishing UPDATE steps
        update_step_variables: Set[str] = set()
        other_step_variables: Set[str] = set()

        for step in workflow.get("steps", []):
            step_vars: Set[str] = set()
            self._collect_template_variables(step, step_vars)

            # Check if this is an UPDATE pattern step
            is_update = self._is_update_pattern_step(step, workflow)

            if is_update:
                update_step_variables.update(step_vars)
            else:
                other_step_variables.update(step_vars)

        # Collect workflow-level variables (outside steps)
        workflow_level_vars: Set[str] = set()
        for key in ["id", "description"]:
            if key in workflow and isinstance(workflow[key], str):
                workflow_level_vars.update(
                    self._extract_template_variables(workflow[key])
                )

        # Check non-UPDATE variables for unknown references
        non_update_vars = other_step_variables | workflow_level_vars
        unknown_variables = non_update_vars - available_variables

        if unknown_variables:
            unknown_list = sorted(unknown_variables)
            available_list = sorted(available_variables)
            raise WorkflowExecutionError(
                f"Unknown template variables: {unknown_list}. "
                f"Available variables: {available_list}"
            )

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

        # UPDATE pattern prohibits matrix
        if workflow.get("matrix"):
            return False

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

    def _is_update_step(
        self,
        step: Dict[str, Any],
        matrix: Dict[str, List[Any]],
    ) -> bool:
        """Check if a step should run in UPDATE pattern mode.

        UPDATE pattern is detected when:
        1. Action declares ActionPattern.UPDATE for the action name
        2. Step has input parameter pointing to .db cache file

        UPDATE steps process all entries in the input cache (no matrix).

        Args:
            step: Step configuration dictionary
            matrix: Workflow matrix definition

        Returns:
            True if step should run in UPDATE mode
        """
        from causaliq_core import ActionPattern

        # UPDATE pattern prohibits matrix
        if matrix:
            return False

        provider_name = step.get("uses")
        if not provider_name:
            return False

        step_inputs = step.get("with", {})
        action_name = step_inputs.get("action")
        if not action_name:
            return False

        # Check if action declares UPDATE pattern
        pattern = self.action_registry.get_action_pattern(
            provider_name, action_name
        )
        if pattern != ActionPattern.UPDATE:
            return False

        # Must have input pointing to .db cache
        input_param = step_inputs.get("input")
        if not input_param:
            return False

        return str(input_param).lower().endswith(".db")

    def _execute_update_step(
        self,
        step: Dict[str, Any],
        resolved_inputs: Dict[str, Any],
        context: WorkflowContext,
        step_logger: Optional[
            Callable[[str, str, str, Dict[str, Any]], None]
        ] = None,
    ) -> Dict[str, Any]:
        """Execute a step in UPDATE pattern mode.

        UPDATE mode processes all entries in the input cache:
        1. Opens input cache
        2. Iterates all entries (subject to filter)
        3. Applies conservative execution (skip if action metadata exists)
        4. Calls action with entry data via _update_entry parameter
        5. Updates entry metadata and objects in place

        Args:
            step: Step configuration dictionary
            resolved_inputs: Resolved action inputs
            context: Workflow context
            step_logger: Optional logging function

        Returns:
            Step result dictionary with status, updated counts, etc.
        """
        from pathlib import Path

        from causaliq_core.utils import evaluate_filter

        from causaliq_workflow.cache import WorkflowCache

        action_name = step["uses"]
        action_method = resolved_inputs.get("action", "default")
        input_path = resolved_inputs.get("input")
        filter_expr = resolved_inputs.get("filter")

        # Get provider name for metadata structuring
        action_class = self.action_registry.get_action_class(action_name)
        provider_name = getattr(action_class, "name", action_name)

        # Validate input_path is provided (should be guaranteed by validation)
        if input_path is None:
            return {
                "status": "error",
                "error": "UPDATE action requires 'input' parameter",
                "entries_processed": 0,
                "entries_skipped": 0,
                "entries_updated": 0,
            }

        # Check input cache exists
        if not Path(input_path).exists():
            return {
                "status": "error",
                "error": f"Input cache does not exist: {input_path}",
                "entries_processed": 0,
                "entries_skipped": 0,
                "entries_updated": 0,
            }

        entries_processed = 0
        entries_skipped = 0
        entries_updated = 0
        errors: List[str] = []

        with WorkflowCache(input_path) as cache:
            entries = cache.list_entries()

            for entry_info in entries:
                entry_matrix = entry_info.get("matrix_values", {})
                entries_processed += 1

                # Get full entry
                full_entry = cache.get(entry_matrix)
                if full_entry is None:
                    continue

                # Flatten metadata for filter evaluation
                flat_meta = self._flatten_metadata(
                    entry_matrix, full_entry.metadata
                )

                # Apply filter expression if present
                if filter_expr:
                    try:
                        if not evaluate_filter(filter_expr, flat_meta):
                            entries_skipped += 1
                            if step_logger:
                                step_logger(
                                    action_method,
                                    step.get("name", "unknown"),
                                    "IGNORED",
                                    entry_matrix,
                                )
                            continue
                    except Exception:
                        # Filter failed on this entry - skip it
                        # (validation should catch syntax errors upfront)
                        entries_skipped += 1
                        if step_logger:
                            step_logger(
                                action_method,
                                step.get("name", "unknown"),
                                "IGNORED",
                                entry_matrix,
                            )
                        continue

                # Conservative execution: skip if action already applied
                # Bypassed in force mode
                if context.mode != "force" and cache.has_action_metadata(
                    entry_matrix, provider_name, action_method
                ):
                    entries_skipped += 1
                    if step_logger:
                        step_logger(
                            action_method,
                            step.get("name", "unknown"),
                            "SKIPPED",
                            entry_matrix,
                        )
                    continue

                # Prepare inputs for action, passing entry data
                action_inputs = {
                    k: v
                    for k, v in resolved_inputs.items()
                    if k not in ("input", "filter")
                }

                # Resolve any remaining template variables from entry metadata
                # This enables UPDATE steps to use {{network}}, {{sample_size}}
                # etc. which are resolved from each entry's metadata
                action_inputs = self._resolve_template_variables(
                    action_inputs, flat_meta
                )

                action_inputs["_update_entry"] = {
                    "matrix_values": entry_matrix,
                    "metadata": full_entry.metadata,
                    "entry": full_entry,
                }

                # Execute action
                try:
                    result = self.action_registry.execute_action(
                        action_name, action_inputs, context
                    )

                    if result.get("status") == "success":
                        # Extract metadata (exclude status and objects)
                        raw_metadata = {
                            k: v
                            for k, v in result.items()
                            if k not in ("status", "objects")
                        }

                        # Structure metadata by provider/action
                        structured_metadata = {
                            provider_name: {action_method: raw_metadata}
                        }

                        # Update entry in cache
                        objects = result.get("objects", [])
                        if cache.update_entry(
                            entry_matrix, structured_metadata, objects
                        ):
                            entries_updated += 1
                            if step_logger:
                                status = (
                                    "FORCED"
                                    if context.mode == "force"
                                    else "EXECUTED"
                                )
                                step_logger(
                                    action_method,
                                    step.get("name", "unknown"),
                                    status,
                                    entry_matrix,
                                )

                except Exception as e:
                    errors.append(f"Entry {entry_matrix}: {e}")
                    if step_logger:
                        step_logger(
                            action_method,
                            step.get("name", "unknown"),
                            "FAILED",
                            entry_matrix,
                        )

        # Determine overall status
        if entries_updated > 0:
            status = "success"
        elif entries_skipped == entries_processed:
            status = "skipped"
        else:
            status = "error" if errors else "skipped"

        result = {
            "status": status,
            "entries_processed": entries_processed,
            "entries_skipped": entries_skipped,
            "entries_updated": entries_updated,
        }

        if errors:
            result["errors"] = errors

        return result

    def _scan_update_step_entries(
        self,
        step: Dict[str, Any],
        resolved_inputs: Dict[str, Any],
        step_logger: Optional[
            Callable[[str, str, str, Dict[str, Any]], None]
        ] = None,
    ) -> Dict[str, int]:
        """Scan UPDATE step cache to count entries that would be processed.

        Used in dry-run mode to report how many entries would be updated
        vs skipped (due to conservative execution - action already applied).
        Optionally logs per-entry status via step_logger.

        Args:
            step: Step configuration dictionary
            resolved_inputs: Resolved action inputs
            step_logger: Optional logging function for per-entry status

        Returns:
            Dictionary with would_process and would_skip counts
        """
        from pathlib import Path

        from causaliq_core.utils import evaluate_filter

        from causaliq_workflow.cache import WorkflowCache

        action_name = step["uses"]
        action_method = resolved_inputs.get("action", "default")
        input_path = resolved_inputs.get("input")
        filter_expr = resolved_inputs.get("filter")

        # Get provider name for metadata checking
        action_class = self.action_registry.get_action_class(action_name)
        provider_name = getattr(action_class, "name", action_name)

        would_process = 0
        would_skip = 0

        if input_path is None or not Path(input_path).exists():
            return {"would_process": 0, "would_skip": 0}

        with WorkflowCache(input_path) as cache:
            entries = cache.list_entries()

            for entry_info in entries:
                entry_matrix = entry_info.get("matrix_values", {})

                # Get full entry
                full_entry = cache.get(entry_matrix)
                if full_entry is None:
                    continue

                # Flatten metadata for filter evaluation
                flat_meta = self._flatten_metadata(
                    entry_matrix, full_entry.metadata
                )

                # Apply filter expression if present
                if filter_expr:
                    try:
                        if not evaluate_filter(filter_expr, flat_meta):
                            would_skip += 1
                            if step_logger:
                                step_logger(
                                    action_method,
                                    step.get("name", "unknown"),
                                    "WOULD IGNORE",
                                    entry_matrix,
                                )
                            continue
                    except Exception:
                        # Filter failed on this entry - skip it
                        # (validation should catch syntax errors upfront)
                        would_skip += 1
                        if step_logger:
                            step_logger(
                                action_method,
                                step.get("name", "unknown"),
                                "WOULD IGNORE",
                                entry_matrix,
                            )
                        continue

                # Conservative execution check: skip if action already applied
                if cache.has_action_metadata(
                    entry_matrix, provider_name, action_method
                ):
                    would_skip += 1
                    if step_logger:
                        step_logger(
                            action_method,
                            step.get("name", "unknown"),
                            "WOULD SKIP",
                            entry_matrix,
                        )
                else:
                    would_process += 1
                    if step_logger:
                        step_logger(
                            action_method,
                            step.get("name", "unknown"),
                            "WOULD EXECUTE",
                            entry_matrix,
                        )

        return {"would_process": would_process, "would_skip": would_skip}

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
        """Validate all actions in workflow.

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

        # Validate action patterns
        pattern_errors = self._validate_action_patterns(workflow)
        if pattern_errors:
            raise WorkflowExecutionError(
                "Action pattern validation failed: "
                f"{'; '.join(pattern_errors)}"
            )

        # Validate filter expressions for UPDATE steps
        filter_errors = self._validate_step_filters(workflow)
        if filter_errors:
            raise WorkflowExecutionError(
                f"Filter validation failed: {'; '.join(filter_errors)}"
            )

    def _validate_action_patterns(self, workflow: Dict[str, Any]) -> List[str]:
        """Validate action patterns against workflow configuration.

        Checks that each step's input/output/matrix configuration matches
        the declared pattern for its action:
        - CREATE: output required, matrix required, cache input prohibited
        - UPDATE: input required, output prohibited, matrix prohibited
        - AGGREGATE: input required, output required, matrix required

        Args:
            workflow: Parsed workflow dictionary

        Returns:
            List of validation error messages (empty if valid)
        """
        from causaliq_core import ActionPattern

        errors: List[str] = []
        matrix = workflow.get("matrix", {})
        has_matrix = bool(matrix)

        for step in workflow.get("steps", []):
            step_name = step.get("name", "unnamed")
            provider_name = step.get("uses")
            if not provider_name:
                continue

            step_inputs = step.get("with", {})
            action_name = step_inputs.get("action")
            if not action_name:
                continue

            # Get the pattern for this action
            pattern = self.action_registry.get_action_pattern(
                provider_name, action_name
            )
            if pattern is None:
                # No pattern declared - skip validation
                continue

            has_input = "input" in step_inputs
            has_output = "output" in step_inputs
            has_cache_input = self._has_cache_input(step_inputs)

            if pattern == ActionPattern.CREATE:
                if not has_output:
                    errors.append(
                        f"Step '{step_name}': CREATE pattern requires "
                        f"'output' parameter"
                    )
                if not has_matrix:
                    errors.append(
                        f"Step '{step_name}': CREATE pattern requires "
                        f"workflow 'matrix' definition"
                    )
                if has_cache_input:
                    errors.append(
                        f"Step '{step_name}': CREATE pattern prohibits "
                        f"cache input (.db files)"
                    )

            elif pattern == ActionPattern.UPDATE:
                if not has_input:
                    errors.append(
                        f"Step '{step_name}': UPDATE pattern requires "
                        f"'input' parameter"
                    )
                if has_output:
                    errors.append(
                        f"Step '{step_name}': UPDATE pattern prohibits "
                        f"'output' parameter"
                    )
                if has_matrix:
                    errors.append(
                        f"Step '{step_name}': UPDATE pattern prohibits "
                        f"workflow 'matrix' definition"
                    )

            elif pattern == ActionPattern.AGGREGATE:
                if not has_input:
                    errors.append(
                        f"Step '{step_name}': AGGREGATE pattern requires "
                        f"'input' parameter"
                    )
                if not has_output:
                    errors.append(
                        f"Step '{step_name}': AGGREGATE pattern requires "
                        f"'output' parameter"
                    )
                if not has_matrix:
                    errors.append(
                        f"Step '{step_name}': AGGREGATE pattern requires "
                        f"workflow 'matrix' definition"
                    )

        return errors

    def _validate_step_filters(self, workflow: Dict[str, Any]) -> List[str]:
        """Validate filter expressions in workflow steps.

        Checks that filter expressions are syntactically valid before
        execution. This catches errors like missing quotes around strings
        (e.g., `network == asia` instead of `network == 'asia'`).

        Args:
            workflow: Parsed workflow dictionary.

        Returns:
            List of validation error messages (empty if all valid).
        """
        from causaliq_core.utils import FilterSyntaxError, validate_filter

        errors: List[str] = []

        for step in workflow.get("steps", []):
            step_name = step.get("name", "unnamed")
            step_inputs = step.get("with", {})
            filter_expr = step_inputs.get("filter")

            if not filter_expr:
                continue

            try:
                validate_filter(filter_expr)
            except FilterSyntaxError as e:
                errors.append(f"Step '{step_name}': {e}")
            except TypeError as e:
                errors.append(f"Step '{step_name}': {e}")

        return errors

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

    def _validate_all_entries(
        self,
        workflow: Dict[str, Any],
        cli_params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Validate all entries (matrix combos/cache entries) before execution.

        This is the validation pass of two-pass execution. It iterates
        all entries that would be processed during execution and calls
        validate_parameters() on each. This catches:

        - Semantic filter errors (e.g., `network == asia` where 'asia'
          is undefined)
        - Invalid action parameters
        - Missing required parameters

        Pattern-specific validation:

        - CREATE: Expand matrix, validate each combination
        - UPDATE: Open cache, iterate entries, apply filter, validate
        - AGGREGATE: Expand matrix, scan entries, validate each combo

        Args:
            workflow: Parsed workflow dictionary
            cli_params: Additional parameters from CLI

        Returns:
            List of validation error messages (empty if all valid)
        """
        if cli_params is None:
            cli_params = {}

        errors: List[str] = []
        matrix = workflow.get("matrix", {})
        jobs = self.expand_matrix(matrix)

        for step in workflow.get("steps", []):
            provider_name = step.get("uses")
            if not provider_name:
                continue

            step_inputs = step.get("with", {})
            action_name = step_inputs.get("action")
            if not action_name:
                continue

            # Determine step pattern
            is_update = self._is_update_step(step, matrix)
            is_aggregation = self._is_aggregation_step(step, matrix)

            if is_update:
                # UPDATE pattern: iterate cache entries
                update_errors = self._validate_update_entries(
                    step, workflow, cli_params
                )
                errors.extend(update_errors)

            elif is_aggregation:
                # AGGREGATE pattern: validate per matrix combo
                agg_errors = self._validate_aggregation_entries(
                    step, jobs, workflow, cli_params
                )
                errors.extend(agg_errors)

            else:
                # CREATE pattern: validate per matrix combo
                create_errors = self._validate_create_entries(
                    step, jobs, workflow, cli_params
                )
                errors.extend(create_errors)

        return errors

    def _validate_update_entries(
        self,
        step: Dict[str, Any],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
    ) -> List[str]:
        """Validate UPDATE pattern entries by iterating input cache.

        Opens the input cache, iterates all entries, applies the filter
        expression, and validates parameters for each matching entry.

        Args:
            step: Step configuration dictionary
            workflow: Full workflow dictionary for variable resolution
            cli_params: CLI parameters

        Returns:
            List of validation error messages
        """
        from pathlib import Path

        from causaliq_core import ActionValidationError
        from causaliq_core.utils import (
            FilterExpressionError,
            evaluate_filter,
        )

        from causaliq_workflow.cache import WorkflowCache

        errors: List[str] = []
        step_name = step.get("name", "unnamed")
        provider_name = str(step.get("uses", ""))
        step_inputs = step.get("with", {})

        # Resolve template variables in step inputs (workflow-level only)
        variables = {
            **workflow,
            **cli_params,
        }
        resolved_inputs = self._resolve_template_variables(
            step_inputs, variables
        )

        input_path = resolved_inputs.get("input")
        filter_expr = resolved_inputs.get("filter")

        # Check input path exists
        if input_path is None:
            errors.append(
                f"Step '{step_name}': UPDATE pattern requires 'input'"
            )
            return errors

        if not Path(input_path).exists():
            # Skip cache validation if cache doesn't exist
            # (will be caught at execution time)
            return errors

        with WorkflowCache(input_path) as cache:
            entries = cache.list_entries()

            for entry_info in entries:
                entry_matrix = entry_info.get("matrix_values", {})

                # Get full entry for metadata
                full_entry = cache.get(entry_matrix)
                if full_entry is None:
                    continue

                # Flatten metadata for filter evaluation
                flat_meta = self._flatten_metadata(
                    entry_matrix, full_entry.metadata
                )

                # Apply filter expression if present
                if filter_expr:
                    try:
                        if not evaluate_filter(filter_expr, flat_meta):
                            continue  # Would be filtered out
                    except FilterExpressionError as e:
                        # Semantic filter error - undefined variable
                        errors.append(
                            f"Step '{step_name}' entry {entry_matrix}: "
                            f"Filter error - {e}"
                        )
                        continue
                    except Exception as e:
                        errors.append(
                            f"Step '{step_name}' entry {entry_matrix}: "
                            f"Filter evaluation failed - {e}"
                        )
                        continue

                # Resolve remaining template variables from entry metadata
                action_inputs = self._resolve_template_variables(
                    resolved_inputs, flat_meta
                )

                # Validate action parameters
                try:
                    self.action_registry.validate_action_parameters(
                        provider_name, action_inputs
                    )
                except ActionValidationError as e:
                    errors.append(
                        f"Step '{step_name}' entry {entry_matrix}: {e}"
                    )

        return errors

    def _validate_create_entries(
        self,
        step: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
    ) -> List[str]:
        """Validate CREATE pattern entries by expanding matrix.

        Validates parameters for each matrix combination.

        Args:
            step: Step configuration dictionary
            jobs: Expanded matrix combinations
            workflow: Full workflow dictionary
            cli_params: CLI parameters

        Returns:
            List of validation error messages
        """
        from causaliq_core import ActionValidationError

        errors: List[str] = []
        step_name = step.get("name", "unnamed")
        provider_name = str(step.get("uses", ""))
        step_inputs = step.get("with", {})

        for job in jobs:
            # Combine all variable sources
            variables = {
                **workflow,
                **job,
                **cli_params,
            }

            # Resolve template variables
            resolved_inputs = self._resolve_template_variables(
                step_inputs, variables
            )

            # Add implicit matrix variables
            for matrix_var, matrix_val in job.items():
                if matrix_var not in resolved_inputs:
                    resolved_inputs[matrix_var] = matrix_val

            # Validate action parameters
            try:
                self.action_registry.validate_action_parameters(
                    provider_name, resolved_inputs
                )
            except ActionValidationError as e:
                errors.append(f"Step '{step_name}' {job}: {e}")

        return errors

    def _validate_aggregation_entries(
        self,
        step: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        workflow: Dict[str, Any],
        cli_params: Dict[str, Any],
    ) -> List[str]:
        """Validate AGGREGATE pattern entries.

        Validates parameters for each matrix combination, scanning input
        caches for matching entries.

        Args:
            step: Step configuration dictionary
            jobs: Expanded matrix combinations
            workflow: Full workflow dictionary
            cli_params: CLI parameters

        Returns:
            List of validation error messages
        """
        from causaliq_core import ActionValidationError

        errors: List[str] = []
        step_name = step.get("name", "unnamed")
        provider_name = str(step.get("uses", ""))
        step_inputs = step.get("with", {})
        matrix = workflow.get("matrix", {})

        # Get aggregation config for scanning
        agg_config = self._get_aggregation_config(step, matrix)

        for job in jobs:
            # Combine all variable sources
            variables = {
                **workflow,
                **job,
                **cli_params,
            }

            # Resolve template variables
            resolved_inputs = self._resolve_template_variables(
                step_inputs, variables
            )

            # Add implicit matrix variables
            for matrix_var, matrix_val in job.items():
                if matrix_var not in resolved_inputs:
                    resolved_inputs[matrix_var] = matrix_val

            # Scan aggregation inputs for this matrix combo
            if agg_config is not None:
                matching_entries = self._scan_aggregation_inputs(
                    agg_config, job
                )
                resolved_inputs["_aggregation_entries"] = matching_entries
                resolved_inputs.pop("aggregate", None)

            # Validate action parameters
            try:
                self.action_registry.validate_action_parameters(
                    provider_name, resolved_inputs
                )
            except ActionValidationError as e:
                errors.append(f"Step '{step_name}' {job}: {e}")

        return errors

    def execute_workflow(
        self,
        workflow: Dict[str, Any],
        mode: str = "dry-run",
        cli_params: Optional[Dict[str, Any]] = None,
        step_logger: Optional[
            Callable[[str, str, str, Dict[str, Any]], None]
        ] = None,
    ) -> List[Dict[str, Any]]:
        """Execute complete workflow with matrix expansion.

        Uses two-pass execution:

        1. Validation pass: Iterates all entries (matrix combos/cache
           entries) and validates action parameters. This catches semantic
           errors like undefined filter variables before any execution.
        2. Execution pass: If validation passes, executes the workflow.

        Caching is controlled at the step level via the 'output' parameter
        in each step's 'with' block. Each step can write to its own cache.

        Args:
            workflow: Parsed workflow dictionary
            mode: Execution mode ('dry-run', 'run', 'compare')
            cli_params: Additional parameters from CLI
            step_logger: Optional function to log step execution
                (action_method, step_name, status, matrix_values)

        Returns:
            List of job results from matrix expansion

        Raises:
            WorkflowExecutionError: If validation or execution fails
        """
        if cli_params is None:
            cli_params = {}

        try:
            # Pass 1: Validate all entries before execution
            validation_errors = self._validate_all_entries(
                workflow, cli_params
            )
            if validation_errors:
                raise WorkflowExecutionError(
                    f"Entry validation failed: {'; '.join(validation_errors)}"
                )

            # Pass 2: Execute workflow
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
        step_logger: Optional[
            Callable[[str, str, str, Dict[str, Any]], None]
        ] = None,
    ) -> Dict[str, Any]:
        """Execute single job with resolved matrix variables.

        Args:
            workflow: Base workflow configuration
            job: Job with resolved matrix variables
            context: Workflow context
            cli_params: CLI parameters
            step_logger: Optional function to log step execution

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

                # Handle UPDATE pattern: process all entries in input cache
                # UPDATE mode is activated when action declares UPDATE pattern
                # and step has input pointing to .db cache file.
                if self._is_update_step(step, matrix):
                    # Dry-run for UPDATE steps - scan cache and log per-entry
                    if context.mode == "dry-run":
                        entry_counts = self._scan_update_step_entries(
                            step, resolved_inputs, step_logger
                        )
                        step_results[step_name] = {
                            "status": "would_execute",
                            **entry_counts,
                        }
                        continue

                    # Execute UPDATE step (processes all cache entries)
                    # Per-entry logging happens inside _execute_update_step
                    step_result = self._execute_update_step(
                        step, resolved_inputs, context, step_logger
                    )

                    step_results[step_name] = step_result
                    continue  # Skip normal execution path

                # Handle step-level cache from output parameter
                output_path = resolved_inputs.pop("output", None)
                step_cache = None

                # Check if output path is valid for caching
                has_output = (
                    output_path is not None
                    and str(output_path).lower() != "none"
                )

                # Dry-run mode: check what would happen without executing
                if context.mode == "dry-run":
                    from pathlib import Path

                    from causaliq_workflow.cache import WorkflowCache

                    # Check if entry would be skipped (already exists)
                    would_skip = False
                    if has_output and Path(output_path).exists():
                        with WorkflowCache(output_path) as check_cache:
                            would_skip = check_cache.exists(
                                context.matrix_values
                            )

                    # Log what would happen in a real run
                    if step_logger:
                        action_method = resolved_inputs.get(
                            "action", "default"
                        )
                        status = (
                            "WOULD SKIP" if would_skip else "WOULD EXECUTE"
                        )
                        step_logger(
                            action_method,
                            step_name,
                            status,
                            context.matrix_values,
                        )

                    step_results[step_name] = {
                        "status": (
                            "would_skip" if would_skip else "would_execute"
                        )
                    }
                    continue

                # Run/force mode: actually execute
                should_cache = has_output and context.mode in ("run", "force")
                if should_cache:
                    from causaliq_workflow.cache import WorkflowCache

                    step_cache = WorkflowCache(output_path)
                    step_cache.open()
                    context.cache = step_cache

                    # Conservative execution: skip if entry already exists
                    # Applies to CREATE and AGGREGATE patterns
                    # Bypassed in force mode
                    if context.mode != "force" and step_cache.exists(
                        context.matrix_values
                    ):
                        # Log skip if logger provided
                        if step_logger:
                            action_method = resolved_inputs.get(
                                "action", "default"
                            )
                            step_logger(
                                action_method,
                                step_name,
                                "SKIPPED",
                                context.matrix_values,
                            )

                        step_results[step_name] = {"status": "skipped"}
                        step_cache.close()
                        context.cache = None
                        continue

                try:
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
                        action_method = resolved_inputs.get(
                            "action", "default"
                        )
                        result_status = step_result.get("status", "unknown")
                        if result_status == "success":
                            status = (
                                "FORCED"
                                if context.mode == "force"
                                else "EXECUTED"
                            )
                        else:
                            status = "FAILED"
                        step_logger(
                            action_method,
                            step_name,
                            status,
                            context.matrix_values,
                        )

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
