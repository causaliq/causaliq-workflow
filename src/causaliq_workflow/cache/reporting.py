"""Reporting view and qualified-name resolution for cache metadata.

The view flattens an entry into the names used by filters, summaries and
plot columns:

- bare names for matrix values and result-object fields;
- ``action.field`` for metadata when the name is unique;
- ``action.inputs.field`` and ``action.result.field`` for explicit access;
- ``provider.action.field`` and ``provider.action.block.field`` for
  provider-qualified access, with the provider name normalised to
  underscores.

Filter expressions are rewritten before evaluation because the
underlying evaluator cannot address dotted keys directly.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, Iterable, List, Tuple, cast

from causaliq_core.metadata import MetadataParts, split_metadata
from causaliq_core.utils import evaluate_filter

__all__ = [
    "build_entry_view",
    "evaluate_entry_filter",
    "flatten_block",
    "resolve_qualified_names",
]

_BLOCKS = ("inputs", "result")


def flatten_block(
    block: Dict[str, Any],
    prefix: str = "",
) -> Iterable[Tuple[str, Any]]:
    """Yield dotted paths and values for a nested metadata block.

    Args:
        block: Mapping to flatten.
        prefix: Path prefix used by recursive calls.

    Yields:
        Tuples of (dotted path, value), including intermediate mappings.
    """
    for key, value in block.items():
        path = f"{prefix}{key}"
        yield path, value
        if isinstance(value, dict):
            yield from flatten_block(value, f"{path}.")


def build_entry_view(
    matrix_values: Dict[str, Any],
    metadata: Dict[str, Any],
    object_values: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the flat reporting view for one cache entry.

    Args:
        matrix_values: Entry's matrix variable values.
        metadata: Entry's metadata, in version 2 or legacy form.
        object_values: Result-object fields, which override bare names.

    Returns:
        Flat mapping of names to values.
    """
    view: Dict[str, Any] = dict(matrix_values)
    parts = split_metadata(metadata)
    short: Dict[Tuple[str, str], List[Any]] = {}
    _add_blocks(
        view,
        short,
        parts.provenance.get("provider"),
        parts.provenance.get("action"),
        parts.inputs,
        parts.result,
    )
    _add_history(view, short, parts)
    if not _has_producer(parts):
        _add_anonymous(view, parts)
    for (action, path), values in short.items():
        if len(values) == 1:
            view[f"{action}.{path}"] = values[0]
    if object_values:
        view.update(object_values)
    return view


def _has_producer(parts: MetadataParts) -> bool:
    """Return True when provenance names a provider and action."""
    provider = parts.provenance.get("provider")
    action = parts.provenance.get("action")
    return isinstance(provider, str) and isinstance(action, str)


def _add_anonymous(view: Dict[str, Any], parts: MetadataParts) -> None:
    """Expose flat metadata fields when no producer is recorded."""
    for block in (parts.inputs, parts.result):
        for path, value in flatten_block(block):
            view.setdefault(path, value)


def _add_blocks(
    view: Dict[str, Any],
    short: Dict[Tuple[str, str], List[Any]],
    provider: Any,
    action: Any,
    inputs: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    """Add one producer's input and result fields to the view."""
    if not isinstance(provider, str) or not isinstance(action, str):
        return
    provider_key = provider.replace("-", "_")
    for block_name in _BLOCKS:
        block = inputs if block_name == "inputs" else result
        for path, value in flatten_block(block):
            view[f"{action}.{block_name}.{path}"] = value
            view[f"{provider_key}.{action}.{block_name}.{path}"] = value
            view[f"{provider_key}.{action}.{path}"] = value
            short.setdefault((action, path), []).append(value)


def _add_history(
    view: Dict[str, Any],
    short: Dict[Tuple[str, str], List[Any]],
    parts: MetadataParts,
) -> None:
    """Add inherited producer blocks to the view."""
    for producer_key, blocks in parts.history.items():
        if not isinstance(blocks, dict):
            continue
        provider, action = _producer_parts(producer_key, blocks)
        _add_blocks(
            view,
            short,
            provider,
            action,
            _block(blocks, "inputs"),
            _block(blocks, "result"),
        )


def _producer_parts(
    producer_key: str,
    blocks: Dict[str, Any],
) -> Tuple[Any, Any]:
    """Return the provider and action names of a history block."""
    provenance = blocks.get("provenance")
    if isinstance(provenance, dict):
        provider = provenance.get("provider")
        action = provenance.get("action")
        if isinstance(provider, str) and isinstance(action, str):
            return provider, action
    if "." in producer_key:
        provider, action = producer_key.rsplit(".", 1)
        return provider, action
    return None, None


def _block(blocks: Dict[str, Any], name: str) -> Dict[str, Any]:
    """Return a named block, treating a flat history entry as result."""
    value = blocks.get(name)
    if isinstance(value, dict):
        return value
    if name == "result" and not any(key in blocks for key in _BLOCKS):
        return blocks
    return {}


def resolve_qualified_names(
    expression: str,
    view: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Rewrite qualified names in a filter expression to safe aliases.

    Args:
        expression: Filter expression written by the user.
        view: Flat reporting view whose dotted keys are addressable.

    Returns:
        Tuple of (rewritten expression, alias values).
    """
    keys = {key for key in view if isinstance(key, str) and "." in key}
    tree = ast.parse(expression, mode="eval")
    rewriter = _NameRewriter(keys, view)
    rewritten = rewriter.visit(tree)
    ast.fix_missing_locations(rewritten)
    return ast.unparse(rewritten), rewriter.aliases


class _NameRewriter(ast.NodeTransformer):
    """Replace dotted references with aliases present in the view."""

    def __init__(self, keys: Iterable[str], view: Dict[str, Any]) -> None:
        """Store the addressable keys and their values."""
        self.keys = set(keys)
        self.view = view
        self.aliases: Dict[str, Any] = {}

    def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
        """Rewrite an attribute chain when it names a view key."""
        name = _attribute_name(node)
        if name is not None and name in self.keys:
            alias = f"q{len(self.aliases)}"
            self.aliases[alias] = self.view[name]
            return ast.copy_location(ast.Name(id=alias, ctx=ast.Load()), node)
        return cast(ast.expr, self.generic_visit(node))


def _attribute_name(node: ast.AST) -> str | None:
    """Return the dotted name of an attribute chain, or None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attribute_name(node.value)
        return f"{parent}.{node.attr}" if parent is not None else None
    return None


def evaluate_entry_filter(
    expression: str,
    view: Dict[str, Any],
) -> bool:
    """Evaluate a filter expression against a reporting view.

    Args:
        expression: Filter expression written by the user.
        view: Flat reporting view.

    Returns:
        True when the view matches the expression.
    """
    rewritten, aliases = resolve_qualified_names(expression, view)
    return evaluate_filter(rewritten, {**view, **aliases})
