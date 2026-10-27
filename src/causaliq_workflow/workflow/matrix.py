"""Matrix expansion, derivation and value matching."""

import itertools
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.errors import WorkflowExecutionError
from causaliq_workflow.workflow.frames import is_workflow_call_step
from causaliq_workflow.workflow.parameters import _call_parameters_vary


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


def _canonical_scalar(value: Any) -> str:
    """Return a canonical comparison key for a matrix scalar value.

    YAML parsing, a cache written by an earlier run, or a CLI override
    may represent the same dimension value as a number or as text. Both
    forms compare equal, so aggregation matches across those sources.

    Args:
        value: Matrix value to canonicalise.

    Returns:
        Canonical text for the value.
    """
    normalised = _normalise_matrix_value(value)
    if isinstance(normalised, bool):
        return "true" if normalised else "false"
    return str(normalised)


def _matrix_values_match(
    entry_values: Dict[str, Any],
    target_values: Dict[str, Any],
    matrix_vars: List[str],
) -> bool:
    """Check if entry matrix values match target values.

    Comparison is case-insensitive for numeric suffixes (k, M, etc).
    A number and its text spelling also compare equal, so a value
    derived from a cache and one written in the workflow match.

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
        if _canonical_scalar(entry_val) != _canonical_scalar(target_val):
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
    all_keys: Optional[Set[str]] = None
    value_sets: Dict[str, Set[Any]] = {}

    for cache_path in cache_paths:
        all_keys, value_sets = _accumulate_cache_keys(
            cache_path, all_keys, value_sets
        )

    if all_keys is None:
        return [], {}

    # Convert sets to sorted lists for deterministic ordering
    matrix_keys = sorted(all_keys)
    matrix_dict = {k: sorted(value_sets[k], key=str) for k in matrix_keys}

    return matrix_keys, matrix_dict


def _accumulate_cache_keys(
    cache_path: str,
    all_keys: Optional[Set[str]],
    value_sets: Dict[str, Set[Any]],
) -> Tuple[Optional[Set[str]], Dict[str, Set[Any]]]:
    """Accumulate matrix keys and values from a single cache file."""
    from pathlib import Path

    from causaliq_workflow.cache import WorkflowCache

    if not Path(cache_path).exists():
        return all_keys, value_sets

    with WorkflowCache(cache_path) as cache:
        for entry_info in cache.list_entries():
            entry_matrix = entry_info.get("matrix_values", {})
            all_keys, value_sets = _merge_entry_keys(
                entry_matrix, all_keys, value_sets, cache_path
            )

    return all_keys, value_sets


def _merge_entry_keys(
    entry_matrix: Dict[str, Any],
    all_keys: Optional[Set[str]],
    value_sets: Dict[str, Set[Any]],
    cache_path: str,
) -> Tuple[Optional[Set[str]], Dict[str, Set[Any]]]:
    """Merge one entry's matrix keys into the accumulated key/value sets."""
    entry_keys = set(entry_matrix.keys())

    if all_keys is None:
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

    return entry_keys, value_sets


def _cache_entry_exists(
    is_cache_output: bool,
    output_path: Any,
    matrix_values: Dict[str, Any],
) -> bool:
    """Return True when a .db output cache already holds the entry."""
    from pathlib import Path

    from causaliq_workflow.cache import WorkflowCache

    if not is_cache_output or not Path(output_path).exists():
        return False
    with WorkflowCache(output_path) as cache:
        return cache.exists(matrix_values)


def _has_cache_output(step: Dict[str, Any]) -> bool:
    """Return True when a step writes a workflow cache (``.db`` output).

    A step's output cache is what gives it a matrix dimensionality: one
    entry per key. A step whose output is not a workflow cache has no
    output keys and therefore runs once.

    Args:
        step: Step configuration dictionary.

    Returns:
        True when the step's ``output`` names a workflow cache.
    """
    output = step.get("with", {}).get("output")
    if output is None:
        return False
    return str(output).lower().endswith(".db")


def _has_file_output(step: Dict[str, Any]) -> bool:
    """Return True when a step writes a file rather than a workflow cache.

    Args:
        step: Step configuration dictionary.

    Returns:
        True when the step's ``output`` is present and is not a cache.
    """
    output = step.get("with", {}).get("output")
    if output is None:
        return False
    return not str(output).lower().endswith(".db")


def _dimension_values(value: Any) -> List[Any]:
    """Return a matrix dimension's value list for a parameter value."""
    if isinstance(value, list):
        return list(value)
    return [value]


