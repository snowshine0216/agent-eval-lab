from agent_eval_lab.graders.fact_key import _normalize, grade_fact_key
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import FactKeySpec

_PAGE = "Kubernetes Cluster   1.34   Reference. Managed Redis 7."


def _answer(text: str) -> Trajectory:
    return Trajectory(
        turns=(
            MessageTurn(role="user", content="q"),
            MessageTurn(role="assistant", content=text),
        ),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed_natural",
    )


def _spec(required, forbidden):
    return FactKeySpec(
        required=required,
        forbidden=forbidden,
        page_snapshot=_PAGE,
        page_snapshot_sha256="x",
        level=1,
    )


def test_normalize_collapses_whitespace_and_casefolds():
    assert _normalize("Managed   Redis\n7") == "managed redis 7"


def test_pass_when_required_present_and_forbidden_absent():
    g = grade_fact_key(
        spec=_spec(required=("1.34",), forbidden=("1.32", "1.33")),
        trajectory=_answer("The recommended Kubernetes version is 1.34."),
    )
    assert g.passed is True
    assert g.score == 1.0


def test_fail_when_required_missing():
    g = grade_fact_key(
        spec=_spec(required=("1.34",), forbidden=()),
        trajectory=_answer("The recommended version is whatever."),
    )
    assert g.passed is False
    assert "1.34" in g.evidence["missing_required"]


def test_fail_when_forbidden_present_hallucination():
    g = grade_fact_key(
        spec=_spec(required=("1.34",), forbidden=("1.32",)),
        trajectory=_answer("The recommended version is 1.32, not 1.34."),
    )
    assert g.passed is False
    assert "1.32" in g.evidence["present_forbidden"]


def test_faithfulness_gate_required_key_absent_from_page_is_authoring_error():
    # A required key the evaluator put in the spec but that is NOT on the page is
    # an authoring fault, surfaced as a non-pass with a clear evidence flag (the
    # grader never silently passes an off-page assertion).
    g = grade_fact_key(
        spec=_spec(required=("9.99",), forbidden=()),
        trajectory=_answer("The version is 9.99."),
    )
    assert g.passed is False
    assert "9.99" in g.evidence["required_not_on_page"]


def test_case_insensitive_and_whitespace_tolerant_match():
    g = grade_fact_key(
        spec=_spec(required=("Managed Redis 7",), forbidden=()),
        trajectory=_answer("strategy manages a   managed redis 7   cluster"),
    )
    assert g.passed is True


def test_no_assistant_message_is_non_pass():
    traj = Trajectory(
        turns=(MessageTurn(role="user", content="q"),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed_natural",
    )
    g = grade_fact_key(spec=_spec(required=("1.34",), forbidden=()), trajectory=traj)
    assert g.passed is False
    assert g.evidence["error"] == "no assistant message in trajectory"
