"""Unit tests for the shared reporting view and filter resolver."""

import pytest
from causaliq_core.metadata import build_metadata

from causaliq_workflow.cache.reporting import (
    build_entry_view,
    evaluate_entry_filter,
    flatten_block,
    resolve_qualified_names,
)


def _metadata() -> dict:
    """Return a version 2 envelope with inputs, results and history."""
    return build_metadata(
        "causaliq-analysis",
        "evaluate_graph",
        {"reference": "asia.xdsl"},
        {
            "status": "ok",
            "f1": 0.9,
            "hyperparameters": {"iss": 1.0},
        },
        history={
            "causaliq-discovery.learn_graph": {
                "parameters": {"algorithm": "hc"},
                "result": {
                    "status": "ok",
                    "elapsed_seconds": 3200.1,
                },
            }
        },
    )


# Test flatten_block yields intermediate and leaf paths.
def test_flatten_block_yields_nested_paths() -> None:
    paths = dict(flatten_block({"a": 1, "b": {"c": 2}}))
    assert paths["a"] == 1
    assert paths["b"] == {"c": 2}
    assert paths["b.c"] == 2


# Test matrix and object values use bare names.
def test_build_entry_view_uses_bare_names_for_matrix_and_object():
    view = build_entry_view(
        {"sample_size": 1000},
        _metadata(),
        {"f1": 0.91, "shd": 4},
    )
    assert view["sample_size"] == 1000
    assert view["f1"] == 0.91
    assert view["shd"] == 4


# Test metadata uses action-qualified names.
def test_build_entry_view_qualifies_metadata_names():
    view = build_entry_view({}, _metadata())
    assert view["evaluate_graph.status"] == "ok"
    assert view["evaluate_graph.hyperparameters.iss"] == 1.0
    assert view["learn_graph.status"] == "ok"
    assert view["learn_graph.elapsed_seconds"] == 3200.1


# Test explicit parameter and result names are available.
def test_build_entry_view_exposes_explicit_blocks():
    view = build_entry_view({}, _metadata())
    assert view["evaluate_graph.result.status"] == "ok"
    assert view["evaluate_graph.parameters.reference"] == "asia.xdsl"
    assert view["learn_graph.result.status"] == "ok"


# Test provider-qualified names normalise hyphens to underscores.
def test_build_entry_view_normalises_provider_names():
    view = build_entry_view({}, _metadata())
    assert view["causaliq_analysis.evaluate_graph.status"] == "ok"
    assert view["causaliq_discovery.learn_graph.status"] == "ok"


# Test a name present in parameters and result has no short form.
def test_build_entry_view_omits_ambiguous_short_name():
    metadata = build_metadata(
        "provider",
        "action",
        {"value": 1},
        {"value": 2},
    )
    view = build_entry_view({}, metadata)
    assert "action.value" not in view
    assert view["action.parameters.value"] == 1
    assert view["action.result.value"] == 2


# Test flat metadata is exposed as bare names.
def test_build_entry_view_exposes_flat_metadata_bare():
    view = build_entry_view({"network": "asia"}, {"seed": 3})
    assert view["seed"] == 3


# Test legacy provider metadata is normalised before viewing.
def test_build_entry_view_normalises_legacy_metadata():
    view = build_entry_view(
        {},
        {"provider": {"action": {"status": "ok"}}},
    )
    assert view["action.status"] == "ok"


# Test object values override bare matrix and metadata names.
def test_build_entry_view_object_values_override_bare_names():
    view = build_entry_view({"f1": 0.1}, _metadata(), {"f1": 0.9})
    assert view["f1"] == 0.9


# Test qualified names are rewritten before evaluation.
def test_resolve_qualified_names_rewrites_known_names():
    view = build_entry_view({}, _metadata())
    expression, aliases = resolve_qualified_names(
        "learn_graph.status == 'ok'",
        view,
    )
    assert expression.startswith("q0 ==")
    assert aliases["q0"] == "ok"


# Test string literals are not rewritten.
def test_resolve_qualified_names_leaves_strings_untouched():
    view = build_entry_view({}, _metadata())
    expression, aliases = resolve_qualified_names(
        "evaluate_graph.status == 'learn_graph.status'",
        view,
    )
    assert "'learn_graph.status'" in expression
    assert aliases["q0"] == "ok"


# Test a nested qualified filter evaluates correctly.
def test_evaluate_entry_filter_handles_nested_paths():
    view = build_entry_view({"sample_size": 1000}, _metadata())
    assert evaluate_entry_filter(
        "evaluate_graph.hyperparameters.iss > 0.5", view
    )
    assert not evaluate_entry_filter(
        "evaluate_graph.hyperparameters.iss > 10", view
    )


# Test a qualified filter combined with a matrix value.
def test_evaluate_entry_filter_combines_matrix_and_metadata():
    view = build_entry_view({"sample_size": 1000}, _metadata())
    assert evaluate_entry_filter(
        "learn_graph.status == 'ok' and sample_size < 10000",
        view,
    )


# Test history entries that are not mappings are skipped.
def test_build_entry_view_skips_non_mapping_history():
    metadata = build_metadata("p", "a", {}, {}, history={"bad": "value"})
    view = build_entry_view({}, metadata)
    assert "a.status" not in view


# Test history producer identity can come from a provenance block.
def test_build_entry_view_uses_history_provenance():
    metadata = build_metadata(
        "p",
        "a",
        {},
        {},
        history={
            "legacy-key": {
                "provenance": {"provider": "q", "action": "b"},
                "result": {"status": "ok"},
            }
        },
    )
    view = build_entry_view({}, metadata)
    assert view["b.status"] == "ok"
    assert view["q.b.status"] == "ok"


# Test history keys without a dot and without provenance are ignored.
def test_build_entry_view_ignores_unnamed_history():
    metadata = build_metadata(
        "p",
        "a",
        {},
        {},
        history={"nodot": {"result": {"status": "ok"}}},
    )
    view = build_entry_view({}, metadata)
    assert "status" not in view
    assert "a.status" not in view


# Test a flat history entry is treated as its result block.
def test_build_entry_view_treats_flat_history_as_result():
    metadata = build_metadata(
        "p",
        "a",
        {},
        {},
        history={"q.b": {"status": "ok"}},
    )
    view = build_entry_view({}, metadata)
    assert view["b.status"] == "ok"


# Test non-attribute expressions are left unchanged.
def test_resolve_qualified_names_ignores_non_attribute_chains():
    expression, aliases = resolve_qualified_names("(1 + 2).x", {})
    assert expression == "(1 + 2).x"
    assert aliases == {}


# Test an unknown qualified name raises an evaluation error.
def test_evaluate_entry_filter_raises_for_unknown_name():
    view = build_entry_view({}, _metadata())
    with pytest.raises(Exception):
        evaluate_entry_filter("learn_graph.unknown > 1", view)
