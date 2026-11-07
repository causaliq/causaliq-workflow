"""Cache-entry scanning configuration for grouping and mapping steps."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from causaliq_workflow.cache.reporting import build_entry_view
from causaliq_workflow.workflow._base import WorkflowExecutorBase
from causaliq_workflow.workflow.matrix import (
    _derive_matrix_from_caches,
    _matrix_values_match,
)


@dataclass
class AggregationConfig:
    """Configuration for matching a step's job against input cache entries.

    A step is given entries when it has an `input` parameter naming
    workflow cache(s) and either declares a cache-reading pattern (MAP or
    AGGREGATE) or the workflow defines a matrix. The matrix variables
    select the entries for the current job.
    """

    input_caches: List[str] = field(default_factory=list)
    """List of input workflow cache paths."""

    filter_expr: Optional[str] = None
    """Optional filter expression to restrict input entries."""

    matrix_vars: List[str] = field(default_factory=list)
    """Matrix variables defining grouping dimensions."""


@dataclass
class _AggregationScan:
    """Mutable accumulator for an aggregation input scan."""

    matching_entries: List[Dict[str, Any]] = field(default_factory=list)
    scanned: int = 0
    filtered: int = 0
    matched: int = 0


class _PopulationEntry(Mapping[str, Any]):
    """One entry of a ``random()`` selection population.

    A name that the entry holds as a matrix value is answered without
    decompressing the entry's metadata, which is what a population
    lookup usually asks for. Any other name falls back to the full
    reporting view; that needs the cache handle, so the views for the
    whole index are built in a single pass.
    """

    def __init__(
        self,
        cache_path: str,
        record: Dict[str, Any],
        index: List[Dict[str, Any]],
    ) -> None:
        """Store the entry's cache path, record and sibling index."""
        self._cache_path = cache_path
        self._record = record
        self._index = index

    def __getitem__(self, key: str) -> Any:
        """Return a matrix value, or fall back to the reporting view."""
        matrix_values = self._record["matrix_values"]
        if key in matrix_values:
            return matrix_values[key]
        return self._view()[key]

    def __contains__(self, key: object) -> bool:
        """Report whether a name is available without a full read."""
        if key in self._record["matrix_values"]:
            return True
        return key in self._view()

    def __iter__(self) -> Iterator[str]:
        """Iterate over the names of the full reporting view."""
        return iter(self._view())

    def __len__(self) -> int:
        """Return the number of names in the full reporting view."""
        return len(self._view())

    def _view(self) -> Dict[str, Any]:
        """Return the entry's reporting view, building it on demand."""
        if self._record["flat_meta"] is None:
            _fill_views(self._cache_path, self._index)
        view: Dict[str, Any] = self._record["flat_meta"]
        return view


class AggregationMixin(WorkflowExecutorBase):
    """Cache-entry scan methods for WorkflowExecutor."""

    def _get_aggregation_config(
        self,
        step: Dict[str, Any],
        matrix: Dict[str, List[Any]],
    ) -> Optional[AggregationConfig]:
        """Get the entry-scan configuration for a step.

        Returns None if the step reads no workflow cache. If no explicit
        matrix is provided but the action maps or groups cache entries,
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
        scan = _AggregationScan()
        resolved_filter, extra_names = self._resolve_scan_filter(config)

        for cache_path in config.input_caches:
            self._scan_one_cache(
                scan,
                config,
                matrix_values,
                cache_path,
                resolved_filter,
                extra_names,
                logger,
            )

        _log_scan_summary(config, scan, logger)
        return scan.matching_entries

    def _resolve_scan_filter(
        self, config: AggregationConfig
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Pre-resolve ``random()`` calls across all input caches."""
        if not config.filter_expr or "random(" not in config.filter_expr:
            return config.filter_expr, {}

        from causaliq_core.utils import resolve_random_calls

        all_meta = self._collect_scan_metadata(config.input_caches)
        return resolve_random_calls(config.filter_expr, all_meta)

    def _collect_scan_metadata(
        self, cache_paths: List[str]
    ) -> List[_PopulationEntry]:
        """Collect population entries from every entry in the caches."""
        all_meta: List[_PopulationEntry] = []
        for cache_path in cache_paths:
            all_meta.extend(self._safe_scan_metadata(cache_path))
        return all_meta

    def _safe_scan_metadata(self, cache_path: str) -> List[_PopulationEntry]:
        """Return lazy population entries for one cache, ignoring errors."""
        try:
            index = self._scan_index_for(cache_path)
        except Exception:
            return []
        return [_PopulationEntry(cache_path, entry, index) for entry in index]

    def _scan_index_for(self, cache_path: str) -> List[Dict[str, Any]]:
        """Return the memoised entry index for one input cache.

        The index (matrix values plus flattened metadata per entry) is
        built once per cache and reused across every matrix job, so a
        large cache is not re-read for each combination.
        """
        from pathlib import Path

        key = str(cache_path)
        if key in self._scan_index:
            return self._scan_index[key]

        index: List[Dict[str, Any]] = []
        if Path(cache_path).exists():
            index = self._build_scan_index(cache_path)
        self._scan_index[key] = index
        return index

    def _build_scan_index(self, cache_path: str) -> List[Dict[str, Any]]:
        """Read entry records and index them for matching.

        Records hold the entry's matrix values and its compressed
        metadata, so a large cache is read without decompressing
        metadata for entries the run never looks at.
        """
        from causaliq_workflow.cache import WorkflowCache

        index: List[Dict[str, Any]] = []
        with WorkflowCache(cache_path) as cache:
            for record in cache.list_entry_records():
                record["flat_meta"] = None
                index.append(record)
        return index

    def _scan_one_cache(
        self,
        scan: _AggregationScan,
        config: AggregationConfig,
        matrix_values: Dict[str, Any],
        cache_path: str,
        resolved_filter: Optional[str],
        extra_names: Dict[str, Any],
        logger: Optional[Callable[[str], None]],
    ) -> None:
        """Scan one cache, skipping missing or unreadable caches."""
        from pathlib import Path

        if not Path(cache_path).exists():
            _warn(logger, f"Warning: Cache does not exist: {cache_path}")
            return

        try:
            self._scan_open_cache(
                scan,
                config,
                matrix_values,
                cache_path,
                resolved_filter,
                extra_names,
            )
        except Exception as e:
            _warn(logger, f"Warning: Failed to read cache {cache_path}: {e}")

    def _scan_open_cache(
        self,
        scan: _AggregationScan,
        config: AggregationConfig,
        matrix_values: Dict[str, Any],
        cache_path: str,
        resolved_filter: Optional[str],
        extra_names: Dict[str, Any],
    ) -> None:
        """Scan a cache's memoised index, loading only matched entries."""
        from causaliq_workflow.cache import WorkflowCache

        index = self._scan_index_for(cache_path)
        scan.scanned += len(index)
        candidates = _matrix_candidates(index, config, matrix_values)
        if not candidates:
            return

        with WorkflowCache(cache_path) as cache:
            _view_records(cache, candidates)
            for entry in _filtered_candidates(
                candidates, resolved_filter, extra_names, scan
            ):
                _append_matched_entry(scan, cache, cache_path, entry)


