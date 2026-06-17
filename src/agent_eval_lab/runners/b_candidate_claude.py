"""EDGE: the `claude -p` B-set candidate driver (spec §5 / §11.6).

Reuses claude_cli_candidate building blocks (parse_claude_result, _sanitized_env,
_env_invalid_trajectory). Unlike the F baseline this driver materializes NO code
tree and reads NO tree back — the candidate's effect is the saved MSTR object,
graded later by the owner verdict (ADR-0021). It needs native Bash + playwright-cli
on PATH and the REAL HOME (OAuth in Keychain), so it is NOT OS-confined: the
spike's §7 residual limitation (mitigated by store relocation, not closed). Same
(task, run_index, save_name) -> Trajectory callback shape as the chat driver.

run_subprocess + workdir_factory are injected so the test suite needs no `claude`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable

from agent_eval_lab.datasets.b_tasks import render_b_prompt
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.claude_cli_candidate import (
    ClaudeResultParseError,
    RunSubprocess,
    WorkdirFactory,
    _env_invalid_trajectory,
    _sanitized_env,
    parse_claude_result,
)

_B_SYSTEM = (
    "You are automating the MicroStrategy Library web UI with playwright-cli (a "
    "headless browser) driven through Bash. Complete the owner-specified report "
    "build exactly; do not take shortcuts via APIs. When the saved report renders "
    "the prompted result, reply with a one-line summary and stop."
)

_ALLOWED_TOOLS = ("Bash",)
_DENIED_TOOLS = ("WebFetch", "WebSearch", "Task")


def _build_b_claude_argv(
    *, model: str, prompt: str, max_budget_usd: float
) -> list[str]:
    """The `claude -p` argv for one B trial: --safe-mode (vanilla), Bash allowed for
    the live browser surface. No --max-turns in the CLI; the subprocess timeout +
    --max-budget-usd bound the run (cf. claude_cli_candidate.build_claude_argv)."""
    return [
        "claude",
        "-p",
        "--model",
        model,
        "--output-format",
        "json",
        "--safe-mode",
        "--disable-slash-commands",
        "--append-system-prompt",
        _B_SYSTEM,
        "--allowedTools",
        " ".join(_ALLOWED_TOOLS),
        "--disallowedTools",
        " ".join(_DENIED_TOOLS),
        "--max-budget-usd",
        str(max_budget_usd),
        prompt,
    ]


def make_b_claude_run_fn(
    *,
    model: str,
    run_subprocess: RunSubprocess,
    workdir_factory: WorkdirFactory,
    login: tuple[str, str],
    folder: str,
    max_budget_usd: float = 1.0,
    timeout_s: int = 600,
) -> Callable[[object, int, str], Trajectory]:
    """Build the per-trial claude -p B candidate driver. Same callback signature as
    make_b_chat_run_fn (task, run_index, save_name) -> Trajectory."""

    def run_fn(task, run_index: int, save_name: str) -> Trajectory:
        workdir = workdir_factory()
        try:
            user = next((m for m in task.input.messages if m.role == "user"), None)
            base_user = user.content if user is not None else ""
            prompt = render_b_prompt(
                base_user, save_name=save_name, login=login, folder=folder
            )
            argv = _build_b_claude_argv(
                model=model, prompt=prompt, max_budget_usd=max_budget_usd
            )
            env = _sanitized_env(os.environ)
            try:
                completed = run_subprocess(
                    argv, cwd=str(workdir), env=env, timeout=timeout_s
                )
            except subprocess.TimeoutExpired:
                return _env_invalid_trajectory(run_index, raw="timeout")
            if getattr(completed, "returncode", 0) != 0:
                return _env_invalid_trajectory(
                    run_index,
                    raw=(
                        f"stdout: {getattr(completed, 'stdout', '')}\n"
                        f"stderr: {getattr(completed, 'stderr', '')}"
                    ),
                )
            try:
                meta = parse_claude_result(completed.stdout)
            except ClaudeResultParseError as exc:
                return _env_invalid_trajectory(run_index, raw=str(exc))
            if meta.is_error:
                return _env_invalid_trajectory(run_index, raw="claude is_error")
            return Trajectory(
                turns=(),
                usage=Usage(
                    prompt_tokens=meta.prompt_tokens,
                    completion_tokens=meta.completion_tokens,
                    latency_s=0.0,
                ),
                run_index=run_index,
                stop_reason="completed_natural",
                rounds=meta.num_turns,
                tool_call_counts={},
                total_cost_usd=meta.total_cost_usd,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    return run_fn
