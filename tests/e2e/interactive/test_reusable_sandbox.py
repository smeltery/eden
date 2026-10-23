"""Interactive calls preserve a caller-managed sandbox and its environment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from eden import AbortController, Aborted, BranchStrategy, IterationContext, create_sandbox
from eden.sandboxes.no_sandbox import provider

pytestmark = pytest.mark.e2e


class ProbeAgent:
    name = "interactive-probe"
    model = "test"

    def __init__(self, output: Path) -> None:
        self._env = {"AGENT_SETTING": "agent"}
        self.output = output
        self.prompts: list[str] = []

    def build_command(self, ctx: IterationContext) -> list[str]:
        raise AssertionError("interactive command should be preferred")

    def build_interactive_command(self, ctx: IterationContext) -> list[str]:
        self.prompts.append(ctx.prompt)
        script = (
            "import json, os; from pathlib import Path; "
            f"Path({str(self.output)!r}).write_text(json.dumps("
            "{key: os.environ[key] for key in "
            "['CREATE_SETTING', 'CALL_SETTING', 'AGENT_SETTING']})); "
            "Path('interactive.txt').write_text('kept'); "
            "raise SystemExit(7)"
        )
        return [sys.executable, "-c", script]

    def parse_stream(self, line: str) -> None:
        return None


def test_interactive_reuses_handle_and_keeps_changes(
    e2e_git_repo: Path,
    tmp_path: Path,
) -> None:
    agent = ProbeAgent(tmp_path / "observed.json")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Branch {{SOURCE_BRANCH}}: {{TASK}}", encoding="utf-8")
    with create_sandbox(
        sandbox=provider(),
        cwd=e2e_git_repo,
        branch_strategy=BranchStrategy.named("interactive-test"),
        env={"CREATE_SETTING": "creation"},
    ) as sandbox:
        handle = sandbox.handle
        result = sandbox.interactive(
            agent=agent,
            prompt_file=prompt,
            prompt_args={"TASK": "inspect"},
            env={"CALL_SETTING": "call"},
            collect_args=False,
        )
        assert sandbox.handle is handle
        assert result.exit_code == 7
        assert result.branch == "interactive-test"
        assert result.worktree_path == sandbox.worktree.worktree_path
        assert agent.prompts == ["Branch interactive-test: inspect"]
        assert json.loads(agent.output.read_text()) == {
            "CREATE_SETTING": "creation",
            "CALL_SETTING": "call",
            "AGENT_SETTING": "agent",
        }
        assert (result.worktree_path / "interactive.txt").read_text() == "kept"
        assert sandbox.exec(f'"{sys.executable}" -c "print(42)"').stdout.strip() == "42"
        sandbox.interactive(agent=agent, env={"CALL_SETTING": "second"})
        assert agent.prompts[-1] == ""
        assert json.loads(agent.output.read_text())["CALL_SETTING"] == "second"


def test_aborted_interactive_leaves_sandbox_usable(e2e_git_repo: Path, tmp_path: Path) -> None:
    controller = AbortController()
    controller.abort()
    with create_sandbox(sandbox=provider(), cwd=e2e_git_repo, branch="abort-test") as sandbox:
        agent = ProbeAgent(tmp_path / "unused.json")
        with pytest.raises(Aborted):
            sandbox.interactive(agent=agent, signal=controller.signal)
        assert agent.prompts == []
        assert sandbox.exec(f'"{sys.executable}" -c "print(42)"').exit_code == 0


def test_invalid_prompt_keeps_sandbox_open(e2e_git_repo: Path, tmp_path: Path) -> None:
    from eden import InvalidOptions

    with create_sandbox(sandbox=provider(), cwd=e2e_git_repo, branch="invalid-test") as sandbox:
        with pytest.raises(InvalidOptions):
            sandbox.interactive(
                agent=ProbeAgent(tmp_path / "unused.json"),
                prompt="literal",
                prompt_file=tmp_path / "missing.md",
            )
        assert sandbox.exec(f'"{sys.executable}" -c "print(42)"').exit_code == 0
