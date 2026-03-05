"""Unit tests for WorkflowExecutor - no filesystem access."""

import pytest

from causaliq_workflow.schema import WorkflowValidationError
from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor


# Test WorkflowExecutionError exception creation
def test_workflow_execution_error():
    """Test creating WorkflowExecutionError with message."""
    error = WorkflowExecutionError("Test error")
    assert str(error) == "Test error"


def test_parse_workflow_success(monkeypatch):
    """Test successful workflow parsing with valid YAML."""
    # Setup mocks
    workflow_data = {"name": "Test", "steps": [{"run": "echo hello"}]}

    def fake_load_workflow_file(path):
        assert path == "/path/to/workflow.yml"
        return workflow_data

    def fake_validate_workflow(data):
        assert data == workflow_data
        return True

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate_workflow
    )
    executor = WorkflowExecutor()
    result = executor.parse_workflow("/path/to/workflow.yml")
    assert result == workflow_data


def test_parse_workflow_validation_error(monkeypatch):
    """Test workflow parsing fails with validation error."""
    # Setup mocks
    workflow_data = {"name": "Test"}  # Missing steps

    def fake_load_workflow_file(path):
        assert path == "/path/to/workflow.yml"
        return workflow_data

    def fake_validate_workflow(data):
        assert data == workflow_data
        raise WorkflowValidationError("Missing steps field")

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate_workflow
    )
    executor = WorkflowExecutor()
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("/path/to/workflow.yml")
    assert "Workflow parsing failed" in str(exc_info.value)


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


# Test template variable extraction
def test_extract_template_variables():
    """Test extraction of template variables from strings."""
    executor = WorkflowExecutor()

    # Test valid template variables
    text1 = "/results/{{id}}/{{dataset}}_{{algorithm}}.xml"
    variables1 = executor._extract_template_variables(text1)
    assert variables1 == {"id", "dataset", "algorithm"}

    # Test no template variables
    text2 = "/results/static/output.xml"
    variables2 = executor._extract_template_variables(text2)
    assert variables2 == set()

    # Test single variable
    text3 = "chart_{{dataset}}.png"
    variables3 = executor._extract_template_variables(text3)
    assert variables3 == {"dataset"}

    # Test non-string input
    variables4 = executor._extract_template_variables(123)
    assert variables4 == set()


def test_parse_workflow_valid_templates(monkeypatch):
    """Test workflow parsing with valid template variables."""
    workflow_data = {
        "id": "test-workflow",
        "description": "Test workflow",
        "matrix": {"dataset": ["asia"], "algorithm": ["pc"]},
        "steps": [
            {
                "uses": "test_action",
                "with": {
                    "result": "/results/{{id}}/{{dataset}}_{{algorithm}}.xml"
                },
            }
        ],
    }

    def fake_load_workflow_file(path):
        assert path == "test.yml"
        return workflow_data

    def fake_validate_workflow(data):
        assert data == workflow_data
        return True

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate_workflow
    )
    executor = WorkflowExecutor()
    executor.action_registry.validate_workflow_actions = lambda workflow: []
    result = executor.parse_workflow("test.yml")
    assert result == workflow_data


def test_parse_workflow_invalid_templates(monkeypatch):
    """Test workflow parsing fails with invalid template variables."""
    workflow_data = {
        "id": "test-workflow",
        "description": "Test workflow",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "uses": "action",
                "with": {"result": "/results/{{unknown_var}}/{{dataset}}.xml"},
            }
        ],
    }

    def fake_load_workflow_file(path):
        assert path == "test.yml"
        return workflow_data

    def fake_validate_workflow(data):
        assert data == workflow_data
        return True

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate_workflow
    )
    executor = WorkflowExecutor()
    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    error_msg = str(exc_info.value)
    assert "Unknown template variables: ['unknown_var']" in error_msg
    assert "Available variables: ['dataset', 'description', 'id']" in error_msg


def test_parse_workflow_no_matrix_valid_templates(monkeypatch):
    """Test workflow parsing with only workflow-level variables."""
    workflow_data = {
        "id": "simple-workflow",
        "description": "Simple test",
        "steps": [
            {
                "uses": "test_action",
                "with": {"output": "/results/{{id}}_{{description}}.txt"},
            }
        ],
    }

    def fake_load_workflow_file(path):
        assert path == "test.yml"
        return workflow_data

    def fake_validate_workflow(data):
        assert data == workflow_data
        return True

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file",
        fake_load_workflow_file,
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate_workflow
    )
    executor = WorkflowExecutor()
    executor.action_registry.validate_workflow_actions = lambda workflow: []
    result = executor.parse_workflow("test.yml")
    assert result == workflow_data


# Test malformed template variables
def test_extract_malformed_templates():
    """Test extraction ignores malformed template patterns."""
    executor = WorkflowExecutor()

    # Test malformed patterns (should be ignored)
    text = "/results/{dataset}/{{}/{{incomplete}/output.xml"
    variables = executor._extract_template_variables(text)
    assert variables == set()

    # Test mixed valid and invalid
    text2 = "/results/{{valid}}/{invalid}/{{also_valid}}.xml"
    variables2 = executor._extract_template_variables(text2)
    assert variables2 == {"valid", "also_valid"}


# Test _has_cache_input helper detects .db files.
def test_has_cache_input_detects_db_files():
    """Test _has_cache_input detects .db file inputs."""
    executor = WorkflowExecutor()

    # String input with .db extension
    assert executor._has_cache_input({"input": "cache.db"}) is True
    assert executor._has_cache_input({"input": "/path/to/result.db"}) is True
    assert executor._has_cache_input({"input": "FILE.DB"}) is True

    # String input without .db extension
    assert executor._has_cache_input({"input": "data.csv"}) is False
    assert executor._has_cache_input({"input": "/path/to/file.xml"}) is False

    # No input parameter
    assert executor._has_cache_input({}) is False
    assert executor._has_cache_input({"other": "value"}) is False


