"""Grader-aware gap adapter: one GradeResult -> a small render-ready EvidenceGap.

GRADE-ONLY (spec §5 Q6): reads only the GradeResult — NEVER the VerificationSpec.
That is why D (fact_key) yields oracle_total=None: the denominator lives on the
spec, not the grade. The ONLY place that knows evidence internals, so adding a
new grader is one new branch + its test; an unknown grader degrades gracefully
(never raises). The displaced_paths it carries are the glossary "displaced path"
signal (oracle-overlay collision) — NOT out-of-scope edits (those are
trajectory-derived; see reports/edit_paths.py).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.records.grade import GradeResult


@dataclass(frozen=True, kw_only=True)
class EvidenceGap:
    grader_id: str
    oracle_total: int | None
    oracle_passed: int | None
    failing_units: tuple[str, ...]
    displaced_paths: tuple[str, ...]
    administrative: bool
    status: str


def _unknown(grade: GradeResult) -> EvidenceGap:
    return EvidenceGap(
        grader_id=grade.grader_id,
        oracle_total=None,
        oracle_passed=None,
        failing_units=(),
        displaced_paths=(),
        administrative=False,
        status="passed" if grade.passed else "failed",
    )


def _node_execution(grader_id: str, passed: bool, ev: Mapping[str, Any]) -> EvidenceGap:
    tests = ev.get("tests")
    if not isinstance(tests, (list, tuple)):
        # not_run / error branch: no per-test detail in evidence.
        return EvidenceGap(
            grader_id=grader_id,
            oracle_total=None,
            oracle_passed=None,
            failing_units=(),
            displaced_paths=tuple(ev.get("displaced_paths", ())),
            administrative=False,
            status="not_executed",
        )
    total = len(tests)
    passed_count = sum(1 for _name, st in tests if st == "passed")
    failing = tuple(name for name, st in tests if st != "passed")
    return EvidenceGap(
        grader_id=grader_id,
        oracle_total=total,
        oracle_passed=passed_count,
        failing_units=failing,
        displaced_paths=tuple(ev.get("displaced_paths", ())),
        administrative=False,
        status="passed" if passed else "failed",
    )


def _fact_key(passed: bool, ev: Mapping[str, Any]) -> EvidenceGap:
    if "missing_required" not in ev:
        # degraded: {"error": "no assistant message in trajectory"}
        return EvidenceGap(
            grader_id="fact_key",
            oracle_total=None,
            oracle_passed=None,
            failing_units=(),
            displaced_paths=(),
            administrative=False,
            status="no_answer",
        )
    failing = tuple(ev.get("missing_required", ())) + tuple(
        ev.get("present_forbidden", ())
    )
    return EvidenceGap(
        grader_id="fact_key",
        oracle_total=None,
        oracle_passed=None,
        failing_units=failing,
        displaced_paths=(),
        administrative=False,
        status="passed" if passed else "failed",
    )


def evidence_gap(grade: GradeResult) -> EvidenceGap:
    ev = grade.evidence
    # Administrative override first: an administrative record carries no oracle.
    if bool(ev.get("marked_failed_not_executed", False)):
        return EvidenceGap(
            grader_id=grade.grader_id,
            oracle_total=None,
            oracle_passed=None,
            failing_units=(),
            displaced_paths=(),
            administrative=True,
            status="not_executed",
        )
    if grade.grader_id == "all_of":
        leaf = next(
            (
                sr
                for sr in ev.get("sub_results", ())
                if sr.get("grader_id") == "node_execution"
            ),
            None,
        )
        if leaf is not None:
            leaf_passed = leaf.get("passed")
            leaf_ev = leaf.get("evidence")
            if leaf_passed is None or leaf_ev is None:
                return _unknown(grade)
            return _node_execution("node_execution", leaf_passed, leaf_ev)
        return _unknown(grade)
    if grade.grader_id == "node_execution":
        return _node_execution("node_execution", grade.passed, ev)
    if grade.grader_id == "fact_key":
        return _fact_key(grade.passed, ev)
    return _unknown(grade)
