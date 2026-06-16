"""Trajectory-derived edit signals: which paths the agent edited, and which lie
outside the task's declared target_paths (the glossary "out-of-scope edit").

Reads ONLY the Trajectory (the agent's str_replace/write_file tool-call targets)
plus the declared target_paths. DESCRIPTIVE, never a verdict — F has no
OnlyModifies leg, so an out-of-scope edit is reported, never auto-failed. Kept
separate from evidence_summary.py: out-of-scope edit (trajectory) and displaced
path (grade, oracle-overlay collision) are different concepts (CONTEXT.md) on
different records and must not be merged (spec §4).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import ToolCallTurn

# Code-world edit tools (f_candidate.py:56-57). An unknown tool contributes no
# edited path (fail-quiet).
_EDIT_TOOLS = frozenset({"str_replace", "write_file"})


@dataclass(frozen=True, kw_only=True)
class EditPaths:
    edited: tuple[str, ...]
    out_of_scope: tuple[str, ...]


def edit_paths(trajectory: Trajectory, *, target_paths: Sequence[str]) -> EditPaths:
    collected: set[str] = set()
    for turn in trajectory.turns:
        if not isinstance(turn, ToolCallTurn):
            continue
        for call in turn.tool_calls:
            if call.name not in _EDIT_TOOLS:
                continue
            path = call.arguments.get("path")
            if isinstance(path, str):
                collected.add(path)
    edited = tuple(sorted(collected))
    in_scope = set(target_paths)
    out_of_scope = tuple(p for p in edited if p not in in_scope)
    return EditPaths(edited=edited, out_of_scope=out_of_scope)
