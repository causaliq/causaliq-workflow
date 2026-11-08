"""Unit tests for workflow matrix expansion."""

import pytest

from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor


# Test matrix expansion with simple variables
def test_expand_matrix_simple():
    """Test matrix expansion with simple variable combinations."""
    matrix = {
        "algorithm": ["pc", "ges"],
        "dataset": ["asia", "cancer"],
    }

    executor = WorkflowExecutor()
    jobs = executor.expand_matrix(matrix)

    # Should generate 4 combinations (2 × 2)
    expected_jobs = [
        {"algorithm": "pc", "dataset": "asia"},
        {"algorithm": "pc", "dataset": "cancer"},
        {"algorithm": "ges", "dataset": "asia"},
        {"algorithm": "ges", "dataset": "cancer"},
    ]

    assert len(jobs) == 4
    assert jobs == expected_jobs


# Test matrix expansion with empty matrix
def test_expand_matrix_empty():
    """Test matrix expansion returns empty job for empty matrix."""
    executor = WorkflowExecutor()
    jobs = executor.expand_matrix({})

    assert jobs == [{}]


# Test matrix expansion with single variable
def test_expand_matrix_single_variable():
    """Test matrix expansion with single variable."""
    matrix = {"algorithm": ["pc", "ges", "lingam"]}

    executor = WorkflowExecutor()
    jobs = executor.expand_matrix(matrix)

    expected_jobs = [
        {"algorithm": "pc"},
        {"algorithm": "ges"},
        {"algorithm": "lingam"},
    ]

    assert len(jobs) == 3
    assert jobs == expected_jobs


def test_expand_matrix_exception_handling(monkeypatch):
    """Test matrix expansion fails gracefully with unexpected errors."""

    # Setup mock to raise exception
    def fake_product(*args, **kwargs):
        raise RuntimeError("Unexpected error in itertools")

    monkeypatch.setattr("itertools.product", fake_product)
    matrix = {"algorithm": ["pc", "ges"]}
    executor = WorkflowExecutor()
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.expand_matrix(matrix)
    assert "Matrix expansion failed" in str(exc_info.value)
    assert "Unexpected error in itertools" in str(exc_info.value)


# Test matrix expansion with realistic workflow data
def test_expand_matrix_with_realistic_data():
    """Test matrix expansion with realistic multi-dimensional matrix."""
    # Setup realistic matrix data
    matrix = {
        "dataset": ["asia", "cancer", "alarm"],
        "algorithm": ["pc", "ges"],
        "alpha": [0.01, 0.05],
    }

    executor = WorkflowExecutor()
    jobs = executor.expand_matrix(matrix)

    # Should generate 12 combinations (3 × 2 × 2)
    assert len(jobs) == 12

    # Verify all combinations are present
    datasets = {job["dataset"] for job in jobs}
    algorithms = {job["algorithm"] for job in jobs}
    alphas = {job["alpha"] for job in jobs}

    assert datasets == {"asia", "cancer", "alarm"}
    assert algorithms == {"pc", "ges"}
    assert alphas == {0.01, 0.05}

    # Verify specific combination exists
    expected_job = {"dataset": "asia", "algorithm": "pc", "alpha": 0.01}
    assert expected_job in jobs


# Test matrix expansion maintains consistent ordering
def test_matrix_expansion_preserves_order():
    """Test matrix expansion produces deterministic job ordering."""
    matrix = {
        "algorithm": ["pc", "ges"],
        "dataset": ["asia", "cancer"],
    }

    executor = WorkflowExecutor()
    jobs1 = executor.expand_matrix(matrix)
    jobs2 = executor.expand_matrix(matrix)

    # Multiple expansions should produce identical results
    assert jobs1 == jobs2

    # First job should be first combination of first variable
    assert jobs1[0] == {"algorithm": "pc", "dataset": "asia"}


# Test matrix expansion expands range strings.
def test_expand_matrix_range_string():
    """Test matrix expansion expands range strings like '0-2' to integers."""
    executor = WorkflowExecutor()

    # Range string in matrix value
    matrix = {
        "seed": ["0-2"],
        "network": ["asia"],
    }
    jobs = executor.expand_matrix(matrix)

    # Should expand "0-2" to 0, 1, 2 → 3 jobs
    assert len(jobs) == 3
    assert jobs[0] == {"seed": 0, "network": "asia"}
    assert jobs[1] == {"seed": 1, "network": "asia"}
    assert jobs[2] == {"seed": 2, "network": "asia"}


# Test matrix expansion with larger range.
def test_expand_matrix_large_range():
    """Test matrix expansion with larger range like '0-24'."""
    executor = WorkflowExecutor()

    matrix = {"seed": ["0-24"]}
    jobs = executor.expand_matrix(matrix)

    assert len(jobs) == 25
    assert jobs[0] == {"seed": 0}
    assert jobs[24] == {"seed": 24}


# Test matrix expansion with mixed values and ranges.
def test_expand_matrix_mixed_values_and_ranges():
    """Test matrix with both explicit values and range strings."""
    executor = WorkflowExecutor()

    matrix = {
        "seed": [0, "5-7", 10],  # Mix of int, range, int
        "network": ["asia", "cancer"],
    }
    jobs = executor.expand_matrix(matrix)

    # seed: [0, 5, 6, 7, 10] = 5 values × 2 networks = 10 jobs
    assert len(jobs) == 10

    # Check range was expanded
    seeds = {job["seed"] for job in jobs}
    assert seeds == {0, 5, 6, 7, 10}


# Test matrix expansion leaves non-range strings unchanged.
def test_expand_matrix_non_range_strings():
    """Test that non-range strings are not modified."""
    executor = WorkflowExecutor()

    matrix = {
        "network": ["asia-v2", "cancer"],  # "asia-v2" is not a range
    }
    jobs = executor.expand_matrix(matrix)

    assert len(jobs) == 2
    assert jobs[0] == {"network": "asia-v2"}
    assert jobs[1] == {"network": "cancer"}
