"""Interactive sessions that borrow an existing sandbox's resources."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

from eden.abort import AbortSignal
from eden.agents._env import agent_env
from eden.agents._protocol import Agent
from eden.env import merge_env

if TYPE_CHECKING:
    from eden.orchestrator.interactive import InteractiveResult
    from eden.sandboxes._sandbox import Sandbox


class _SandboxInteractive:
    def interactive(
        self,
        *,
        agent: Agent,
        prompt: str | None = None,
        prompt_file: str | Path | None = None,
        prompt_args: Mapping[str, object] | None = None,
        env: Mapping[str, str] | None = None,
        name: str | None = None,
        collect_args: bool | None = None,
        signal: AbortSignal | None = None,
    ) -> InteractiveResult:
        """Attach an agent TTY without recreating or closing this sandbox."""
        from eden.orchestrator.interactive._interactive_exec import (
            build_interactive_argv,
            run_interactive_exec,
        )
        from eden.orchestrator.interactive._interactive_prompt import render_interactive_prompt
        from eden.orchestrator.interactive._interactive_resources import (
            prepare_interactive_resources,
        )
        from eden.orchestrator.interactive._session import InteractiveResult

        sandbox = cast("Sandbox", self)
        resources = prepare_interactive_resources(
            sandbox=sandbox.sandbox_provider,
            signal=signal,
            existing_worktree=sandbox.worktree,
            cwd=sandbox.cwd,
            prompt=prompt,
            prompt_file=prompt_file,
            prompt_args=prompt_args,
            env=env,
            branch_strategy=None,
            base_branch=None,
            copy_to_worktree=None,
            name=name,
            throw_on_duplicate_worktree=True,
            timeouts=sandbox.timeouts,
        )
        merged_env = merge_env(sandbox.create_env, resources.merged_env, agent_env(agent))
        rendered = render_interactive_prompt(
            prompt_text=resources.prompt_text,
            prompt_is_literal=resources.prompt_is_literal,
            prompt_args=prompt_args,
            collect_args=collect_args,
            source_branch=sandbox.worktree.branch,
            target_branch=resources.target_branch,
            handle=sandbox.handle,
        )
        argv = build_interactive_argv(
            agent=agent,
            rendered_prompt=rendered,
            handle=sandbox.handle,
            worktree_path=sandbox.worktree.worktree_path,
            branch=sandbox.worktree.branch,
            name=name,
        )
        exit_code = run_interactive_exec(
            handle=sandbox.handle,
            sandbox_name=sandbox.sandbox_provider.name,
            argv=argv,
            env=merged_env,
            signal=signal,
        )
        return InteractiveResult(
            branch=sandbox.worktree.branch,
            exit_code=exit_code,
            worktree_path=sandbox.worktree.worktree_path,
            cwd=resources.cwd_path,
        )
