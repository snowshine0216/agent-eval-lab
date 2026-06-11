"""Pure, total fc-v1 failure classification (ADR-0013): derived, never stored.

Maps every graded RunResult to exactly one of passed | task_failure |
agent_failure | harness_failure plus one closed subcategory, reading only the
mechanical discriminators already on the record: the trajectory's
parse_failure and stop_reason, the grade's failure_reason, and the first
execution leg's evidence — the plain dicts the JSONL round-trip yields, never
reconstructed dataclasses (grill Q9). The priority-ordered, first-match-wins
table is frozen with its version: changing any row's semantics mints fc-v2
and re-renders committed runs, never a model re-run.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.records.trajectory import NO_CHOICES_ERROR

CLASSIFIER_VERSION = "fc-v1"

Category = Literal["passed", "task_failure", "agent_failure", "harness_failure"]

# Closed at 15 values (item 004 resolved Q17); versioned with the classifier.
Subcategory = Literal[
    "provider_response",
    "malformed_reply",
    "missing_final_state",
    "sandbox_fault",
    "verdict_missing",
    "tree_collision",
    "foreign_verdict",
    "oracle_empty",
    "forbidden_action",
    "step_limit_exceeded",
    "step_exhaustion",
    "oracle_timeout",
    "oracle_red",
    "oracle_error",
    "other_miss",
]


@dataclass(frozen=True, kw_only=True)
class RunClassification:
    """One run's derived task/agent/harness interpretation (never a grade)."""

    category: Category
    subcategory: Subcategory | None  # None iff category == "passed"
    detail: str  # one-line evidence citation
    classifier_version: str = CLASSIFIER_VERSION


def _one_line(text: object, limit: int = 200) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _classification(
    category: Category, subcategory: Subcategory | None, detail: object
) -> RunClassification:
    return RunClassification(
        category=category, subcategory=subcategory, detail=_one_line(detail)
    )


def first_execution_evidence(
    evidence: Mapping[str, Any], grader_id: object
) -> Mapping[str, Any] | None:
    """The first execution leg's evidence, in declared order (grill Q9).

    Walks the plain dicts the JSONL round-trip yields: the grade's own
    evidence when it is the execution grader's, recursing `sub_results`
    entries (each a {"grader_id", "evidence", ...} dict) for all_of —
    including nested all_of, walked in declared order.
    """
    if grader_id == "execution":
        return evidence
    if grader_id != "all_of":
        return None
    subs = evidence.get("sub_results")
    if not isinstance(subs, Sequence) or isinstance(subs, (str, bytes)):
        return None
    for sub in subs:
        if not isinstance(sub, Mapping):
            continue
        sub_evidence = sub.get("evidence")
        if not isinstance(sub_evidence, Mapping):
            continue
        found = first_execution_evidence(sub_evidence, sub.get("grader_id"))
        if found is not None:
            return found
    return None


def classify_run(run: RunResult) -> RunClassification:
    """fc-v1: priority-ordered, first-match-wins, total — never raises."""
    if run.grade.passed:  # row 1 wins first, even over a recorded parse_failure
        return _classification("passed", None, "grade.passed")
    parse_failure = run.trajectory.parse_failure
    if parse_failure is not None:  # rows 2-3
        return _classify_parse_failure(parse_failure.error)
    exec_ev = first_execution_evidence(run.grade.evidence, run.grade.grader_id)
    early = _classify_execution_evidence(exec_ev)  # rows 4-9
    if early is not None:
        return early
    return _classify_grade_and_budget(run, exec_ev)  # rows 10-16


def _classify_parse_failure(error: str) -> RunClassification:
    if error == NO_CHOICES_ERROR:  # row 2: the provider delivered no completion
        return _classification(
            "harness_failure", "provider_response", f"parse_failure: {error}"
        )
    # row 3: the model emitted an unparseable payload (envelope was well-formed)
    return _classification(
        "agent_failure", "malformed_reply", f"parse_failure: {error}"
    )


_ERROR_KIND_ROWS: Mapping[str, tuple[Category, Subcategory]] = {
    "harness": ("harness_failure", "sandbox_fault"),  # row 5
    "verdict_missing": ("harness_failure", "verdict_missing"),  # row 6
    "tree_collision": ("agent_failure", "tree_collision"),  # row 7
}


def _classify_execution_evidence(
    exec_ev: Mapping[str, Any] | None,
) -> RunClassification | None:
    if exec_ev is None:
        return None
    execution = exec_ev.get("execution")
    if execution == "not_run":  # row 4: the runner always seeds final_state
        return _classification(
            "harness_failure",
            "missing_final_state",
            f"execution=not_run reason={exec_ev.get('reason')!r}",
        )
    if execution == "error":  # rows 5-8
        return _classify_execution_error(exec_ev)
    if execution == "run" and exec_ev.get("status") == "no_tests":  # row 9
        return _classification(
            "task_failure",
            "oracle_empty",
            f"oracle suite status=no_tests counts={exec_ev.get('counts')!r}",
        )
    return None


def _classify_execution_error(exec_ev: Mapping[str, Any]) -> RunClassification:
    error = exec_ev.get("execution_error")
    error_map = error if isinstance(error, Mapping) else {}
    kind = error_map.get("kind")
    # Row 8 closes the branch by construction (grill Q1): the kind is an OPEN
    # string, so any unrecognized (foreign) kind is a verdict-plumbing fault —
    # harness, never an agent miss. Non-string kinds fall through likewise.
    named = _ERROR_KIND_ROWS.get(kind) if isinstance(kind, str) else None
    category, subcategory = (
        named
        if named is not None
        else (
            "harness_failure",
            "foreign_verdict",
        )
    )
    return _classification(
        category,
        subcategory,
        f"execution_error kind={kind!r} detail={error_map.get('detail')!r}",
    )


_SUITE_STATUS_ROWS: Mapping[str, Subcategory] = {
    "timeout": "oracle_timeout",  # row 13
    "failed": "oracle_red",  # row 14
    "error": "oracle_error",  # row 15
}


def _classify_grade_and_budget(
    run: RunResult, exec_ev: Mapping[str, Any] | None
) -> RunClassification:
    reason = run.grade.failure_reason
    if reason == "forbidden_action":  # row 10
        return _classification(
            "agent_failure", "forbidden_action", "failure_reason=forbidden_action"
        )
    if reason == "step_limit_exceeded":  # row 11
        return _classification(
            "agent_failure",
            "step_limit_exceeded",
            "failure_reason=step_limit_exceeded",
        )
    if run.trajectory.stop_reason == "max_steps":  # row 12 outranks rows 13-15
        return _classification(
            "agent_failure", "step_exhaustion", "stop_reason=max_steps"
        )
    if exec_ev is not None and exec_ev.get("execution") == "run":  # rows 13-15
        status = exec_ev.get("status")
        named = _SUITE_STATUS_ROWS.get(status) if isinstance(status, str) else None
        if named is not None:
            return _classification(
                "agent_failure",
                named,
                f"oracle suite status={status} counts={exec_ev.get('counts')!r}",
            )
    return _classification(  # row 16: total without an unknown bucket
        "agent_failure",
        "other_miss",
        "failed with no mapped discriminator "
        f"(grader_id={run.grade.grader_id!r}, "
        f"stop_reason={run.trajectory.stop_reason!r})",
    )
