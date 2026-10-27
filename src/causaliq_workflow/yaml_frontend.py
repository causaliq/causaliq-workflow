"""Workflow YAML front-end with predictable scalar typing.

PyYAML applies YAML 1.1 implicit typing by default, which turns values
such as ``no``, ``01`` and ``2020-01-01`` into booleans, octal integers
and dates. CausalIQ workflow values are plain text far more often than
they are those types, so this module restricts implicit typing to the
YAML 1.2 core spellings.

The module also shields ``{{name}}`` template tokens from the YAML
parser. A whole-value token such as ``sample_size: {{sample_size}}`` is
otherwise read as a nested mapping. Each token is replaced with a safe
plain-scalar sentinel before parsing and restored afterwards.
"""

import re
import uuid
from typing import Any, Dict, Tuple

import yaml

_TEMPLATE_TOKEN_PATTERN = re.compile(r"\{\{[a-zA-Z_][a-zA-Z0-9_-]*\}\}")

_DROPPED_TAGS = frozenset(
    {
        "tag:yaml.org,2002:bool",
        "tag:yaml.org,2002:int",
        "tag:yaml.org,2002:float",
        "tag:yaml.org,2002:timestamp",
    }
)

_BOOL_PATTERN = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$")

_INT_PATTERN = re.compile(r"^[-+]?(?:0|[1-9][0-9]*)$")

_FLOAT_PATTERN = re.compile(
    r"^[-+]?(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?$"
)


class WorkflowLoader(yaml.SafeLoader):
    """SafeLoader with predictable scalar typing for workflows."""


WorkflowLoader.yaml_implicit_resolvers = {
    first: [
        (tag, regexp) for tag, regexp in resolvers if tag not in _DROPPED_TAGS
    ]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

WorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", _BOOL_PATTERN, list("tTfF")
)
WorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int", _INT_PATTERN, list("-+0123456789")
)
WorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float", _FLOAT_PATTERN, list("-+0123456789.")
)


def _protect_template_tokens(text: str) -> Tuple[str, Dict[str, str]]:
    """Replace template tokens with YAML-safe sentinels.

    Args:
        text: Workflow YAML text.

    Returns:
        The protected text and a mapping of sentinel to original token.
    """
    nonce = uuid.uuid4().hex
    tokens: Dict[str, str] = {}

    def _replace(match: "re.Match[str]") -> str:
        sentinel = f"__cq_token_{nonce}_{len(tokens)}__"
        tokens[sentinel] = match.group(0)
        return sentinel

    return _TEMPLATE_TOKEN_PATTERN.sub(_replace, text), tokens


def _restore_template_tokens(obj: Any, tokens: Dict[str, str]) -> Any:
    """Restore template tokens in a parsed workflow object.

    Args:
        obj: Parsed YAML value.
        tokens: Mapping of sentinel to original token.

    Returns:
        The value with every sentinel replaced by its token.
    """
    if isinstance(obj, dict):
        return {
            _restore_template_tokens(key, tokens): (
                _restore_template_tokens(value, tokens)
            )
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [_restore_template_tokens(item, tokens) for item in obj]
    if isinstance(obj, str):
        for sentinel, token in tokens.items():
            obj = obj.replace(sentinel, token)
    return obj


def load_workflow_text(text: str) -> Any:
    """Parse workflow YAML with CausalIQ value rules.

    Args:
        text: Workflow YAML text.

    Returns:
        Parsed YAML value.

    Raises:
        yaml.YAMLError: If the text is not valid YAML.
    """
    protected, tokens = _protect_template_tokens(text)
    data = yaml.load(protected, Loader=WorkflowLoader)
    return _restore_template_tokens(data, tokens)


def parse_scalar_text(text: str) -> Any:
    """Parse one CLI parameter value with CausalIQ value rules.

    Args:
        text: Parameter value text.

    Returns:
        The parsed value: a scalar, a list or None.

    Raises:
        yaml.YAMLError: If the text is not valid YAML.
    """
    return yaml.load(text, Loader=WorkflowLoader)
