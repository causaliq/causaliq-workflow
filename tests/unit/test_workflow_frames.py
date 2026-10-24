"""Tests for workflow-call grammar and call-stack frames."""

import os
from pathlib import Path

import pytest

from causaliq_workflow.workflow.frames import (
    WorkflowFrame,
    call_base_dir,
    canonical_key,
    find_recursive_frame,
    format_call_chain,
    has_workflow_suffix,
    is_workflow_call_step,
    is_workflow_path,
    looks_like_workflow_file,
    resolve_call_target,
    root_frames,
    workflow_frame,
)


# is_workflow_path accepts only dot-relative paths.
@pytest.mark.parametrize(
    ("uses", "expected"),
    [
        ("./child.yml", True),
        ("../shared/child.yml", True),
        (".\\child.yml", True),
        ("child.yml", False),
        ("causaliq-discovery", False),
        ("", False),
    ],
)
def test_is_workflow_path(uses: str, expected: bool) -> None:
    assert is_workflow_path(uses) is expected


# is_workflow_call_step ignores steps that are not dictionaries.
def test_is_workflow_call_step_non_dict() -> None:
    assert is_workflow_call_step("uses: ./child.yml") is False


# is_workflow_call_step detects a relative uses value.
def test_is_workflow_call_step_detects_path() -> None:
    assert is_workflow_call_step({"uses": "./child.yml"}) is True


# is_workflow_call_step ignores action providers.
def test_is_workflow_call_step_ignores_provider() -> None:
    assert is_workflow_call_step({"uses": "causaliq-discovery"}) is False


# looks_like_workflow_file recognises YAML suffixes only.
@pytest.mark.parametrize(
    ("uses", "expected"),
    [
        ("./child.yml", True),
        ("child.yaml", True),
        (".\\child.YML", True),
        ("child.txt", False),
        ("causaliq-discovery", False),
        (None, False),
        (42, False),
    ],
)
def test_looks_like_workflow_file(uses: object, expected: bool) -> None:
    assert looks_like_workflow_file(uses) is expected


# has_workflow_suffix checks the path suffix case-insensitively.
@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("child.yml", True),
        ("child.YAML", True),
        ("child.txt", False),
        ("child", False),
    ],
)
def test_has_workflow_suffix(target: str, expected: bool) -> None:
    assert has_workflow_suffix(target) is expected


# workflow_frame records the canonical path and its directory.
def test_workflow_frame_resolves_path(tmp_path: Path) -> None:
    frame = workflow_frame(tmp_path / "child.yml")
    assert frame.path == (tmp_path / "child.yml").resolve()
    assert frame.source_dir == tmp_path.resolve()


# root_frames returns an empty stack when no source path is known.
def test_root_frames_without_source_path() -> None:
    assert root_frames(None) == ()


# root_frames seeds the stack with the top-level workflow.
def test_root_frames_returns_source_frame(tmp_path: Path) -> None:
    frames = root_frames(tmp_path / "parent.yml")
    assert len(frames) == 1
    assert frames[0].source_dir == tmp_path.resolve()


# call_base_dir falls back to the current directory.
def test_call_base_dir_without_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert call_base_dir(()) == Path.cwd()


# call_base_dir uses the innermost frame's directory.
def test_call_base_dir_uses_last_frame(tmp_path: Path) -> None:
    frame = WorkflowFrame(tmp_path / "a.yml", tmp_path / "nested")
    assert call_base_dir((frame,)) == tmp_path / "nested"


# resolve_call_target resolves against the calling workflow's directory.
def test_resolve_call_target_uses_frame_dir(tmp_path: Path) -> None:
    frame = workflow_frame(tmp_path / "parent.yml")
    target = resolve_call_target("./child.yml", (frame,))
    assert target == (tmp_path / "child.yml").resolve()


# resolve_call_target resolves against the current directory by default.
def test_resolve_call_target_uses_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    target = resolve_call_target("./child.yml", ())
    assert target == (Path.cwd() / "child.yml").resolve()


# canonical_key matches the platform path normalisation.
def test_canonical_key_uses_normcase(tmp_path: Path) -> None:
    path = tmp_path / "child.yml"
    assert canonical_key(path) == os.path.normcase(str(path))


# find_recursive_frame returns the frame holding the target.
def test_find_recursive_frame_returns_match(tmp_path: Path) -> None:
    target = (tmp_path / "child.yml").resolve()
    frame = workflow_frame(target)
    assert find_recursive_frame(target, (frame,)) is frame


# find_recursive_frame returns None for a new workflow.
def test_find_recursive_frame_returns_none(tmp_path: Path) -> None:
    frame = workflow_frame(tmp_path / "parent.yml")
    target = (tmp_path / "child.yml").resolve()
    assert find_recursive_frame(target, (frame,)) is None


# format_call_chain names every workflow in the cycle.
def test_format_call_chain(tmp_path: Path) -> None:
    frames = (
        workflow_frame(tmp_path / "parent.yml"),
        workflow_frame(tmp_path / "child.yml"),
    )
    target = (tmp_path / "parent.yml").resolve()
    assert format_call_chain(frames, target) == (
        "parent.yml -> child.yml -> parent.yml"
    )
