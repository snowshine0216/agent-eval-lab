"""Pure world resolution: a task's `available_tools` -> its world binding.

The dataset row is the single source of world truth (item 004 resolved Q1):
tool names resolve by membership in exactly one world's registry. The two
name spaces are disjoint by tested invariant; an unknown name, a cross-world
mix, or an empty tool list refuses to resolve — fail loud, never a silent
default (grill Q4). Resolution itself is pure; the code-world binding carries
the pytest edge's `execute_request` as a value, never invoking it here.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.runners.loop import ApplyFn, Executor
from agent_eval_lab.runners.pytest_edge import execute_request
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
from agent_eval_lab.tools.code_world import apply as code_world_apply
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS, ToolDef
from agent_eval_lab.tools.workspace import apply as workspace_apply


@dataclass(frozen=True, kw_only=True)
class WorldBinding:
    """The frozen (registry, apply_fn, executor) triple (CONTEXT.md term)."""

    registry: Mapping[str, ToolDef]
    apply_fn: ApplyFn
    executor: Executor | None


_WORKSPACE_BINDING = WorldBinding(
    registry=WORKSPACE_TOOLS, apply_fn=workspace_apply, executor=None
)
_CODE_BINDING = WorldBinding(
    registry=CODE_WORLD_TOOLS, apply_fn=code_world_apply, executor=execute_request
)


def resolve_world(available_tools: Sequence[str]) -> WorldBinding:
    """Resolve by tool-name membership; ValueError names every offender."""
    names = tuple(available_tools)
    if not names:
        raise ValueError(
            "cannot resolve world: empty tool list (no shipped dataset has a "
            "tool-less task; refusing to invent semantics — item 004 grill Q4)"
        )
    unknown = tuple(
        name
        for name in names
        if name not in WORKSPACE_TOOLS and name not in CODE_WORLD_TOOLS
    )
    if unknown:
        raise ValueError(f"cannot resolve world: unknown tools {unknown!r}")
    workspace_names = tuple(name for name in names if name in WORKSPACE_TOOLS)
    code_names = tuple(name for name in names if name in CODE_WORLD_TOOLS)
    if workspace_names and code_names:
        raise ValueError(
            "cannot resolve world: cross-world tool mix "
            f"(workspace {workspace_names!r} vs code {code_names!r})"
        )
    return _CODE_BINDING if code_names else _WORKSPACE_BINDING
