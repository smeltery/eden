"""Verify GitHub agent workflow template rendering."""

from __future__ import annotations

from hashlib import sha256

import pytest

from eden.cli._templates._backlog import get_backlog_manager
from eden.cli._templates.github import render_github_agent_workflows

pytestmark = pytest.mark.unit


def _fingerprint(files: dict[str, str]) -> str:
    rendered = "".join(f"{path}\0{contents}\0" for path, contents in sorted(files.items()))
    return sha256(rendered.encode()).hexdigest()


def test_render_github_agent_workflows_exact_github_output() -> None:
    files = render_github_agent_workflows(
        sandbox="docker",
        agent="claude-code",
        model="m",
        image_name="eden:test",
        backlog=get_backlog_manager("github"),
    )

    assert set(files) == {
        "../.github/workflows/eden-agent-implement.yml",
        "../.github/workflows/eden-agent-review.yml",
        "Dockerfile",
        "github/implement_issue.py",
        "github/review_pr.py",
        "github/factory.py",
        "github/implement-issue.md",
        "github/review-pr.md",
        "github/SETUP_TRACKER.md",
        "github/REVIEW_OUTPUT.md",
        "CODING_STANDARDS.md",
        ".env.example",
        ".gitignore",
    }
    assert _fingerprint(files) == "8fa2bf80fc88773b3a4e2f97c0638bc5bdd8c6130a558cdb82c0290f5e25e969"


def test_render_github_agent_workflows_exact_custom_output() -> None:
    files = render_github_agent_workflows(
        sandbox="podman",
        agent="codex",
        model="gpt-5",
        image_name="eden:pod",
        backlog=get_backlog_manager("custom"),
    )

    assert _fingerprint(files) == "185a06b35dd78f722d5f17e6bf6bb0756747351e96ca33f4ae743f80fa5bf664"


def test_review_uses_unprivileged_same_repository_event() -> None:
    files = render_github_agent_workflows(
        sandbox="docker",
        agent="codex",
        model="m",
        image_name="eden:test",
        backlog=get_backlog_manager("github"),
    )
    workflow = files["../.github/workflows/eden-agent-review.yml"]
    assert "\n  pull_request:\n" in workflow
    assert "pull_request_target" not in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "CODEX_API_KEY: ${{ secrets.CODEX_API_KEY }}" in workflow
    assert "CODEX_API_KEY=" in files[".env.example"]
    assert "OPENAI_API_KEY" not in files[".env.example"]
