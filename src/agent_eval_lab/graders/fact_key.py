"""Pure D-set fact-key grading (§4.2 / D18 / D24).

A deterministic L1-L3 oracle: the candidate's final answer must contain every
required key, must contain no forbidden/contradiction key, and every required
key must also be on the evaluator-frozen page snapshot (the faithfulness gate —
no hallucinating off-page facts). Matching is case-insensitive, whitespace-
normalized, literal substring. No I/O, total.
"""

import re
from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import FactKeySpec

GRADER_ID = "fact_key"
_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace + strip. Pure."""
    return _WS.sub(" ", text).strip().casefold()


def _final_answer(trajectory: Trajectory) -> str | None:
    return next(
        (
            t.content
            for t in reversed(trajectory.turns)
            if isinstance(t, MessageTurn) and t.role == "assistant"
        ),
        None,
    )


def _non_pass(evidence: Mapping[str, Any]) -> GradeResult:
    return GradeResult(
        grader_id=GRADER_ID,
        passed=False,
        score=0.0,
        evidence=evidence,
        failure_reason=None,
    )


def grade_fact_key(*, spec: FactKeySpec, trajectory: Trajectory) -> GradeResult:
    answer = _final_answer(trajectory)
    if answer is None:
        return _non_pass({"error": "no assistant message in trajectory"})

    page = _normalize(spec.page_snapshot)
    ans = _normalize(answer)

    # Faithfulness/authoring gate: every required key must be ON the page.
    required_not_on_page = [k for k in spec.required if _normalize(k) not in page]
    # Required keys the candidate failed to state.
    missing_required = [k for k in spec.required if _normalize(k) not in ans]
    # Forbidden/contradiction keys the candidate stated (hallucination).
    present_forbidden = [k for k in spec.forbidden if _normalize(k) in ans]

    passed = not required_not_on_page and not missing_required and not present_forbidden
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={
            "level": spec.level,
            "required_not_on_page": required_not_on_page,
            "missing_required": missing_required,
            "present_forbidden": present_forbidden,
            "page_snapshot_sha256": spec.page_snapshot_sha256,
        },
        failure_reason=None,
    )