# Test _has_cache_input with list inputs.
def test_has_cache_input_list_inputs():
    """Test _has_cache_input with list of input files."""
    executor = WorkflowExecutor()

    # List with at least one .db file
    assert (
        executor._has_cache_input({"input": ["file.csv", "cache.db"]}) is True
    )
    assert (
        executor._has_cache_input({"input": ["result.db", "other.db"]}) is True
    )

    # List without .db files
    assert (
        executor._has_cache_input({"input": ["file.csv", "data.xml"]}) is False
    )

    # Empty list
    assert executor._has_cache_input({"input": []}) is False


# Test CREATE pattern requires output parameter.
def test_validate_create_pattern_requires_output(monkeypatch):
    """Test CREATE pattern validation requires output parameter."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "id": "test",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "create_step",
                "uses": "test_provider",
                "with": {"action": "create_action"},
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.CREATE

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    assert "CREATE pattern requires 'output'" in str(exc_info.value)


# Test CREATE pattern requires matrix definition.
def test_validate_create_pattern_requires_matrix(monkeypatch):
    """Test CREATE pattern validation requires matrix definition."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "id": "test",
        "steps": [
            {
                "name": "create_step",
                "uses": "test_provider",
                "with": {"action": "create_action", "output": "result.db"},
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.CREATE

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    assert "CREATE pattern requires workflow 'matrix'" in str(exc_info.value)


# Test CREATE pattern prohibits cache input.
def test_validate_create_pattern_prohibits_cache_input(monkeypatch):
    """Test CREATE pattern validation prohibits .db input files."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "id": "test",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "create_step",
                "uses": "test_provider",
                "with": {
                    "action": "create_action",
                    "output": "result.db",
                    "input": "other_cache.db",
                },
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.CREATE

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    assert "CREATE pattern prohibits cache input" in str(exc_info.value)


# Test UPDATE pattern requires input parameter.
def test_validate_update_pattern_requires_input(monkeypatch):
    """Test UPDATE pattern validation requires input parameter."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "id": "test",
        "steps": [
            {
                "name": "update_step",
                "uses": "test_provider",
                "with": {"action": "update_action"},
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.UPDATE

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    assert "UPDATE pattern requires 'input'" in str(exc_info.value)


# Test UPDATE pattern prohibits output parameter.
def test_validate_update_pattern_prohibits_output(monkeypatch):
    """Test UPDATE pattern validation prohibits output parameter."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "id": "test",
        "steps": [
            {
                "name": "update_step",
                "uses": "test_provider",
                "with": {
                    "action": "update_action",
                    "input": "cache.db",
                    "output": "new_cache.db",
                },
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.UPDATE

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    assert "UPDATE pattern prohibits 'output'" in str(exc_info.value)


# Test UPDATE pattern prohibits matrix definition.
def test_validate_update_pattern_prohibits_matrix(monkeypatch):
    """Test UPDATE pattern validation prohibits matrix definition."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "id": "test",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "update_step",
                "uses": "test_provider",
                "with": {"action": "update_action", "input": "cache.db"},
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.UPDATE

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    assert "UPDATE pattern prohibits workflow 'matrix'" in str(exc_info.value)


# Test AGGREGATE pattern requires input parameter.
def test_validate_aggregate_pattern_requires_input(monkeypatch):
    """Test AGGREGATE pattern validation requires input parameter."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "id": "test",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "agg_step",
                "uses": "test_provider",
                "with": {"action": "aggregate_action", "output": "result.db"},
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.AGGREGATE

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    assert "AGGREGATE pattern requires 'input'" in str(exc_info.value)


# Test AGGREGATE pattern requires output parameter.
def test_validate_aggregate_pattern_requires_output(monkeypatch):
    """Test AGGREGATE pattern validation requires output parameter."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "id": "test",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "agg_step",
                "uses": "test_provider",
                "with": {"action": "aggregate_action", "input": "cache.db"},
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.AGGREGATE

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    assert "AGGREGATE pattern requires 'output'" in str(exc_info.value)


# Test AGGREGATE pattern requires matrix definition.
def test_validate_aggregate_pattern_requires_matrix(monkeypatch):
    """Test AGGREGATE pattern validation requires matrix definition."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "id": "test",
        "steps": [
            {
                "name": "agg_step",
                "uses": "test_provider",
                "with": {
                    "action": "aggregate_action",
                    "input": "cache.db",
                    "output": "result.db",
                },
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.AGGREGATE

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    with pytest.raises(WorkflowExecutionError) as exc_info:
        executor.parse_workflow("test.yml")
    assert "AGGREGATE pattern requires workflow 'matrix'" in str(
        exc_info.value
    )


# Test valid CREATE pattern configuration passes.
def test_validate_create_pattern_valid(monkeypatch):
    """Test valid CREATE pattern configuration passes validation."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "id": "test",
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "create_step",
                "uses": "test_provider",
                "with": {
                    "action": "create_action",
                    "output": "result.db",
                    "data": "/path/to/data.csv",
                },
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.CREATE

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    result = executor.parse_workflow("test.yml")
    assert result == workflow_data


# Test no pattern declared skips validation.
def test_validate_no_pattern_skips_validation(monkeypatch):
    """Test actions without declared patterns skip validation."""
    workflow_data = {
        "id": "test",
        "steps": [
            {
                "name": "unknown_step",
                "uses": "test_provider",
                "with": {"action": "unknown_action"},
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return None  # No pattern declared

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    result = executor.parse_workflow("test.yml")
    assert result == workflow_data
