"""EDGE: run vanilla `claude -p` (Sonnet 4.6, no skills) as the F-task agent.

A baseline harness DISTINCT from the lab's chat-loop runner: Claude Code drives
its own loop with its native tools over a materialized copy of the pinned
web-dossier tree, then the held-out Node oracle grades the produced tree. Auth is
the session's OAuth/subscription (no per-token dollars; total_cost_usd is the
API-equivalent efficiency metric). See
docs/superpowers/specs/2026-06-16-claude-p-f-baseline-design.md.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


class ClaudeResultParseError(ValueError):
    """`claude -p --output-format json` stdout could not be parsed into a result."""


@dataclass(frozen=True, kw_only=True)
class ClaudeRunMeta:
    prompt_tokens: int
    completion_tokens: int
    num_turns: int
    total_cost_usd: float
    is_error: bool


def parse_claude_result(stdout: str) -> ClaudeRunMeta:
    """Parse the single result object from `--output-format json`.

    Maps usage.input_tokens -> prompt_tokens, usage.output_tokens ->
    completion_tokens. Raises ClaudeResultParseError on malformed/incomplete JSON
    (the caller maps that to env-invalid, never a model FAIL)."""
    try:
        obj = json.loads(stdout)
        usage = obj["usage"]
        return ClaudeRunMeta(
            prompt_tokens=int(usage["input_tokens"]),
            completion_tokens=int(usage["output_tokens"]),
            num_turns=int(obj["num_turns"]),
            total_cost_usd=float(obj["total_cost_usd"]),
            is_error=bool(obj["is_error"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ClaudeResultParseError(str(exc)) from exc


SURFACES: tuple[str, ...] = ("edit-only", "natural")

# Inspect + edit tools every surface gets (Claude Code native tool names).
_BASE_ALLOWED_TOOLS: tuple[str, ...] = ("Read", "Edit", "Write", "Glob", "Grep")
# Never allowed in either baseline (keep it offline + non-agentic-delegating).
_ALWAYS_DENIED_TOOLS: tuple[str, ...] = ("WebFetch", "WebSearch", "Task")

_EDIT_SYSTEM_BASE = (
    "You are fixing code in a checked-out repository. The repository's files are "
    "in your current working directory. Inspect the relevant files, then make the "
    "owner-specified change. Change ONLY what the task requires; leave every other "
    "file and layer untouched. When the edit is complete, reply with a one-line "
    "summary and stop."
)
_NO_TESTS_LINE = "Do not attempt to run tests."


def claude_system_prompt(surface: str) -> str:
    """The edit instructions appended to Claude's system prompt. edit-only forbids
    running tests; natural allows it. No Factor-P scaffolding in either."""
    if surface not in SURFACES:
        raise ValueError(f"unknown surface: {surface!r}")
    if surface == "edit-only":
        return f"{_EDIT_SYSTEM_BASE}\n\n{_NO_TESTS_LINE}"
    return _EDIT_SYSTEM_BASE


def build_claude_argv(
    *,
    model: str,
    surface: str,
    prompt: str,
    system_prompt: str,
    max_budget_usd: float,
) -> list[str]:
    """Assemble the `claude -p` argv for one attempt. Pure list construction.

    Vanilla isolation is via **--safe-mode**: it disables ALL of the owner's
    customizations (CLAUDE.md, skills, plugins, hooks, MCP servers, custom commands
    /agents, output styles, workflows, themes, keybindings) while leaving Auth,
    model selection, built-in tools, and permissions working normally. This is why
    the run uses the REAL HOME (not a clean temp HOME): the OAuth credentials live
    in the macOS Keychain ($HOME/Library/Keychains) + ~/.claude.json, so a clean
    HOME would report "Not logged in". --disable-slash-commands is kept as a
    belt-and-suspenders. Bash is allowed iff natural. There is no --max-turns in
    CLI 2.1.177; rounds are bounded by the subprocess timeout (caller), with
    --max-budget-usd as a secondary cost stop."""
    if surface not in SURFACES:
        raise ValueError(f"unknown surface: {surface!r}")
    allowed = list(_BASE_ALLOWED_TOOLS) + (["Bash"] if surface == "natural" else [])
    denied = list(_ALWAYS_DENIED_TOOLS) + ([] if surface == "natural" else ["Bash"])
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
        system_prompt,
        "--allowedTools",
        " ".join(allowed),
        "--disallowedTools",
        " ".join(denied),
        "--max-budget-usd",
        str(max_budget_usd),
        prompt,
    ]


# ---- Tree materialization + readback ------------------------------------------

_READBACK_IGNORE: tuple[str, ...] = (".git", "node_modules")


def materialize_tree(tree: Mapping[str, str], dest: Path) -> None:
    """Write a {posix-relpath: content} tree to disk under dest."""
    for rel, content in tree.items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def read_back_tree(
    dest: Path, *, ignore: tuple[str, ...] = _READBACK_IGNORE
) -> dict[str, str]:
    """Read the produced tree back into {posix-relpath: content}, skipping any
    path under an ignored top-level dir (.git, node_modules)."""
    out: dict[str, str] = {}
    for path in sorted(dest.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dest)
        if rel.parts[0] in ignore:
            continue
        out[rel.as_posix()] = path.read_text()
    return out


# ---- Env sanitization --------------------------------------------------------

# Vars that could make the nested `claude -p` non-vanilla by leaking the PARENT
# session's effort level / plugin / config dir. --safe-mode already disables
# customizations, but stripping these keeps effort at the default and prevents a
# CLAUDE_CONFIG_DIR override from re-pointing config. We deliberately KEEP the real
# HOME (and never strip auth: ANTHROPIC_*, *TOKEN*, *KEY*, PATH, locale) — the OAuth
# credentials are resolved via $HOME (macOS Keychain + ~/.claude.json), so a clean
# HOME would report "Not logged in".
_CONTAMINATING_ENV_KEYS: tuple[str, ...] = (
    "CLAUDE_CONFIG_DIR",
    "XDG_CONFIG_HOME",
    "CLAUDE_CODE_EFFORT_LEVEL",
    "CLAUDE_EFFORT",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_PLUGIN_DATA",
)


def _sanitized_env(base_env: Mapping[str, str]) -> dict[str, str]:
    """Return a new env dict with the contaminating keys removed. HOME is preserved
    (auth resolves via $HOME); vanilla isolation comes from --safe-mode, not HOME."""
    return {k: v for k, v in base_env.items() if k not in _CONTAMINATING_ENV_KEYS}


# ---- run_fn factory -----------------------------------------------------------

from agent_eval_lab.records.trajectory import (  # noqa: E402
    PROVIDER_ERROR,
    ParseFailure,
    Trajectory,
    Usage,
)
from agent_eval_lab.runners.multi_run import ReplacementOutcome  # noqa: E402

# Injected so unit tests need no real `claude` / network.
RunSubprocess = Callable[..., object]  # (argv, *, cwd, env, timeout) -> completed
WorkdirFactory = Callable[[], Path]  # () -> workdir (the seeded tree root)


def _user_prompt(edit_task) -> str:
    msg = next((m for m in edit_task.input.messages if m.role == "user"), None)
    return msg.content if msg is not None else ""


def _env_invalid_trajectory(run_index: int, *, raw: str) -> Trajectory:
    """A run where Claude never produced a fair trial (subprocess failed / timed
    out / unparseable). Mirrors the chat-loop PROVIDER_ERROR path so
    is_env_invalid_run masks it out of pass^k."""
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=run_index,
        stop_reason="env_unhealthy",
        parse_failure=ParseFailure(raw=raw[:500], error=PROVIDER_ERROR),
        final_state={"files": {}},
    )


def make_claude_run_fn(
    *,
    model: str,
    surface: str,
    run_subprocess: RunSubprocess,
    workdir_factory: WorkdirFactory,
    max_budget_usd: float = 0.5,
    timeout_s: int = 300,
) -> Callable[[object, int], Trajectory]:
    """Build the per-attempt claude-p driver for one surface. Same signature as
    runners.f_candidate.make_f_run_fn so it plugs into run_f_candidate."""
    system_prompt = claude_system_prompt(surface)

    def run_fn(edit_task, run_index: int) -> Trajectory:
        workdir = workdir_factory()
        try:
            seeded = dict((edit_task.initial_state or {}).get("files", {}))
            materialize_tree(seeded, workdir)
            argv = build_claude_argv(
                model=model,
                surface=surface,
                prompt=_user_prompt(edit_task),
                system_prompt=system_prompt,
                max_budget_usd=max_budget_usd,
            )
            env = _sanitized_env(os.environ)
            try:
                completed = run_subprocess(
                    argv, cwd=str(workdir), env=env, timeout=timeout_s
                )
            except subprocess.TimeoutExpired:
                return _env_invalid_trajectory(run_index, raw="timeout")
            if getattr(completed, "returncode", 0) != 0:
                # stderr is where `claude` writes its real error; keep it for debugging
                # a voided paid run (stdout is usually empty on nonzero exit).
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
            try:
                produced = read_back_tree(workdir)
            except (UnicodeDecodeError, OSError) as exc:
                # A tree we cannot read back is no fair trial (e.g. claude emitted a
                # non-UTF-8 artifact on `natural`). Degrade to env-invalid rather than
                # crashing the whole run — and never errors="replace" (that would
                # corrupt the grading input).
                return _env_invalid_trajectory(
                    run_index, raw=f"read-back failed: {exc}"
                )
            return Trajectory(
                turns=(),
                usage=Usage(
                    prompt_tokens=meta.prompt_tokens,
                    completion_tokens=meta.completion_tokens,
                    latency_s=0.0,
                ),
                run_index=run_index,
                stop_reason="completed_natural",
                final_state={"files": produced},
                rounds=meta.num_turns,
                tool_call_counts={},
                total_cost_usd=meta.total_cost_usd,
            )
        finally:
            # The produced tree is already read into memory above; the temp
            # workdir is no longer needed. Clean it so a 30-attempt run does not
            # leak hundreds of tree copies.
            shutil.rmtree(workdir, ignore_errors=True)

    return run_fn


# ---- Baseline rollup (pure) ---------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class BaselineRow:
    condition_id: str
    base: str  # "f1" / "f2" / "f3"
    k: int  # attempts run for this base (== requested k)
    valid: int  # clean (non env-invalid) attempts
    invalid: int  # env-invalid attempts (subprocess failure/timeout/parse)
    void: bool  # True iff < k clean attempts (D34: never scored over <k)
    pass_hat_k: bool  # not void AND all k clean attempts passed
    pass_at_1: float  # fraction of clean attempts that passed
    cost_usd: float  # Σ total_cost_usd over attempts that recorded one (USD)


def summarize_baseline(
    condition_id: str,
    base_ids: Sequence[str],
    outcomes: Sequence[ReplacementOutcome],
) -> tuple[BaselineRow, ...]:
    """Roll one ReplacementOutcome per base into per-(condition, base) rows.
    Pure. `base_ids` and `outcomes` are positionally paired (strict)."""
    rows = []
    for base, outcome in zip(base_ids, outcomes, strict=True):
        passed = [r.grade.passed for r in outcome.valid_runs]
        n_valid = len(passed)
        n_attempts = len(outcome.attempts)
        # API-equivalent cost over every attempt that reported one; env-invalid
        # attempts carry None (no fair trial, no recorded cost) → counted as 0.
        cost_usd = sum(
            (att.run.trajectory.total_cost_usd or 0.0) for att in outcome.attempts
        )
        rows.append(
            BaselineRow(
                condition_id=condition_id,
                base=base,
                k=n_attempts,
                valid=n_valid,
                invalid=n_attempts - n_valid,
                void=outcome.void,
                pass_hat_k=(not outcome.void) and n_valid > 0 and all(passed),
                pass_at_1=(sum(passed) / n_valid) if n_valid else 0.0,
                cost_usd=cost_usd,
            )
        )
    return tuple(rows)
