"""Pure Tier-3 judge core (ADR 0005): no I/O, deterministic, total.

The edge (runners/judge_edge.run_judge) pre-computes a JudgeVerdict per reachable
LlmJudgeSpec and threads an immutable verdict map keyed by `prompt_hash` into the
pure grader, which only reads it. This module imports no http client; importing
it must never reach the network.
"""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.graders.canonical import canonicalize
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.tasks.schema import AllOf, LlmJudgeSpec, VerificationSpec

Message = Mapping[str, str]

PASS_THRESHOLD = 4  # D5: score >= 4 => faithful; coupled to the rubric anchors.


@dataclass(frozen=True, kw_only=True)
class JudgeVerdict:
    score: int
    rationale: str
    raw: str
    judge_model: str
    prompt_hash: str


@dataclass(frozen=True, kw_only=True)
class JudgeParseFailure:
    raw: str
    error: str  # "no_score" | "out_of_range" | "conflicting_scores"


def _render_tool_call(turn: ToolCallTurn) -> str:
    parts = []
    for call in turn.tool_calls:
        args = json.dumps(canonicalize(dict(call.arguments)), sort_keys=True)
        parts.append(f"{call.name}({args})")
    return "\n".join(parts)


def _render_tool_result(turn: ToolResultTurn) -> str:
    if isinstance(turn.outcome, ToolSuccess):
        result_json = json.dumps(canonicalize(turn.outcome.result), sort_keys=True)
        return f"  -> ok:{result_json}"
    return f"  -> error:{turn.outcome.error}"


def render_trajectory_digest(trajectory: Trajectory) -> str:
    """Deterministic, canonical rendering of the trajectory in turn order (D8)."""
    lines: list[str] = []
    for turn in trajectory.turns:
        if isinstance(turn, ToolCallTurn):
            lines.append(_render_tool_call(turn))
        elif isinstance(turn, ToolResultTurn):
            lines.append(_render_tool_result(turn))
        elif isinstance(turn, MessageTurn) and turn.role == "user":
            lines.append(f"USER: {turn.content}")
        elif isinstance(turn, MessageTurn) and turn.role == "assistant":
            lines.append(f"ASSISTANT: {turn.content}")
    return "\n".join(lines)


def build_judge_prompt(
    *, spec: LlmJudgeSpec, trajectory: Trajectory
) -> tuple[Message, ...]:
    lo, hi = spec.scale
    system = (
        "You are a strict evaluator. Read the rubric and the agent trajectory, then "
        f"score the agent's final assistant message on an integer scale {lo}-{hi}. "
        "Reply with a one-paragraph rationale, then a final line exactly of the form "
        "'SCORE: <int>'.\n\n"
        f"RUBRIC (score {lo}-{hi}):\n{spec.rubric}"
    )
    user = "TRAJECTORY:\n" + render_trajectory_digest(trajectory)
    return (
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    )


def prompt_hash(messages: tuple[Message, ...]) -> str:
    blob = json.dumps([dict(m) for m in messages], sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


_SCORE_LINE = re.compile(r"(?mi)^\s*SCORE:\s*([+-]?\d+)\s*$")


def parse_judge_response(
    text: str, scale: tuple[int, int]
) -> "JudgeVerdict | JudgeParseFailure":
    """Parse the judge's text response and return a JudgeVerdict or JudgeParseFailure.

    The SCORE line regex uses (?mi) — MULTILINE + IGNORECASE — so 'score: 4' and
    'SCORE: 4' are both accepted.  This case-insensitive tolerance is deliberate: some
    models emit lowercase, and the rubric contract only requires the integer to be on its
    own line.  Specifically pinned behaviors:
    - 'score: 4' (lowercase) → ACCEPTED (JudgeVerdict)
    - '**SCORE: 4**' (bold markdown) → no_score (asterisks are non-whitespace)
    - 'SCORE: 4.5' (float) → no_score (regex only matches integers)
    - 'SCORE: 4\\nSCORE: 4' (identical duplicates) → single verdict (deduped)
    - 'SCORE: 4\\nSCORE: 2' (conflicting) → conflicting_scores
    """
    lo, hi = scale
    matches = _SCORE_LINE.findall(text)
    if not matches:
        return JudgeParseFailure(raw=text, error="no_score")
    distinct = {int(m) for m in matches}
    if len(distinct) > 1:
        return JudgeParseFailure(raw=text, error="conflicting_scores")
    score = next(iter(distinct))
    if not (lo <= score <= hi):
        return JudgeParseFailure(raw=text, error="out_of_range")
    return JudgeVerdict(
        score=score, rationale=text, raw=text, judge_model="", prompt_hash=""
    )


def grade_llm_judge(
    *,
    spec: LlmJudgeSpec,
    trajectory: Trajectory,
    verdicts: Mapping[str, Any],
) -> GradeResult:
    key = prompt_hash(build_judge_prompt(spec=spec, trajectory=trajectory))
    value = verdicts.get(key)
    if not isinstance(value, JudgeVerdict):
        return _non_pass(key, value)
    passed = value.score >= PASS_THRESHOLD
    return GradeResult(
        grader_id="llm_judge",
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={
            "judge_model": value.judge_model,
            "prompt_hash": value.prompt_hash,
            "score": value.score,
            "scale": [spec.scale[0], spec.scale[1]],
            "threshold": PASS_THRESHOLD,
            "binary_label": "faithful" if passed else "unfaithful",
            "rationale": value.rationale,
            "raw": value.raw,
        },
        failure_reason=None,
    )


def _non_pass(key: str, value: Any) -> GradeResult:
    if value is None:
        evidence: dict[str, Any] = {"judge": "not_run", "prompt_hash": key}
    else:
        # A JudgeError (or any non-verdict) at the key: structured error evidence.
        # The nested "judge_error" dict is the MECHANICAL DISCRIMINATOR between an
        # infra failure (this path) and an agent failure (no "judge_error" key).
        # Callers reading results can do: "judge_error" in evidence to tell them apart.
        evidence = {
            "judge": "error",
            "prompt_hash": key,
            "judge_error": {
                "kind": getattr(value, "kind", "unknown"),
                "detail": getattr(value, "error", repr(value)),
            },
        }
    return GradeResult(
        grader_id="llm_judge",
        passed=False,
        score=0.0,
        evidence=evidence,
        failure_reason=None,
    )


def collect_judge_specs(verification: VerificationSpec) -> tuple[LlmJudgeSpec, ...]:
    """Pure walk of the spec tree (recurses AllOf exactly as grade_all_of does, D1)."""
    if isinstance(verification, LlmJudgeSpec):
        return (verification,)
    if isinstance(verification, AllOf):
        return tuple(
            spec for sub in verification.specs for spec in collect_judge_specs(sub)
        )
    return ()
