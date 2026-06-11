"""Hypothesis totality: fc-v1 never raises, always a closed category (crit. 6)."""

from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.reports.classify import RunClassification, classify_run

_CATEGORIES = {"passed", "task_failure", "agent_failure", "harness_failure"}

# Keys and atoms are biased toward the discriminators the table reads, so the
# search space is dense in realistic-but-adversarial evidence shapes — and a
# FOREIGN execution-error kind (grill Q1: "transport", "parse", arbitrary text)
# is generated explicitly alongside the named ones.
_keys = st.sampled_from(
    [
        "execution",
        "status",
        "execution_error",
        "kind",
        "detail",
        "sub_results",
        "grader_id",
        "evidence",
        "counts",
        "reason",
        "x",
    ]
) | st.text(max_size=8)

_atoms = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False)
    | st.text(max_size=12)
    | st.sampled_from(
        [
            "run",
            "not_run",
            "error",
            "passed",
            "failed",
            "timeout",
            "no_tests",
            "harness",
            "tree_collision",
            "verdict_missing",
            "unknown",
            "transport",
            "parse",
        ]
    )
)

_values = st.recursive(
    _atoms,
    lambda children: (
        st.lists(children, max_size=3) | st.dictionaries(_keys, children, max_size=4)
    ),
    max_leaves=16,
)

_evidence = st.dictionaries(_keys, _values, max_size=5)

_grades = st.builds(
    GradeResult,
    grader_id=st.sampled_from(
        ["execution", "all_of", "final_state", "trajectory", "output_match", "?"]
    ),
    passed=st.booleans(),
    score=st.sampled_from([0.0, 1.0]),
    evidence=_evidence,
    failure_reason=st.sampled_from(
        [
            None,
            "malformed_call",
            "schema_violation",
            "wrong_tool",
            "wrong_args",
            "missing_call",
            "extra_call",
            "order_mismatch",
            "forbidden_action",
            "step_limit_exceeded",
        ]
    ),
)

_parse_failures = st.none() | st.builds(
    ParseFailure,
    raw=st.just("{}"),
    error=st.text(max_size=40) | st.just("no choices in provider response"),
)

_trajectories = st.builds(
    Trajectory,
    turns=st.just(()),
    usage=st.just(Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0)),
    run_index=st.just(0),
    stop_reason=st.sampled_from(["completed", "max_steps", "parse_failure"]),
    parse_failure=_parse_failures,
    final_state=st.none() | st.just({"files": {}}),
)

_runs = st.builds(
    RunResult,
    task_id=st.just("t-1"),
    condition_id=st.just("p:m"),
    run_index=st.just(0),
    trajectory=_trajectories,
    grade=_grades,
)


@given(_runs)
def test_classify_run_is_total_and_closed(run: RunResult) -> None:
    classification = classify_run(run)
    assert isinstance(classification, RunClassification)
    assert classification.category in _CATEGORIES
    assert (classification.category == "passed") == (classification.subcategory is None)
    assert classification.classifier_version == "fc-v1"
    assert "\n" not in classification.detail


@given(_runs)
def test_classify_run_is_deterministic(run: RunResult) -> None:
    assert classify_run(run) == classify_run(run)
