"""Sandbox creation anchors all host-side operations to the requested repo."""

from __future__ import annotations

from pathlib import Path

import pytest

from eden import BranchStrategy, CwdError, create_sandbox
from eden.sandboxes.no_sandbox import provider

pytestmark = pytest.mark.unit


def test_create_from_outside_target_repository(
    tmp_git_repo: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside = tmp_path_factory.mktemp("outside")
    monkeypatch.chdir(outside)
    config = tmp_git_repo / ".eden"
    config.mkdir()
    (config / ".env").write_text("TARGET_REPO_SETTING=target\n", encoding="utf-8")
    with create_sandbox(
        sandbox=provider(),
        cwd=tmp_git_repo,
        branch_strategy=BranchStrategy.named("target"),
    ) as sandbox:
        assert sandbox.cwd == tmp_git_repo.resolve()
        assert sandbox.worktree.host_repo_path == tmp_git_repo.resolve()
        assert sandbox.worktree.worktree_path.is_relative_to(config.resolve())
        assert sandbox.create_env["TARGET_REPO_SETTING"] == "target"
        assert not (outside / ".eden").exists()


def test_relative_target_resolves_before_creation(
    tmp_git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_git_repo.parent)
    with create_sandbox(sandbox=provider(), cwd=Path(tmp_git_repo.name), branch="relative") as s:
        assert s.cwd == tmp_git_repo.resolve()
        assert s.worktree.host_repo_path == tmp_git_repo.resolve()


def test_invalid_target_fails_before_creating_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CwdError):
        create_sandbox(sandbox=provider(), cwd=tmp_path / "missing")
    assert not (tmp_path / ".eden").exists()