def _matrix_overrides(
    parameters: Dict[str, Any], matrix: Dict[str, Any]
) -> Dict[str, List[Any]]:
    """Return the parameter values that replace matrix dimensions."""
    return {
        name: _dimension_values(value)
        for name, value in parameters.items()
        if name in matrix
    }


def _bind_parameters(
    workflow: Dict[str, Any], parameters: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Bind parameters to a workflow's matrix and variables.

    A parameter that names a matrix dimension replaces that dimension's
    values; every other parameter binds as a template variable. Parameters
    never add a dimension, so they are not part of a cache key.

    Args:
        workflow: Workflow dictionary to bind against.
        parameters: Parameter values from a caller or the CLI.

    Returns:
        Tuple of (workflow with overridden matrix, variable parameters).
        The input workflow is never modified.
    """
    matrix = workflow.get("matrix", {})
    overrides = _matrix_overrides(parameters, matrix)
    variables = {
        name: value for name, value in parameters.items() if name not in matrix
    }
    if not overrides:
        return workflow, variables
    return {**workflow, "matrix": {**matrix, **overrides}}, variables


def _runs_once(step: Dict[str, Any], matrix: Dict[str, Any]) -> bool:
    """Return True when a step runs once, outside matrix expansion.

    A step that writes a file rather than a workflow cache has no output
    dimensionality, so it runs once instead of once per matrix
    combination. Such a step may still read a cache (for example ``plot``
    reading a metrics cache) because it writes no cache.

    A step with a file output that declares a workflow matrix keeps its
    per-job granularity (for example ``summarise`` writing one ``.csv``
    row per combination) until its output becomes a workflow cache. A
    step with no output at all is not a single-run step, so its missing
    ``output`` or ``input`` is still reported by pattern validation.

    A workflow-call step has no cache output of its own, so it runs once
    per workflow unless its ``with`` values reference a matrix variable
    of the calling workflow; such a call resolves to different parameters
    per combination and must run once per combination.

    Args:
        step: Step configuration dictionary.
        matrix: The workflow's matrix definition (empty when absent).

    Returns:
        True when the step runs once rather than per matrix combination.
    """
    if is_workflow_call_step(step):
        return not _call_parameters_vary(step, matrix)
    if matrix:
        return False
    return _has_file_output(step)


def _cache_input_paths(input_param: Any) -> List[Any]:
    """Return the cache (.db) paths named by a step input parameter."""
    if not input_param:
        return []
    inputs = (
        [input_param] if isinstance(input_param, str) else list(input_param)
    )
    return [p for p in inputs if str(p).lower().endswith(".db")]


def _has_db_input(input_param: Any) -> bool:
    """Return True when an input parameter names any cache (.db) file."""
    if not input_param:
        return False
    if isinstance(input_param, str):
        inputs = [input_param]
    elif isinstance(input_param, list):
        inputs = list(input_param)
    else:
        inputs = []
    return any(str(p).lower().endswith(".db") for p in inputs)


def _parse_range(value: str) -> Optional[List[Any]]:
    """Return the integers spanned by a 'start-end' range, or None."""
    parts = value.split("-")
    if len(parts) != 2:
        return None
    try:
        start = int(parts[0].strip())
        end = int(parts[1].strip())
    except ValueError:
        return None
    if start > end:
        return None
    return list(range(start, end + 1))


class MatrixMixin(WorkflowExecutorBase):
    """Matrix expansion and derivation for WorkflowExecutor."""

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
        expanded = _parse_range(value)
        if expanded is None:
            return [value]
        return expanded

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
        # If explicit matrix exists, use it
        explicit_matrix: Dict[str, List[Any]] = workflow.get("matrix", {})
        if explicit_matrix:
            return explicit_matrix

        # Check for AGGREGATE steps that need derived matrix
        for step in workflow.get("steps", []):
            derived_matrix = self._aggregate_step_matrix(step)
            if derived_matrix:
                return derived_matrix

        return {}

    def _aggregate_step_matrix(
        self, step: Dict[str, Any]
    ) -> Dict[str, List[Any]]:
        """Derive a matrix from an AGGREGATE step's input caches.

        Returns an empty dictionary when the step is not an AGGREGATE
        pattern step or has no cache input.
        """
        from causaliq_core import ActionPattern

        if not _has_cache_output(step):
            return {}
        if self._get_step_action_pattern(step) != ActionPattern.AGGREGATE:
            return {}

        step_inputs = step.get("with", {})
        cache_paths = _cache_input_paths(step_inputs.get("input"))
        if not cache_paths:
            return {}

        _, derived_matrix = _derive_matrix_from_caches(cache_paths)
        return derived_matrix
