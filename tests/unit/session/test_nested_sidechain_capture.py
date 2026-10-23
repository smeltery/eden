"""Session-scoped Claude transcript capture regression tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from eden.session import capture_sidechain_sessions
from eden.session._slug import claude_projects_slug

pytestmark = pytest.mark.unit


def test_nested_capture_scopes_session_and_rewrites_paths(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    cwd = Path("/workspace")
    project = home / ".claude/projects" / claude_projects_slug(cwd)
    for session in ("current", "unrelated"):
        nested = project / session / "subagents"
        nested.mkdir(parents=True)
        (nested / "agent-one.jsonl").write_text(
            json.dumps({"cwd": "/workspace", "text": "hello"}) + "\n", encoding="utf-8"
        )
    nested = project / "current/subagents"
    (nested / "notes.jsonl").write_text("{}", encoding="utf-8")
    stale = nested / "agent-old.jsonl"
    stale.write_text("{}", encoding="utf-8")
    os.utime(stale, (1, 1))

    captured = capture_sidechain_sessions(
        main_session_id="current",
        sandbox_cwd=cwd,
        host_repo_path=repo,
        branch="feat/test",
        iteration=1,
        since=2,
        home=home,
    )

    assert len(captured) == 1
    assert captured[0].name == "iter-1-current-sub-agent-one.jsonl"
    assert captured[0].parent == repo / ".eden/sessions/feat-test"
    assert json.loads(captured[0].read_text(encoding="utf-8"))["cwd"] == str(repo)


def test_bad_nested_transcript_does_not_drop_siblings(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    cwd = tmp_path / "repo"
    project = tmp_path / ".claude/projects" / claude_projects_slug(cwd)
    nested = project / "main/subagents"
    nested.mkdir(parents=True)
    (nested / "agent-bad.jsonl").write_bytes(b"\xff\xfe")
    (nested / "agent-good.jsonl").write_text('{"text":"ok"}\n', encoding="utf-8")

    captured = capture_sidechain_sessions(
        main_session_id="main",
        sandbox_cwd=cwd,
        host_repo_path=cwd,
        branch="main",
        iteration=0,
        home=tmp_path,
    )

    assert [p.name for p in captured] == ["iter-0-main-sub-agent-good.jsonl"]
    assert "Could not capture Claude subagent transcript" in caplog.text


def test_storage_captures_nested_transcripts_with_main_session(tmp_path: Path) -> None:
    from eden.providers import CreateOptions
    from eden.sandboxes.no_sandbox import provider
    from eden.session import ClaudeSessionStorage

    repo = tmp_path / "repo"
    repo.mkdir()
    project = tmp_path / ".claude/projects" / claude_projects_slug(repo)
    nested = project / "main/subagents"
    nested.mkdir(parents=True)
    (project / "main.jsonl").write_text('{"text":"main"}\n', encoding="utf-8")
    (nested / "agent-child.jsonl").write_text('{"text":"child"}\n', encoding="utf-8")
    handle = provider().create(
        CreateOptions(
            branch="main",
            worktree_path=repo,
            host_repo_path=repo,
            env={},
            mounts=(),
            name_hint=None,
        )
    )
    try:
        captured = ClaudeSessionStorage(home=tmp_path).host_capture(
            handle=handle,
            session_id="main",
            host_repo_path=repo,
            branch="main",
            iteration=0,
        )
    finally:
        handle.close()
    assert captured is not None and captured.is_file()
    child = captured.parent / "iter-0-main-sub-agent-child.jsonl"
    assert json.loads(child.read_text(encoding="utf-8")) == {"text": "child"}
