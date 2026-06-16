from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.reports.evidence_summary import EvidenceGap, evidence_gap


def _grade(grader_id, passed, evidence):
    return GradeResult(
        grader_id=grader_id,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence=evidence,
    )


def test_node_execution_failing_tests_and_displaced():
    grade = _grade(
        "node_execution",
        False,
        {
            "execution": "run",
            "status": "failed",
            "counts": {"passed": 1, "failed": 2, "errors": 0, "skipped": 0},
            "tests": [["a", "passed"], ["b", "failed"], ["c", "failed"]],
            "displaced_paths": ["tests/test_app.js"],
        },
    )
    gap = evidence_gap(grade)
    assert gap == EvidenceGap(
        grader_id="node_execution",
        oracle_total=3,
        oracle_passed=1,
        failing_units=("b", "c"),
        displaced_paths=("tests/test_app.js",),
        administrative=False,
        status="failed",
    )


def test_node_execution_passed():
    grade = _grade(
        "node_execution",
        True,
        {
            "execution": "run",
            "status": "passed",
            "tests": [["a", "passed"]],
            "displaced_paths": [],
        },
    )
    gap = evidence_gap(grade)
    assert gap.status == "passed"
    assert gap.oracle_total == 1 and gap.oracle_passed == 1
    assert gap.failing_units == ()


def test_node_execution_not_run_branch_has_no_tests():
    grade = _grade(
        "node_execution",
        False,
        {"execution": "not_run", "reason": "missing_final_state"},
    )
    gap = evidence_gap(grade)
    assert gap.oracle_total is None and gap.oracle_passed is None
    assert gap.failing_units == () and gap.status == "not_executed"


def test_all_of_walks_to_node_execution_leaf():
    grade = _grade(
        "all_of",
        False,
        {
            "sub_results": [
                {
                    "grader_id": "node_execution",
                    "passed": False,
                    "failure_reason": None,
                    "evidence": {
                        "execution": "run",
                        "status": "failed",
                        "tests": [["x", "failed"]],
                        "displaced_paths": [],
                    },
                },
            ]
        },
    )
    gap = evidence_gap(grade)
    assert gap.grader_id == "node_execution"
    assert gap.oracle_total == 1 and gap.failing_units == ("x",)
    assert gap.status == "failed"


def test_fact_key_missing_and_forbidden():
    grade = _grade(
        "fact_key",
        False,
        {
            "level": "L1",
            "required_not_on_page": [],
            "missing_required": ["price"],
            "present_forbidden": ["refund"],
            "page_snapshot_sha256": "abc",
        },
    )
    gap = evidence_gap(grade)
    assert gap.oracle_total is None and gap.oracle_passed is None
    assert gap.failing_units == ("price", "refund")
    assert gap.displaced_paths == () and gap.status == "failed"


def test_fact_key_no_answer_degraded_branch():
    grade = _grade("fact_key", False, {"error": "no assistant message in trajectory"})
    gap = evidence_gap(grade)
    assert gap.status == "no_answer"
    assert gap.failing_units == () and gap.oracle_total is None


def test_administrative_marked_failed_not_executed():
    grade = _grade("node_execution", False, {"marked_failed_not_executed": True})
    gap = evidence_gap(grade)
    assert gap.administrative is True
    assert gap.status == "not_executed"
    assert gap.oracle_total is None and gap.failing_units == ()


def test_unknown_grader_never_raises():
    grade = _grade("some_future_grader", True, {"whatever": 1})
    gap = evidence_gap(grade)
    assert gap.grader_id == "some_future_grader"
    assert gap.status == "passed"
    assert gap.oracle_total is None and gap.failing_units == ()


# ---------------------------------------------------------------------------
# Finding 2 — all_of leaf KeyError when evidence key missing
# ---------------------------------------------------------------------------


def test_all_of_leaf_missing_evidence_does_not_raise():
    """all_of whose node_execution sub_result lacks 'evidence' must not raise KeyError;
    should fall through to _unknown (or graceful gap)."""
    grade = _grade(
        "all_of",
        False,
        {
            "sub_results": [
                {
                    "grader_id": "node_execution",
                    "passed": False,
                    # 'evidence' key is intentionally missing
                }
            ]
        },
    )
    # Must not raise
    gap = evidence_gap(grade)
    # Returns a minimal gap (unknown-style or not_executed)
    assert gap.oracle_total is None
    assert gap.failing_units == ()


def test_all_of_leaf_missing_passed_does_not_raise():
    """all_of whose node_execution sub_result lacks 'passed' must not raise."""
    grade = _grade(
        "all_of",
        False,
        {
            "sub_results": [
                {
                    "grader_id": "node_execution",
                    # 'passed' key is intentionally missing
                    "evidence": {"tests": [["a", "failed"]], "displaced_paths": []},
                }
            ]
        },
    )
    # Must not raise
    gap = evidence_gap(grade)
    # just mustn't raise — any gap is acceptable
    assert gap.oracle_total is not None or gap.oracle_total is None


# ---------------------------------------------------------------------------
# Finding 3 — isinstance(tests, Sequence) accepts str
# ---------------------------------------------------------------------------


def test_node_execution_tests_as_string_does_not_raise():
    """evidence['tests'] = 'error' (a str) must NOT crash the unpack;
    must return status='not_executed' (or unknown) with oracle_total=None."""
    grade = _grade(
        "node_execution",
        False,
        {
            "execution": "run",
            "status": "failed",
            "tests": "error",  # str is a Sequence — the bug
        },
    )
    # Must not raise
    gap = evidence_gap(grade)
    assert gap.oracle_total is None
    assert gap.oracle_passed is None
