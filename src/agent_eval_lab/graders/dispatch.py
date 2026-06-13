"""Pure dispatch from VerificationSpec variants to their graders."""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.graders.composite import grade_all_of
from agent_eval_lab.graders.exact_match import grade_exact_match
from agent_eval_lab.graders.execution import grade_execution
from agent_eval_lab.graders.fact_key import grade_fact_key
from agent_eval_lab.graders.judge import grade_llm_judge
from agent_eval_lab.graders.node_execution import grade_node_execution
from agent_eval_lab.graders.policy import grade_trajectory_spec
from agent_eval_lab.graders.state import grade_final_state
from agent_eval_lab.graders.tool_call import grade_tool_call_match
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExecutionSpec,
    FactKeySpec,
    FinalStateSpec,
    LlmJudgeSpec,
    NodeExecutionSpec,
    OutputMatchSpec,
    ToolCallMatchSpec,
    TrajectorySpec,
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
    initial_state: Mapping[str, Any] | None = None,
    verdicts: Mapping[str, Any] | None = None,
) -> GradeResult:
    verdicts = {} if verdicts is None else verdicts
    if isinstance(verification, OutputMatchSpec):
        return grade_output_match(spec=verification, trajectory=trajectory)
    if isinstance(verification, ToolCallMatchSpec):
        return grade_tool_call_match(
            spec=verification, trajectory=trajectory, registry=registry
        )
    if isinstance(verification, FinalStateSpec):
        return grade_final_state(
            spec=verification, initial_state=initial_state, trajectory=trajectory
        )
    if isinstance(verification, TrajectorySpec):
        return grade_trajectory_spec(
            spec=verification, initial_state=initial_state, trajectory=trajectory
        )
    if isinstance(verification, LlmJudgeSpec):
        return grade_llm_judge(
            spec=verification, trajectory=trajectory, verdicts=verdicts
        )
    if isinstance(verification, ExecutionSpec):
        return grade_execution(
            spec=verification, trajectory=trajectory, verdicts=verdicts
        )
    if isinstance(verification, NodeExecutionSpec):
        return grade_node_execution(
            spec=verification, trajectory=trajectory, verdicts=verdicts
        )
    if isinstance(verification, FactKeySpec):
        return grade_fact_key(spec=verification, trajectory=trajectory)
    if isinstance(verification, AllOf):
        return grade_all_of(
            spec=verification,
            initial_state=initial_state,
            trajectory=trajectory,
            registry=registry,
            grade=grade_trajectory,
            verdicts=verdicts,
        )
    raise ValueError(f"unsupported verification spec: {verification!r}")
