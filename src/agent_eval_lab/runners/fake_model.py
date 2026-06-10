"""Deterministic fake model for runner tests + the report CLI smoke.

Replays a per-task script of canonical turns. call_id is derived deterministically
from (task_id, step, index) so the same inputs always yield the same trajectory.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.tasks.tool_calls import ToolCall
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn

_FIXED_USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def _to_turn(task_id: str, step: int, spec: Mapping[str, Any]) -> MessageTurn | ToolCallTurn:
    if spec["type"] == "message":
        return MessageTurn(role="assistant", content=spec["content"])
    call = ToolCall(
        call_id=f"{task_id}-{step}-0",
        name=spec["name"],
        arguments=dict(spec.get("arguments", {})),
    )
    return ToolCallTurn(tool_calls=(call,), content=spec.get("content"))


@dataclass(frozen=True, kw_only=True)
class FakeModel:
    scripts: Mapping[str, Sequence[Mapping[str, Any]]]

    def respond(self, *, task_id: str, step: int) -> MessageTurn | ToolCallTurn:
        return _to_turn(task_id, step, self.scripts[task_id][step])

    def respond_with_usage(
        self, *, task_id: str, step: int
    ) -> tuple[MessageTurn | ToolCallTurn, dict[str, int]]:
        return self.respond(task_id=task_id, step=step), dict(_FIXED_USAGE)

    def num_steps(self, task_id: str) -> int:
        return len(self.scripts[task_id])
