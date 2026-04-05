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
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

if TYPE_CHECKING:
    from causaliq_core import ActionPattern

    from causaliq_workflow.cache import WorkflowCache

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


def _normalise_matrix_value(value: Any) -> Any:
    """Normalise matrix value for case-insensitive comparison.

    Numeric suffixes (k, K, m, M, g, G, t, T) are normalised to lowercase
    for comparison. This allows workflows to use '1K' or '1k' interchangeably.

    Args:
        value: Matrix value to normalise

    Returns:
        Normalised value (string lowercased if it has numeric suffix,
        otherwise unchanged)
    """
    if not isinstance(value, str):
        return value
    # Match numeric values with optional suffix (e.g., "100", "1k", "10M")
    # Normalise suffix to lowercase for comparison
    if re.match(r"^\d+[kKmMgGtT]?$", value):
        return value.lower()
    return value


def _matrix_values_match(
    entry_values: Dict[str, Any],
    target_values: Dict[str, Any],
    matrix_vars: List[str],
) -> bool:
    """Check if entry matrix values match target values.

    Comparison is case-insensitive for numeric suffixes (k, M, etc).

    A ``None`` value on either side (target or entry) means the
    dimension is not applicable and is treated as a wildcard
    (always matches).  A *missing* key on the entry side
    (dimension absent from the input cache) is also treated as a
    wildcard so that caches with fewer dimensions can still be
    consumed by broader matrices.

    Args:
        entry_values: Matrix values from cache entry.
        target_values: Target matrix values to match against.
        matrix_vars: List of matrix variable names to compare.

    Returns:
        True if all matrix variables match.
    """
    _SENTINEL = object()
    for var in matrix_vars:
        target_val = target_values.get(var)
        entry_val = entry_values.get(var, _SENTINEL)
        # Missing key in entry — dimension absent, wildcard
        if entry_val is _SENTINEL:
            continue
        # None on either side — N/A dimension, wildcard
        if target_val is None or entry_val is None:
            continue
        entry_val = _normalise_matrix_value(entry_val)
        target_val = _normalise_matrix_value(target_val)
        if entry_val != target_val:
            return False
    return True


