"""Unit tests for action pattern validation of workflow steps."""

import pytest

from causaliq_workflow.workflow import WorkflowExecutionError, WorkflowExecutor


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


# Test PRODUCE pattern requires output parameter.
def test_validate_produce_pattern_requires_output(monkeypatch):
    """Test PRODUCE pattern validation requires output parameter."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "create_step",
                "uses": "test_provider",
                "with": {
                    "action": "create_action",
                    "data": "{{dataset}}",  # Use matrix var to pass validation
                },
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.PRODUCE

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
    assert "creates cache entries, so an 'output' cache path" in str(
        exc_info.value
    )


# Test PRODUCE pattern requires matrix definition.
def test_validate_produce_pattern_requires_matrix(monkeypatch):
    """Test PRODUCE pattern validation requires matrix definition."""
    from causaliq_core import ActionPattern

    workflow_data = {
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
        return ActionPattern.PRODUCE

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
    assert "creates one cache entry per matrix combination" in str(
        exc_info.value
    )


# Test PRODUCE pattern prohibits cache input.
def test_validate_produce_pattern_prohibits_cache_input(monkeypatch):
    """Test PRODUCE pattern validation prohibits .db input files."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "create_step",
                "uses": "test_provider",
                "with": {
                    "action": "create_action",
                    "output": "{{dataset}}/result.db",  # Use matrix var
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
        return ActionPattern.PRODUCE

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
    assert "'input' cannot name a cache (.db) file" in str(exc_info.value)


# Test AGGREGATE pattern requires input parameter.
def test_validate_aggregate_pattern_requires_input(monkeypatch):
    """Test AGGREGATE pattern validation requires input parameter."""
    from causaliq_core import ActionPattern

    workflow_data = {
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
    assert "groups cache entries, so an 'input' cache path" in str(
        exc_info.value
    )


# Test AGGREGATE pattern requires output parameter.
def test_validate_aggregate_pattern_requires_output(monkeypatch):
    """Test AGGREGATE pattern validation requires output parameter."""
    from causaliq_core import ActionPattern

    workflow_data = {
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
    assert "groups cache entries into output entries" in str(exc_info.value)


# Test AGGREGATE pattern requires a matrix naming the grouping dimensions.
def test_validate_aggregate_pattern_requires_matrix(monkeypatch):
    """Test AGGREGATE pattern requires a grouping matrix."""
    from causaliq_core import ActionPattern

    # AGGREGATE without matrix and without cache input (non-.db file)
    workflow_data = {
        "steps": [
            {
                "name": "agg_step",
                "uses": "test_provider",
                "with": {
                    "action": "aggregate_action",
                    "input": "data.csv",  # Not a cache file
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
    assert "must name the grouping dimensions" in str(exc_info.value)


# Test MAP with cache input passes without an explicit matrix.
def test_validate_map_pattern_without_matrix_valid(monkeypatch):
    """Test MAP passes without an explicit matrix (inherited from cache)."""
    from causaliq_core import ActionPattern

    # MAP with cache input but no explicit matrix - matrix inherited
    workflow_data = {
        "steps": [
            {
                "name": "map_step",
                "uses": "test_provider",
                "with": {
                    "action": "map_action",
                    "input": "cache.db",  # Cache input supplies the matrix
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
        return ActionPattern.MAP

    monkeypatch.setattr(
        "causaliq_workflow.workflow.load_workflow_file", fake_load
    )
    monkeypatch.setattr(
        "causaliq_workflow.workflow.validate_workflow", fake_validate
    )

    executor = WorkflowExecutor()
    executor.action_registry.get_action_pattern = fake_get_pattern
    executor.action_registry.validate_workflow_actions = lambda w: []

    # Should pass validation (matrix inherited from cache)
    result = executor.parse_workflow("test.yml")
    assert result == workflow_data


# Test MAP pattern requires an input parameter.
def test_validate_map_pattern_requires_input(monkeypatch):
    """Test MAP pattern validation requires an input cache path."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "steps": [
            {
                "name": "map_step",
                "uses": "test_provider",
                "with": {"action": "map_action", "output": "result.db"},
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.MAP

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
    assert "maps one cache entry to one output entry" in str(exc_info.value)


# Test MAP pattern requires an output parameter.
def test_validate_map_pattern_requires_output(monkeypatch):
    """Test MAP pattern validation requires an output cache path."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "steps": [
            {
                "name": "map_step",
                "uses": "test_provider",
                "with": {"action": "map_action", "input": "cache.db"},
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.MAP

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
    assert "'output' cache path is required" in str(exc_info.value)


# Test valid PRODUCE pattern configuration passes.
def test_validate_produce_pattern_valid(monkeypatch):
    """Test valid PRODUCE pattern configuration passes validation."""
    from causaliq_core import ActionPattern

    workflow_data = {
        "matrix": {"dataset": ["asia"]},
        "steps": [
            {
                "name": "create_step",
                "uses": "test_provider",
                "with": {
                    "action": "create_action",
                    "output": "{{dataset}}_result.db",
                    "data": "/path/to/{{dataset}}.csv",
                },
            }
        ],
    }

    def fake_load(path):
        return workflow_data

    def fake_validate(data):
        return True

    def fake_get_pattern(provider, action):
        return ActionPattern.PRODUCE

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
