"""Schema-first AST tool-call grader (design §6).

Pipeline per observed call:
  1. parse/name-known   -> else malformed_call
  2. validate vs schema -> else schema_violation (NEVER coerced)
Then structural compare (canonicalized) against ExpectedToolCall sequence:
  wrong_tool | wrong_args | missing_call | extra_call | order_mismatch.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from agent_eval_lab.graders.canonicalize import canonicalize
from agent_eval_lab.tasks.grading import FailureCategory, GradeResult
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.jsonschema_mini import validate

_GRADER_ID = "ast_tool_match"


def _fail(reason: FailureCategory, message: str, **evidence: Any) -> GradeResult:
    return GradeResult(
        grader_id=_GRADER_ID,
        passed=False,
        score=0.0,
        evidence={"message": message, **evidence},
        failure_reason=reason,
    )


def _passed() -> GradeResult:
    return GradeResult(
        grader_id=_GRADER_ID, passed=True, score=1.0, evidence={"message": "match"}
    )


def _precheck(
    observed: Sequence[ToolCall], schemas: Mapping[str, Any]
) -> GradeResult | None:
    """Stage 1+2: unknown tool -> malformed_call; bad args -> schema_violation."""
    for call in observed:
        if call.name not in schemas:
            return _fail(
                "malformed_call", f"unknown tool {call.name!r}", tool=call.name
            )
        errors = validate(dict(call.arguments), schemas[call.name])
        if errors:
            return _fail("schema_violation", "; ".join(errors), tool=call.name)
    return None


def _key(call: ToolCall | ExpectedToolCall) -> Any:
    return (call.name, canonicalize(dict(call.arguments)))


def _grade_exact_sequence(
    expected: Sequence[ExpectedToolCall], observed: Sequence[ToolCall]
) -> GradeResult:
    if len(observed) < len(expected):
        return _fail(
            "missing_call", f"expected {len(expected)} calls, saw {len(observed)}"
        )
    if len(observed) > len(expected):
        return _fail(
            "extra_call", f"expected {len(expected)} calls, saw {len(observed)}"
        )
    exp_keys = [_key(e) for e in expected]
    obs_keys = [_key(o) for o in observed]
    if exp_keys == obs_keys:
        return _passed()
    if Counter(obs_keys) == Counter(exp_keys):
        return _fail("order_mismatch", "same calls, wrong order")
    for exp, obs in zip(expected, observed, strict=True):
        if exp.name != obs.name:
            return _fail("wrong_tool", f"expected {exp.name!r}, saw {obs.name!r}")
        if _key(exp) != _key(obs):
            return _fail("wrong_args", f"argument mismatch for {obs.name!r}")
    raise AssertionError("unreachable: ordered keys differ, so the loop must return")


def _grade_multiset(
    expected: Sequence[ExpectedToolCall], observed: Sequence[ToolCall]
) -> GradeResult:
    exp_counts = Counter(_key(e) for e in expected)
    obs_counts = Counter(_key(o) for o in observed)
    if obs_counts == exp_counts:
        return _passed()
    missing = exp_counts - obs_counts
    extra = obs_counts - exp_counts
    if extra and not missing:
        return _fail("extra_call", "unexpected call(s) present")
    expected_names = {e.name for e in expected}
    if any(name not in expected_names for (name, _args) in extra):
        return _fail("wrong_tool", "unexpected tool in multiset")
    return _fail("missing_call", "expected call(s) absent or wrong args")


def grade_tool_calls(
    spec: ToolCallMatchSpec,
    observed: Sequence[ToolCall],
    schemas: Mapping[str, Any],
) -> GradeResult:
    """Grade observed tool calls against the spec via the schema-first pipeline."""
    precheck = _precheck(observed, schemas)
    if precheck is not None:
        return precheck
    if spec.match == "multiset":
        return _grade_multiset(spec.expected_tool_calls, observed)
    return _grade_exact_sequence(spec.expected_tool_calls, observed)