def _matrix_candidates(
    index: List[Dict[str, Any]],
    config: AggregationConfig,
    matrix_values: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Return indexed entries whose matrix values match this job.

    The matrix comparison runs before the filter expression because both
    predicates only narrow the candidate set: the same entries survive
    either way, but the filter is then evaluated for this job's entries
    rather than for the whole cache.
    """
    return [
        entry
        for entry in index
        if _matrix_values_match(
            entry["matrix_values"], matrix_values, config.matrix_vars
        )
    ]


def _view_records(cache: Any, records: List[Dict[str, Any]]) -> None:
    """Build missing reporting views for records using an open cache."""
    for record in records:
        if record["flat_meta"] is not None:
            continue
        metadata = cache.decompress_metadata(record["metadata_blob"])
        record["flat_meta"] = build_entry_view(
            record["matrix_values"], metadata
        )


def _fill_views(cache_path: str, records: List[Dict[str, Any]]) -> None:
    """Build missing reporting views for records of one cache.

    The views are built in a single pass with the cache open once, so a
    large cache is not reopened per entry when a population lookup needs
    metadata names.
    """
    if all(record["flat_meta"] is not None for record in records):
        return

    from causaliq_workflow.cache import WorkflowCache

    with WorkflowCache(cache_path) as cache:
        _view_records(cache, records)


def _filtered_candidates(
    candidates: List[Dict[str, Any]],
    resolved_filter: Optional[str],
    extra_names: Dict[str, Any],
    scan: _AggregationScan,
) -> List[Dict[str, Any]]:
    """Return the candidates that satisfy the filter expression."""
    if not resolved_filter:
        return candidates

    kept: List[Dict[str, Any]] = []
    for entry in candidates:
        if _aggregation_filter_skip(
            resolved_filter, extra_names, entry["flat_meta"]
        ):
            scan.filtered += 1
            continue
        kept.append(entry)
    return kept


def _append_matched_entry(
    scan: _AggregationScan,
    cache: Any,
    cache_path: str,
    entry: Dict[str, Any],
) -> None:
    """Load one matched entry in full and append it to the scan."""
    full_entry = cache.get(entry["matrix_values"])
    if full_entry is None:
        return
    scan.matched += 1
    scan.matching_entries.append(
        _aggregated_entry(
            entry["matrix_values"],
            full_entry,
            cache_path,
            {"hash": entry.get("hash")},
        )
    )


def _warn(logger: Optional[Callable[[str], None]], message: str) -> None:
    """Emit a scan warning when a logger is provided."""
    if logger:
        logger(message)


def _aggregation_filter_skip(
    resolved_filter: str,
    extra_names: Dict[str, Any],
    flat_meta: Dict[str, Any],
) -> bool:
    """Return True when the entry is filtered out of the aggregation.

    The caller only invokes this with a resolved filter expression.
    """
    from causaliq_workflow.cache.reporting import evaluate_entry_filter

    try:
        return not evaluate_entry_filter(
            resolved_filter, {**flat_meta, **extra_names}
        )
    except Exception:
        return True


def _aggregated_entry(
    entry_matrix: Dict[str, Any],
    full_entry: Any,
    cache_path: str,
    entry_info: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the aggregation entry dictionary for one matched entry."""
    objects_content = {
        name: obj.content for name, obj in full_entry.objects.items()
    }
    return {
        "matrix_values": entry_matrix,
        "metadata": full_entry.metadata,
        "cache_path": str(cache_path),
        "entry_hash": entry_info.get("hash"),
        "entry": full_entry,
        "objects": objects_content,
    }


def _log_scan_summary(
    config: AggregationConfig,
    scan: _AggregationScan,
    logger: Optional[Callable[[str], None]],
) -> None:
    """Log the aggregation scan statistics when a logger is provided."""
    if not logger:
        return
    filter_info = ""
    if config.filter_expr:
        filter_info = f", filtered={scan.filtered}"
    logger(
        f"Aggregation scan: scanned={scan.scanned}"
        f"{filter_info}, matched={scan.matched}"
    )
