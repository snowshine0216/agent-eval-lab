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
from collections.abc import Mapping
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

    Skills are disabled (--disable-slash-commands). Bash is allowed iff natural.
    There is no --max-turns in CLI 2.1.177; rounds are bounded by the subprocess
    timeout (caller), with --max-budget-usd as a secondary cost stop."""
    if surface not in SURFACES:
        raise ValueError(f"unknown surface: {surface!r}")
    allowed = list(_BASE_ALLOWED_TOOLS) + (["Bash"] if surface == "natural" else [])
    denied = list(_ALWAYS_DENIED_TOOLS) + (
        [] if surface == "natural" else ["Bash"]
    )
    return [
        "claude",
        "-p",
        "--model",
        model,
        "--output-format",
        "json",
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