def _derive_matrix_from_caches(
    cache_paths: List[str],
) -> Tuple[List[str], Dict[str, List[Any]]]:
    """Derive matrix keys and values from input caches.

    Scans all input caches, extracts matrix keys from entries, and validates
    that all caches have the same key structure. Returns the unique key names
    and a dictionary mapping each key to its unique values across all entries.

    Args:
        cache_paths: List of paths to workflow cache files (.db)

    Returns:
        Tuple of (matrix_keys, matrix_dict) where:
        - matrix_keys: List of matrix variable names
        - matrix_dict: Dict mapping each key to list of unique values

    Raises:
        WorkflowExecutionError: If caches have inconsistent matrix keys
    """
    from pathlib import Path

    from causaliq_workflow.cache import WorkflowCache

    all_keys: Optional[Set[str]] = None
    value_sets: Dict[str, Set[Any]] = {}

    for cache_path in cache_paths:
        if not Path(cache_path).exists():
            continue

        with WorkflowCache(cache_path) as cache:
            entries = cache.list_entries()

            for entry_info in entries:
                entry_matrix = entry_info.get("matrix_values", {})
                entry_keys = set(entry_matrix.keys())

                if all_keys is None:
                    all_keys = entry_keys
                    value_sets = {k: set() for k in entry_keys}
                elif entry_keys != all_keys:
                    raise WorkflowExecutionError(
                        f"Input caches have inconsistent matrix keys. "
                        f"Expected {sorted(all_keys)}, "
                        f"found {sorted(entry_keys)} in '{cache_path}'"
                    )

                # Collect unique values for each key
                for key, val in entry_matrix.items():
                    value_sets[key].add(val)

    if all_keys is None:
        return [], {}

    # Convert sets to sorted lists for deterministic ordering
    matrix_keys = sorted(all_keys)
    matrix_dict = {k: sorted(value_sets[k], key=str) for k in matrix_keys}

    return matrix_keys, matrix_dict


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

        except WorkflowExecutionError:
            # Re-raise our own errors without wrapping
            raise
        except (WorkflowValidationError, FileNotFoundError) as e:
            raise WorkflowExecutionError(f"Workflow parsing failed: {e}")
        except Exception as e:
            raise WorkflowExecutionError(
                f"Unexpected error parsing workflow: {e}"
            ) from e

    def _expand_range_value(self, value: Any) -> List[Any]:
        """Expand a range string to a list of integers.

        Detects strings like "0-24" and expands them to [0, 1, 2, ..., 24].
        Non-range values are returned as-is in a single-element list.

        Args:
            value: A matrix value that may be a range string

        Returns:
            List of expanded values (or single-element list for non-ranges)
        """
        if not isinstance(value, str):
            return [value]

        value = value.strip()

        # Check for range pattern: digits-digits
        if "-" in value:
            parts = value.split("-")
            if len(parts) == 2:
                try:
                    start = int(parts[0].strip())
                    end = int(parts[1].strip())
                    if start <= end:
                        return list(range(start, end + 1))
                except ValueError:
                    pass  # Not a valid range, return as-is

        return [value]

    def _expand_matrix_values(self, values: List[Any]) -> List[Any]:
        """Expand range strings in a list of matrix values.

        Args:
            values: List of matrix values that may contain range strings

        Returns:
            Expanded list with ranges converted to individual values
        """
        expanded: List[Any] = []
        for value in values:
            expanded.extend(self._expand_range_value(value))
        return expanded

    def expand_matrix(
        self, matrix: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """Expand matrix variables into individual job configurations.

        Generates all combinations from matrix variables using cartesian
        product. Each combination becomes a separate job configuration.

        Range strings like "0-24" are automatically expanded to individual
        integer values [0, 1, 2, ..., 24].

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
            # Expand any range strings in values
            value_lists = [
                self._expand_matrix_values(vals) for vals in matrix.values()
            ]

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

    def _derive_workflow_matrix(
        self,
        workflow: Dict[str, Any],
    ) -> Dict[str, List[Any]]:
        """Get effective matrix for workflow, deriving from cache if needed.

        If the workflow has an explicit matrix, returns it. Otherwise, checks
        for AGGREGATE pattern steps and derives matrix from their input caches.

        Args:
            workflow: Parsed workflow dictionary

        Returns:
            Effective matrix dictionary (may be empty for non-matrix workflows)
        """
        from causaliq_core import ActionPattern

        # If explicit matrix exists, use it
        explicit_matrix: Dict[str, List[Any]] = workflow.get("matrix", {})
        if explicit_matrix:
            return explicit_matrix

        # Check for AGGREGATE steps that need derived matrix
        for step in workflow.get("steps", []):
            step_inputs = step.get("with", {})
            provider_name = step.get("uses")
            action_name = step_inputs.get("action")

            if not provider_name or not action_name:
                continue

            # Check if action is AGGREGATE pattern
            try:
                pattern = self.action_registry.get_action_pattern(
                    provider_name, action_name
                )
            except Exception:
                continue

            if pattern != ActionPattern.AGGREGATE:
                continue

            # Check if step has cache input (.db files in input parameter)
            input_param = step_inputs.get("input")
            cache_paths: List[str] = []
            if input_param:
                inputs = (
                    [input_param]
                    if isinstance(input_param, str)
                    else list(input_param) if input_param else []
                )
                cache_paths = [
                    p for p in inputs if str(p).lower().endswith(".db")
                ]

            if cache_paths:
                # Derive matrix from cache
                _, derived_matrix = _derive_matrix_from_caches(cache_paths)
                if derived_matrix:
                    return derived_matrix

        return {}

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
        """Validate template variables in workflow.

        Performs two validations:
        1. All template variables must exist in the available context
           (workflow variables, matrix variables, or built-ins).
        2. All matrix variables must be used in at least one CREATE step's
           template. AGGREGATE steps use matrix for grouping (not templating)
           and UPDATE steps don't use explicit matrix.

        For UPDATE pattern steps, template variables not in the workflow
        context are allowed as they will be resolved from entry metadata
        at runtime.

        Args:
            workflow: Parsed workflow dictionary

        Raises:
            WorkflowExecutionError: If unknown template variables found
                or if matrix variables are not used in any CREATE step
        """
        from causaliq_core import ActionPattern

        # Build available context
        available_variables = {"id", "description"}

        # Add workflow variables (excluding workflow metadata fields)
        workflow_vars = {
            k
            for k, v in workflow.items()
            if k not in {"id", "description", "matrix", "steps"}
        }
        available_variables.update(workflow_vars)

        # Get matrix variables if present
        matrix_vars = set(workflow.get("matrix", {}).keys())
        available_variables.update(matrix_vars)

        # Collect template variables per step type
        update_step_variables: Set[str] = set()
        create_step_variables: Set[str] = set()

        for step in workflow.get("steps", []):
            step_vars: Set[str] = set()
            self._collect_template_variables(step, step_vars)

            # Check step pattern type
            is_update = self._is_update_pattern_step(step, workflow)
            is_aggregate = self._is_aggregate_pattern_step(step, workflow)

            if is_update:
                update_step_variables.update(step_vars)
            elif is_aggregate:
                # AGGREGATE steps use matrix for grouping, not templating
                # Still check for unknown variables but don't require matrix
                # usage
                pass
            else:
                # CREATE pattern step
                create_step_variables.update(step_vars)

        # Check non-UPDATE variables for unknown references
        # (AGGREGATE step variables are checked but not collected for matrix
        # usage validation)
        all_non_update_vars: Set[str] = set()
        has_create_steps = False
        for step in workflow.get("steps", []):
            is_update = self._is_update_pattern_step(step, workflow)
            is_aggregate = self._is_aggregate_pattern_step(step, workflow)

            if not is_update:
                step_vars = set()
                self._collect_template_variables(step, step_vars)
                all_non_update_vars.update(step_vars)

            # Check if step is CREATE pattern (ignoring workflow context)
            # This determines if matrix usage validation applies
            step_pattern = self._get_step_action_pattern(step)
            if step_pattern == ActionPattern.CREATE:
                has_create_steps = True

        unknown_variables = all_non_update_vars - available_variables

        if unknown_variables:
            unknown_list = sorted(unknown_variables)
            available_list = sorted(available_variables)
            raise WorkflowExecutionError(
                f"Unknown template variables: {unknown_list}. "
                f"Available variables: {available_list}"
            )

        # Validate all matrix variables are used in CREATE steps.
        # Only applies when there are CREATE pattern steps in the
        # workflow.  Variables whose only values are None are exempt
        # because they represent dimensions that are not applicable
        # to this workflow (e.g. sample_size=[None] for LLM-only
        # steps) and are used solely as cache key placeholders.
        if matrix_vars and has_create_steps:
            matrix_def = workflow.get("matrix", {})
            unused_matrix_vars = matrix_vars - create_step_variables
            unused_matrix_vars = {
                var
                for var in unused_matrix_vars
                if not all(v is None for v in matrix_def.get(var, []))
            }
            if unused_matrix_vars:
                unused_list = sorted(unused_matrix_vars)
                raise WorkflowExecutionError(
                    f"Matrix variables not used in any step: {unused_list}. "
                    f"Each matrix variable must appear in at least one "
                    f"{{{{variable}}}} template in CREATE pattern steps."
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
        input_param = step_inputs.get("input")
        has_cache_input = False
        if input_param:
            if isinstance(input_param, str):
                inputs = [input_param]
            elif isinstance(input_param, list):
                inputs = list(input_param)
            else:
                inputs = []
            has_cache_input = any(
                str(p).lower().endswith(".db") for p in inputs
            )

        if not has_cache_input:
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
        1. The workflow has a matrix definition AND step has cache input, OR
        2. The action declares AGGREGATE pattern AND step has cache input
           (matrix will be derived from input cache)

        Args:
            step: Step configuration dictionary
            matrix: Workflow matrix definition

        Returns:
            True if step should run in aggregation mode
        """
        from causaliq_core import ActionPattern

        step_inputs = step.get("with", {})

        # Check if step has cache input (.db files in input parameter)
        has_cache_input = False
        input_param = step_inputs.get("input")
        if input_param:
            if isinstance(input_param, str):
                inputs = [input_param]
            elif isinstance(input_param, list):
                inputs = list(input_param)
            else:
                # Non-string, non-list input cannot be .db files
                inputs = []
            has_cache_input = any(
                str(p).lower().endswith(".db") for p in inputs
            )

        if not has_cache_input:
            return False

        # Check the action's declared pattern
        provider_name = step.get("uses")
        action_name = step_inputs.get("action")
        if provider_name and action_name:
            try:
                pattern = self.action_registry.get_action_pattern(
                    provider_name, action_name
                )
                # UPDATE pattern has its own execution path
                if pattern == ActionPattern.UPDATE:
                    return False
                # Explicit AGGREGATE pattern is always aggregation
                if pattern == ActionPattern.AGGREGATE:
                    return True
            except Exception:
                pass

        # If matrix is provided with cache input and no explicit
        # pattern, treat as aggregation (legacy behaviour)
        if matrix:
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

        When the workflow has a matrix, the UPDATE step processes
        only the entry matching the current matrix combination.
        Without a matrix, all entries are processed.

        Args:
            step: Step configuration dictionary
            matrix: Workflow matrix definition

        Returns:
            True if step should run in UPDATE mode
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
        except (AttributeError, KeyError):
            return False
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

        UPDATE mode processes all entries in one or more input caches:
        1. Opens each input cache
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
        input_param = resolved_inputs.get("input")
        filter_expr = resolved_inputs.get("filter")

        # Get provider name for metadata structuring
        action_class = self.action_registry.get_action_class(action_name)
        provider_name = getattr(action_class, "name", action_name)

        # Validate input is provided (should be guaranteed by validation)
        if input_param is None:
            return {
                "status": "error",
                "error": "UPDATE action requires 'input' parameter",
                "entries_processed": 0,
                "entries_skipped": 0,
                "entries_updated": 0,
            }

        # Normalise to list of paths
        if isinstance(input_param, str):
            input_paths = [input_param]
        elif isinstance(input_param, list):
            input_paths = list(input_param)
        else:
            return {
                "status": "error",
                "error": (
                    f"'input' must be string or list, "
                    f"got {type(input_param).__name__}"
                ),
                "entries_processed": 0,
                "entries_skipped": 0,
                "entries_updated": 0,
            }

        # Check all input caches exist before processing
        missing = [p for p in input_paths if not Path(p).exists()]
        if missing:
            return {
                "status": "error",
                "error": f"Input cache(s) do not exist: {', '.join(missing)}",
                "entries_processed": 0,
                "entries_skipped": 0,
                "entries_updated": 0,
            }

        entries_processed = 0
        entries_skipped = 0
        entries_updated = 0
        errors: List[str] = []

        # When running inside a matrix job, process only the entry
        # matching the current matrix combination.  Without a matrix,
        # iterate all entries in the cache (original behaviour).
        matrix_values = getattr(context, "matrix_values", None)

        for input_path in input_paths:
            with WorkflowCache(input_path) as cache:
                if matrix_values:
                    entries = [{"matrix_values": matrix_values}]
                else:
                    entries = cache.list_entries()

                # Pre-resolve random() calls in filter
                resolved_filter, extra_names = self._resolve_filter(
                    filter_expr, cache, entries
                )

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
                    if resolved_filter:
                        try:
                            if not evaluate_filter(
                                resolved_filter,
                                {**flat_meta, **extra_names},
                            ):
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

                    # Resolve any remaining template variables from entry
                    # metadata. This enables UPDATE steps to use {{network}},
                    # {{sample_size}} etc. resolved from each entry's metadata
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
        context: Optional[WorkflowContext] = None,
        step_logger: Optional[
            Callable[[str, str, str, Dict[str, Any]], None]
        ] = None,
    ) -> Dict[str, int]:
        """Scan UPDATE step cache(s) to count entries that would be processed.

        Used in dry-run mode to report how many entries would be updated
        vs skipped (due to conservative execution - action already applied).
        Optionally logs per-entry status via step_logger.

        Args:
            step: Step configuration dictionary
            resolved_inputs: Resolved action inputs
            context: Workflow context
            step_logger: Optional logging function for per-entry status

        Returns:
            Dictionary with would_process and would_skip counts
        """
        from pathlib import Path

        from causaliq_core.utils import evaluate_filter

        from causaliq_workflow.cache import WorkflowCache

        action_name = step["uses"]
        action_method = resolved_inputs.get("action", "default")
        input_param = resolved_inputs.get("input")
        filter_expr = resolved_inputs.get("filter")

        # Get provider name for metadata checking
        action_class = self.action_registry.get_action_class(action_name)
        provider_name = getattr(action_class, "name", action_name)

        would_process = 0
        would_skip = 0

        if input_param is None:
            return {"would_process": 0, "would_skip": 0}

        # Normalise to list of paths
        if isinstance(input_param, str):
            input_paths = [input_param]
        elif isinstance(input_param, list):
            input_paths = list(input_param)
        else:
            return {"would_process": 0, "would_skip": 0}

        # When running inside a matrix job, target only the matching
        # entry.  Without a matrix, scan all entries.
        matrix_values = getattr(context, "matrix_values", None)

        for input_path in input_paths:
            if not Path(input_path).exists():
                # Cache does not exist yet.  When targeting a specific
                # matrix entry we can assume the upstream CREATE step
                # will produce it, so count as "would execute".
                if matrix_values:
                    would_process += 1
                    if step_logger:
                        step_logger(
                            action_method,
                            step.get("name", "unknown"),
                            "WOULD EXECUTE",
                            matrix_values,
                        )
                continue

            with WorkflowCache(input_path) as cache:
                if matrix_values:
                    entries = [{"matrix_values": matrix_values}]
                else:
                    entries = cache.list_entries()

                # Pre-resolve random() calls in filter
                resolved_filter, extra_names = self._resolve_filter(
                    filter_expr, cache, entries
                )

                for entry_info in entries:
                    entry_matrix = entry_info.get("matrix_values", {})

                    # Get full entry
                    full_entry = cache.get(entry_matrix)
                    if full_entry is None:
                        # Entry does not exist yet.  Same reasoning
                        # as missing cache above.
                        if matrix_values:
                            would_process += 1
                            if step_logger:
                                step_logger(
                                    action_method,
                                    step.get("name", "unknown"),
                                    "WOULD EXECUTE",
                                    entry_matrix,
                                )
                        continue

                    # Flatten metadata for filter evaluation
                    flat_meta = self._flatten_metadata(
                        entry_matrix, full_entry.metadata
                    )

                    # Apply filter expression if present
                    if resolved_filter:
                        try:
                            if not evaluate_filter(
                                resolved_filter,
                                {**flat_meta, **extra_names},
                            ):
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
                            would_skip += 1
                            if step_logger:
                                step_logger(
                                    action_method,
                                    step.get("name", "unknown"),
                                    "WOULD IGNORE",
                                    entry_matrix,
                                )
                            continue

                    # Conservative execution check
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
        If no explicit matrix is provided but the action is AGGREGATE pattern,
        matrix keys are derived from the input cache entries.

        Args:
            step: Step configuration dictionary
            matrix: Workflow matrix definition

        Returns:
            AggregationConfig if aggregation mode, None otherwise
        """
        if not self._is_aggregation_step(step, matrix):
            return None

        step_inputs = step.get("with", {})

        # Get cache paths from 'input' parameter (.db files only)
        input_param = step_inputs.get("input")

        # Collect cache paths (.db files only)
        input_caches: List[str] = []
        if input_param:
            inputs = (
                [input_param]
                if isinstance(input_param, str)
                else (list(input_param) if input_param else [])
            )
            # Filter to only .db files for cache scanning
            input_caches = [
                str(p) for p in inputs if str(p).lower().endswith(".db")
            ]

        # Determine matrix variables
        if matrix:
            # Use explicit matrix keys
            matrix_vars = list(matrix.keys())
        else:
            # Derive matrix keys from input caches
            matrix_vars, _ = _derive_matrix_from_caches(input_caches)

        return AggregationConfig(
            input_caches=input_caches,
            filter_expr=step_inputs.get("filter"),
            matrix_vars=matrix_vars,
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
            - entry: The full CacheEntry object
            - objects: Dict mapping object names to their content

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

        # Pre-resolve random() calls across all input caches
        resolved_filter = config.filter_expr
        extra_names: Dict[str, Any] = {}
        if config.filter_expr and "random(" in config.filter_expr:
            from causaliq_core.utils import resolve_random_calls

            all_meta: List[Dict[str, Any]] = []
            for cp in config.input_caches:
                if not Path(cp).exists():
                    continue
                try:
                    with WorkflowCache(cp) as c:
                        for ei in c.list_entries():
                            em = ei.get("matrix_values", {})
                            fe = c.get(em)
                            if fe is not None:
                                all_meta.append(
                                    self._flatten_metadata(em, fe.metadata)
                                )
                except Exception:
                    continue
            resolved_filter, extra_names = resolve_random_calls(
                config.filter_expr, all_meta
            )

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

                        # Get full entry to access metadata
                        full_entry = cache.get(entry_matrix)
                        if full_entry is None:
                            continue

                        # Flatten metadata for filter evaluation
                        flat_meta = self._flatten_metadata(
                            entry_matrix, full_entry.metadata
                        )

                        # Apply filter expression if present
                        if resolved_filter:
                            try:
                                if not evaluate_filter(
                                    resolved_filter,
                                    {**flat_meta, **extra_names},
                                ):
                                    total_filtered += 1
                                    continue
                            except Exception:
                                # Filter evaluation error - skip entry
                                total_filtered += 1
                                continue

                        # Check if entry matches current matrix values
                        # (case-insensitive for numeric suffixes like 1k/1K)
                        matches = _matrix_values_match(
                            entry_matrix,
                            matrix_values,
                            config.matrix_vars,
                        )

                        if matches:
                            total_matched += 1
                            # Extract object contents for easy access
                            objects_content = {
                                name: obj.content
                                for name, obj in full_entry.objects.items()
                            }
                            matching_entries.append(
                                {
                                    "matrix_values": entry_matrix,
                                    "metadata": full_entry.metadata,
                                    "cache_path": str(cache_path),
                                    "entry_hash": entry_info.get("hash"),
                                    "entry": full_entry,
                                    "objects": objects_content,
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

    def _resolve_filter(
        self,
        filter_expr: Optional[str],
        cache: "WorkflowCache",
        entries: List[Dict[str, Any]],
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Pre-resolve ``random()`` calls in a filter expression.

        Scans *entries* from *cache* to build the distinct-value
        populations needed by ``random(count, seed)`` patterns,
        then returns a rewritten expression and a dictionary of
        pre-computed frozen sets.

        When *filter_expr* contains no ``random()`` calls the
        original expression is returned unchanged with an empty
        dictionary.

        Args:
            filter_expr: Filter expression string, or ``None``.
            cache: Open cache used to retrieve full entries.
            entries: Entry list from ``cache.list_entries()``.

        Returns:
            Tuple of *(resolved_expression, extra_names)*.
        """
        if not filter_expr or "random(" not in filter_expr:
            return filter_expr, {}

        from causaliq_core.utils import resolve_random_calls

        all_meta: List[Dict[str, Any]] = []
        for entry_info in entries:
            entry_matrix = entry_info.get("matrix_values", {})
            full_entry = cache.get(entry_matrix)
            if full_entry is not None:
                all_meta.append(
                    self._flatten_metadata(entry_matrix, full_entry.metadata)
                )

        return resolve_random_calls(filter_expr, all_meta)

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
            raise WorkflowExecutionError("; ".join(action_errors))

        # Validate action patterns
        pattern_errors = self._validate_action_patterns(workflow)
        if pattern_errors:
            raise WorkflowExecutionError("; ".join(pattern_errors))

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
                # Matrix can be explicit or derived from cache input
                if not has_matrix and not has_cache_input:
                    errors.append(
                        f"Step '{step_name}': AGGREGATE pattern requires "
                        f"workflow 'matrix' definition or cache input"
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

    def _deduplicate_errors(self, errors: List[str]) -> List[str]:
        """Deduplicate validation errors by grouping similar messages.

        Groups errors that have the same core message (after the step
        prefix) and returns a unique list without repetition.

        Args:
            errors: List of validation error strings

        Returns:
            Deduplicated list of unique errors
        """
        # Pattern to extract step name and core message
        # Format: "Step 'name': message"
        pattern = re.compile(r"^Step '([^']+)':\s*(.+)$")

        # Track unique (step_name, message) pairs
        seen: Set[tuple[str, str]] = set()
        result: List[str] = []

        for error in errors:
            match = pattern.match(error)
            if match:
                step_name = match.group(1)
                message = match.group(2)
                key = (step_name, message)
                if key not in seen:
                    seen.add(key)
                    result.append(f"Step '{step_name}': {message}")
            else:
                # Keep unmatched errors as-is
                if error not in result:
                    result.append(error)

        return result

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
            step_name = step.get("name", "unnamed")
            provider_name = step.get("uses")
            if not provider_name:
                continue

            step_inputs = step.get("with", {})
            action_name = step_inputs.get("action")
            if not action_name:
                errors.append(
                    f"Step '{step_name}': Missing 'action' parameter"
                )
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
                # AGGREGATE pattern: validate per matrix combo.
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

            # Pre-resolve random() calls in filter
            resolved_filter, extra_names = self._resolve_filter(
                filter_expr, cache, entries
            )

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
                if resolved_filter:
                    try:
                        if not evaluate_filter(
                            resolved_filter,
                            {**flat_meta, **extra_names},
                        ):
                            continue  # Would be filtered out
                    except FilterExpressionError as e:
                        # Semantic filter error - undefined variable
                        errors.append(
                            f"Step '{step_name}': Filter error - {e}"
                        )
                        continue
                    except Exception as e:
                        errors.append(
                            f"Step '{step_name}': "
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
                    errors.append(f"Step '{step_name}': {e}")

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
                errors.append(f"Step '{step_name}': {e}")

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

        # Track entry fingerprints per output matrix combo to
        # detect silent duplication (different combos producing
        # identical aggregation input sets).
        fingerprints: Dict[frozenset, Dict[str, Any]] = {}

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

            # Note: For AGGREGATE pattern, matrix variables are NOT added
            # as implicit parameters. They are used only for filtering/
            # grouping entries via _scan_aggregation_inputs, not as action
            # parameters. The action receives _aggregation_entries instead.

            # Scan aggregation inputs for this matrix combo
            if agg_config is not None:
                # Use the resolved filter (with template variables
                # substituted) instead of the raw filter.
                resolved_filter = resolved_inputs.get("filter")
                scan_config = agg_config
                if resolved_filter != agg_config.filter_expr:
                    scan_config = AggregationConfig(
                        input_caches=agg_config.input_caches,
                        filter_expr=resolved_filter,
                        matrix_vars=agg_config.matrix_vars,
                    )
                matching_entries = self._scan_aggregation_inputs(
                    scan_config, job
                )
                resolved_inputs["_aggregation_entries"] = matching_entries
                resolved_inputs.pop("aggregate", None)

                # Build fingerprint from matched entry hashes.
                # Skip empty sets — the input cache may not
                # exist yet (created by an earlier step).
                fp = frozenset(
                    e.get("entry_hash", id(e)) for e in matching_entries
                )
                if fp and fp in fingerprints:
                    prev = fingerprints[fp]
                    diff = {
                        k: (prev[k], job[k])
                        for k in job
                        if job[k] != prev.get(k)
                    }
                    import warnings

                    warnings.warn(
                        f"Step '{step_name}': matrix combos"
                        f" differ only in {diff} but"
                        f" select identical aggregation"
                        f" entries — the differing"
                        f" dimension(s) may need a filter"
                        f" or should be removed from the"
                        f" matrix",
                        stacklevel=1,
                    )
                elif fp:
                    fingerprints[fp] = job

            # Validate action parameters
            try:
                self.action_registry.validate_action_parameters(
                    provider_name, resolved_inputs
                )
            except ActionValidationError as e:
                errors.append(f"Step '{step_name}': {e}")

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
                deduped = self._deduplicate_errors(validation_errors)
                raise WorkflowExecutionError("; ".join(deduped))

            # Validate-only mode: skip execution pass
            if mode == "validate":
                return []

            # Pass 2: Execute workflow
            # Derive matrix from explicit definition or from input caches
            matrix = self._derive_workflow_matrix(workflow)
            jobs = self.expand_matrix(matrix)
            total_jobs = len(jobs)

            results = []
            for job_index, job in enumerate(jobs):
                # Create workflow context (cache set per-step)
                context = WorkflowContext(
                    mode=mode,
                    matrix=matrix,
                    matrix_values=job,
                    cache=None,
                    job_index=job_index,
                    total_jobs=total_jobs,
                )

                # Execute job steps
                job_result = self._execute_job(
                    workflow,
                    job,
                    context,
                    cli_params,
                    step_logger,
                )
                results.append(job_result)

            return results

        except WorkflowExecutionError:
            # Re-raise our own errors without wrapping
            raise
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
                # Matrix variables are available for substitution via {{var}}
                # but are NOT automatically passed as action parameters.
                # This ensures explicit specification in with: clause.
                resolved_inputs = self._resolve_template_variables(
                    action_inputs, variables
                )

                # Handle aggregation mode: scan input caches for matching
                # entries. Aggregation mode is activated when step has 'input'
                # parameter and workflow has matrix definition.
                matrix = workflow.get("matrix", {})
                agg_config = self._get_aggregation_config(step, matrix)
                if agg_config is not None:
                    # Use the resolved filter (with template variables
                    # substituted) instead of the raw filter from the
                    # step definition.
                    resolved_filter = resolved_inputs.get("filter")
                    if resolved_filter != agg_config.filter_expr:
                        agg_config = AggregationConfig(
                            input_caches=agg_config.input_caches,
                            filter_expr=resolved_filter,
                            matrix_vars=agg_config.matrix_vars,
                        )
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
                            step,
                            resolved_inputs,
                            context,
                            step_logger,
                        )
                        has_work = entry_counts.get("would_process", 0) > 0
                        step_results[step_name] = {
                            "status": (
                                "would_execute" if has_work else "would_skip"
                            ),
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
                # Only .db files are workflow caches
                is_cache_output = has_output and str(
                    output_path
                ).lower().endswith(".db")

                # Dry-run mode: check what would happen without executing
                if context.mode == "dry-run":
                    from pathlib import Path

                    from causaliq_workflow.cache import WorkflowCache

                    # Check if entry would be skipped (only for .db outputs)
                    would_skip = False
                    if is_cache_output and Path(output_path).exists():
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
                # Only create cache for .db output files; other outputs (like
                # .csv or "-" for terminal) are handled directly by the action
                should_cache = is_cache_output and context.mode in (
                    "run",
                    "force",
                )
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

                # For non-cache outputs (.csv, "-", ...), pass output to action
                if has_output and not is_cache_output:
                    resolved_inputs["output"] = output_path

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

                    # Check for objects that couldn't be stored
                    # (action produced objects but no .db cache was open)
                    if (
                        context.cache is None
                        and step_result.get("status") == "success"
                        and step_result.get("objects")
                    ):
                        action_method = resolved_inputs.get(
                            "action", "default"
                        )
                        raise WorkflowExecutionError(
                            f"Step '{step_name}' (action '{action_method}') "
                            f"produced objects but no workflow cache is open "
                            f"to store them. Use 'output: path/to/cache.db' "
                            f"to specify a workflow cache destination."
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

            # Restore original matrix values after each step so
            # that dedup projection for one step does not leak
            # into the next step in the same job.
            context.matrix_values = job

        return {
            "job": job,
            "steps": step_results,
            "context": context,
        }
