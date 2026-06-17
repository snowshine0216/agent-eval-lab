"""EDGE: the chat-loop B-set candidate driver (spec §5 / §11.5).

For qwen-max / deepseek / MiniMax: each trial gets a FRESH playwright-cli session
+ isolated workdir (make_bash_executor, allowlist-confined to {"playwright-cli"}),
the static B-1 user prompt re-rendered with the per-trial save-name + candidate
login + folder (render_b_prompt), and the browse loop (run_single + BROWSE_TOOLS),
max_rounds=50. Same (task, run_index, save_name) -> Trajectory callback shape as
the claude -p driver, so b_live drives either identically.

make_bash_executor + run_single are injected (executor_factory / run_single_fn) so
the test suite needs no playwright-cli, no fs writes, and no live provider.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import httpx

from agent_eval_lab.datasets.b_tasks import render_b_prompt
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.bash_edge import make_bash_executor
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.tasks.schema import Task, TaskInput
from agent_eval_lab.tools.browse import BROWSE_TOOLS, apply_browse

B_MAX_ROUNDS = 50  # spec §11.5 / decision 6 — keep 50, calibrate-first per runbook.


def _render_task(
    task: Task, *, save_name: str, login: tuple[str, str], folder: str
) -> Task:
    """Re-render the user message with the per-trial save-name/login/folder; keep
    the system message (and any skill-arm injection) verbatim."""
    user = next((m for m in task.input.messages if m.role == "user"), None)
    base_user = user.content if user is not None else ""
    rendered_user = render_b_prompt(
        base_user, save_name=save_name, login=login, folder=folder
    )
    messages = tuple(
        MessageTurn(role="user", content=rendered_user) if m.role == "user" else m
        for m in task.input.messages
    )
    return replace(
        task,
        input=TaskInput(messages=messages, available_tools=task.input.available_tools),
    )


def make_b_chat_run_fn(
    *,
    config: ProviderConfig,
    http_client: httpx.Client,
    temperature: float,
    max_tokens: int,
    condition_id: str,
    login: tuple[str, str],
    folder: str,
    workdir_root: Path,
    max_rounds: int = B_MAX_ROUNDS,
    executor_factory: Callable[
        ..., tuple[Callable, Callable[[], None]]
    ] = make_bash_executor,
    run_single_fn: Callable[..., Trajectory] = run_single,
) -> Callable[[Task, int, str], Trajectory]:
    """Build the per-trial chat-loop candidate driver for one arm."""

    def run_fn(task: Task, run_index: int, save_name: str) -> Trajectory:
        rendered = _render_task(task, save_name=save_name, login=login, folder=folder)
        workdir = workdir_root / f"b-work-{save_name}"
        executor, close = executor_factory(session_id=save_name, workdir=workdir)
        try:
            return run_single_fn(
                task=rendered,
                registry=BROWSE_TOOLS,
                config=config,
                http_client=http_client,
                run_index=run_index,
                temperature=temperature,
                max_tokens=max_tokens,
                apply_fn=apply_browse,
                executor=executor,
                run_uid=f"{condition_id}__{task.id}__{run_index:04d}",
                max_rounds=max_rounds,
            )
        finally:
            close()

    return run_fn
