"""AST tool-call grading: schema-first pipeline, never repairs (spec §6).

Pipeline: parse failure -> malformed_call; raw args vs schema ->
schema_violation; canonicalize proven-equivalent forms; structural compare.
Precedence: malformed_call > validation tier (unknown tool -> wrong_tool;
invalid args -> schema_violation) > missing_call/extra_call >
order_mismatch > wrong_tool > wrong_args.
"""

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from agent_eval_lab.graders.canonical import canonicalize
from agent_eval_lab.records.grade import FailureCategory, GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import ToolCall, ToolCallTurn
from agent_eval_lab.tasks.schema import ExpectedToolCall, ToolCallMatchSpec
from agent_eval_lab.tools.validation import validate_args
from agent_eval_lab.tools.workspace import ToolDef

GRADER_ID = "ast_tool_match"

Pair = tuple[str, Any]


def _fail(reason: FailureCategory, evidence: Mapping[str, Any]) -> GradeResult:
    return GradeResult(
        grader_id=GRADER_ID,
        passed=False,
        score=0.0,
        evidence=evidence,
        failure_reason=reason,
    )


def _passed(evidence: Mapping[str, Any]) -> GradeResult:
    return GradeResult(
        grader_id=GRADER_ID,
        passed=True,
        score=1.0,
        evidence=evidence,
        failure_reason=None,
    )


def _pairs(calls: Iterable[ExpectedToolCall | ToolCall]) -> tuple[Pair, ...]:
    return tuple((call.name, canonicalize(call.arguments)) for call in calls)


def _multiset(pairs: tuple[Pair, ...]) -> Counter:
    return Counter((name, json.dumps(args, sort_keys=True)) for name, args in pairs)


def grade_tool_call_match(
    *,
    spec: ToolCallMatchSpec,
    trajectory: Trajectory,
    registry: Mapping[str, ToolDef],
) -> GradeResult:
    if trajectory.parse_failure is not None:
        return _fail(
            "malformed_call",
            {
                "raw": trajectory.parse_failure.raw,
                "error": trajectory.parse_failure.error,
            },
        )
    observed = tuple(
        call
        for turn in trajectory.turns
        if isinstance(turn, ToolCallTurn)
        for call in turn.tool_calls
    )
    expected_pairs = _pairs(spec.expected_tool_calls)
    observed_pairs = _pairs(observed)
    evidence = {"expected": expected_pairs, "observed": observed_pairs}
    for call in observed:
        tool = registry.get(call.name)
        if tool is None:
            return _fail("wrong_tool", {**evidence, "unknown_tool": call.name})
        error = validate_args(tool.parameters, call.arguments)
        if error is not None:
            return _fail(
                "schema_violation",
                {
                    **evidence,
                    "call_id": call.call_id,
                    "tool_name": call.name,
                    "error": error,
                },
            )
    if spec.match == "multiset":
        return _grade_multiset(expected_pairs, observed_pairs, evidence)
    return _grade_sequence(expected_pairs, observed_pairs, evidence)


def _grade_sequence(
    expected: tuple[Pair, ...],
    observed: tuple[Pair, ...],
    evidence: Mapping[str, Any],
) -> GradeResult:
    if observed == expected:
        return _passed(evidence)
    if len(observed) < len(expected):
        return _fail("missing_call", evidence)
    if len(observed) > len(expected):
        return _fail("extra_call", evidence)
    if _multiset(observed) == _multiset(expected):
        return _fail("order_mismatch", evidence)
    position = next(
        i for i, (exp, obs) in enumerate(zip(expected, observed)) if exp != obs
    )
    expected_name = expected[position][0]
    observed_name = observed[position][0]
    reason = "wrong_tool" if expected_name != observed_name else "wrong_args"
    return _fail(reason, {**evidence, "position": position})


def _grade_multiset(
    expected: tuple[Pair, ...],
    observed: tuple[Pair, ...],
    evidence: Mapping[str, Any],
) -> GradeResult:
    if _multiset(observed) == _multiset(expected):
        return _passed(evidence)
    if len(observed) < len(expected):
        return _fail("missing_call", evidence)
    if len(observed) > len(expected):
        return _fail("extra_call", evidence)
    expected_names = Counter(name for name, _ in expected)
    observed_names = Counter(name for name, _ in observed)
    reason = "wrong_args" if expected_names == observed_names else "wrong_tool"
    return _fail(reason, evidence)
