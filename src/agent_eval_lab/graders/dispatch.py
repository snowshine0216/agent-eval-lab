"""Pure dispatch from VerificationSpec variants to their graders."""

from collections.abc import Mapping

from agent_eval_lab.graders.exact_match import grade_exact_match
from agent_eval_lab.graders.tool_call import grade_tool_call_match
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import (
    OutputMatchSpec,
    ToolCallMatchSpec,
    VerificationSpec,
)
from agent_eval_lab.tools.workspace import ToolDef


def grade_output_match(*, spec: OutputMatchSpec, trajectory: Trajectory) -> GradeResult:
    if spec.normalizer is not None:
        raise ValueError(f"unsupported normalizer: {spec.normalizer!r}")
    final = next(
        (
            turn
            for turn in reversed(trajectory.turns)
            if isinstance(turn, MessageTurn) and turn.role == "assistant"
        ),
        None,
    )
    if final is None:
        return GradeResult(
            grader_id="output_match",
            passed=False,
            score=0.0,
            evidence={"error": "no assistant message in trajectory"},
            failure_reason=None,
        )
    return grade_exact_match(expected=spec.expected_output, actual=final.content)


def grade_trajectory(
    *,
    verification: VerificationSpec,
    trajectory: Trajectory,
    registry: Mapping[str, ToolDef],
) -> GradeResult:
    if isinstance(verification, OutputMatchSpec):
        return grade_output_match(spec=verification, trajectory=trajectory)
    if isinstance(verification, ToolCallMatchSpec):
        return grade_tool_call_match(
            spec=verification, trajectory=trajectory, registry=registry
        )
    raise ValueError(f"unsupported verification spec: {verification!r}")
