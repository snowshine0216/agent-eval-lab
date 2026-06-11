"""Pure execution-grading core: overlay, hash, collector, grader (no sandbox)."""

import typing

from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    OverlaidTree,
    OverlayCollision,
    collect_execution_specs,
    execution_hash,
    grade_execution,
    overlay_oracle,
)
from agent_eval_lab.records.execution import ExecutionResult, TestCaseResult
from agent_eval_lab.records.grade import FailureCategory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import AllOf, ExecutionSpec, TrajectorySpec

ORACLE = {
    "test_oracle_calc.py": (
        "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
}

TREE = {"calc.py": "def add(a, b):\n    return a + b\n"}

SPEC = ExecutionSpec(held_out_tests=ORACLE)

PASSED_RESULT = ExecutionResult(
    status="passed",
    exit_code=0,
    passed=1,
    failed=0,
    errors=0,
    skipped=0,
    tests=(TestCaseResult(test_id="test_oracle_calc::test_add", status="passed"),),
    stdout="1 passed in <duration>",
    stderr="",
)

FAILED_RESULT = ExecutionResult(
    status="failed",
    exit_code=1,
    passed=0,
    failed=1,
    errors=0,
    skipped=0,
    tests=(TestCaseResult(test_id="test_oracle_calc::test_add", status="failed"),),
    stdout="1 failed in <duration>",
    stderr="",
)


def _trajectory(final_state) -> Trajectory:
    return Trajectory(
        turns=(MessageTurn(role="assistant", content="done"),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def _verdict(result: ExecutionResult, key: str) -> ExecutionVerdict:
    return ExecutionVerdict(result=result, execution_hash=key, displaced_paths=())


# --- overlay (ADR-0010) ---


def test_overlay_combines_disjoint_trees_with_no_displacement() -> None:
    overlaid = overlay_oracle(TREE, ORACLE)
    assert isinstance(overlaid, OverlaidTree)
    assert overlaid.files == {**TREE, **ORACLE}
    assert overlaid.displaced_paths == ()


def test_overlay_oracle_wins_exact_path_collision_and_reports_displacement() -> None:
    agent_tree = {**TREE, "test_oracle_calc.py": "def test_fake():\n    assert True\n"}
    overlaid = overlay_oracle(agent_tree, ORACLE)
    assert isinstance(overlaid, OverlaidTree)
    assert overlaid.files["test_oracle_calc.py"] == ORACLE["test_oracle_calc.py"]
    assert overlaid.displaced_paths == ("test_oracle_calc.py",)


def test_overlay_detects_casefold_prefix_collision() -> None:
    agent_tree = {"Tests/test_app.py": "def test_fake():\n    assert True\n"}
    oracle = {"tests/test_app.py": "def test_real():\n    assert True\n"}
    overlaid = overlay_oracle(agent_tree, oracle)
    assert overlaid == OverlayCollision(
        pairs=(("Tests/test_app.py", "tests/test_app.py"),)
    )


def test_overlay_detects_nfc_normalization_collision() -> None:
    # 'café.py' composed vs 'café.py' decomposed: same NFC form,
    # different spelling -- a collision, not a displacement.
    composed = "café.py"
    decomposed = "café.py"
    overlaid = overlay_oracle({composed: "x = 1\n"}, {decomposed: "x = 2\n"})
    assert isinstance(overlaid, OverlayCollision)
    assert overlaid.pairs == ((composed, decomposed),)


def test_overlay_never_mutates_its_inputs() -> None:
    agent_tree = {"test_oracle_calc.py": "agent\n", "calc.py": "x = 1\n"}
    oracle = dict(ORACLE)
    overlay_oracle(agent_tree, oracle)
    assert agent_tree == {"test_oracle_calc.py": "agent\n", "calc.py": "x = 1\n"}
    assert oracle == ORACLE


# --- execution hash (ADR-0011) ---


def test_execution_hash_is_deterministic() -> None:
    assert execution_hash(SPEC, TREE) == execution_hash(SPEC, TREE)


def test_execution_hash_changes_with_oracle_path_content_tree_and_timeout() -> None:
    base = execution_hash(SPEC, TREE)
    other_path = ExecutionSpec(
        held_out_tests={"test_other.py": ORACLE["test_oracle_calc.py"]}
    )
    other_content = ExecutionSpec(held_out_tests={"test_oracle_calc.py": "changed\n"})
    other_timeout = ExecutionSpec(held_out_tests=ORACLE, timeout_s=10.0)
    assert execution_hash(other_path, TREE) != base
    assert execution_hash(other_content, TREE) != base
    assert execution_hash(SPEC, {**TREE, "extra.py": ""}) != base
    assert execution_hash(other_timeout, TREE) != base


def test_execution_hash_covers_raw_timeout_none_vs_explicit_default() -> None:
    # None and the edge default (10.0) hash apart: dedup is a non-goal.
    explicit = ExecutionSpec(held_out_tests=ORACLE, timeout_s=10.0)
    assert execution_hash(SPEC, TREE) != execution_hash(explicit, TREE)


def test_execution_hash_is_well_defined_when_overlay_would_collide() -> None:
    colliding_tree = {"Test_oracle_calc.py": "agent\n"}
    assert isinstance(overlay_oracle(colliding_tree, ORACLE), OverlayCollision)
    assert execution_hash(SPEC, colliding_tree) == execution_hash(
        SPEC, dict(colliding_tree)
    )


# --- spec collector ---


def test_collect_execution_specs_finds_nested_specs_in_order() -> None:
    other = ExecutionSpec(held_out_tests={"test_b.py": "def test_b():\n    pass\n"})
    tree = AllOf(
        specs=(
            TrajectorySpec(constraints=()),
            AllOf(specs=(SPEC,)),
            other,
        )
    )
    assert collect_execution_specs(tree) == (SPEC, other)


def test_collect_execution_specs_returns_empty_for_non_execution_specs() -> None:
    assert collect_execution_specs(TrajectorySpec(constraints=())) == ()


# --- pure grader ---


def test_grade_execution_passes_when_suite_passed_with_full_evidence() -> None:
    key = execution_hash(SPEC, TREE)
    verdict = ExecutionVerdict(
        result=PASSED_RESULT, execution_hash=key, displaced_paths=("displaced.py",)
    )
    grade = grade_execution(
        spec=SPEC, trajectory=_trajectory({"files": TREE}), verdicts={key: verdict}
    )
    assert grade.grader_id == "execution"
    assert grade.passed is True
    assert grade.score == 1.0
    assert grade.failure_reason is None
    assert grade.evidence == {
        "execution": "run",
        "status": "passed",
        "exit_code": 0,
        "counts": {"passed": 1, "failed": 0, "errors": 0, "skipped": 0},
        "tests": [["test_oracle_calc::test_add", "passed"]],
        "stdout": "1 passed in <duration>",
        "stderr": "",
        "execution_hash": key,
        "displaced_paths": ["displaced.py"],
    }


def test_grade_execution_fails_on_failed_suite_with_no_failure_reason() -> None:
    key = execution_hash(SPEC, TREE)
    grade = grade_execution(
        spec=SPEC,
        trajectory=_trajectory({"files": TREE}),
        verdicts={key: _verdict(FAILED_RESULT, key)},
    )
    assert grade.passed is False
    assert grade.score == 0.0
    assert grade.failure_reason is None
    assert grade.evidence["execution"] == "run"
    assert grade.evidence["status"] == "failed"


def test_grade_execution_missing_final_state_short_circuits_before_lookup() -> None:
    grade = grade_execution(spec=SPEC, trajectory=_trajectory(None), verdicts={})
    assert grade.passed is False
    assert grade.evidence == {"execution": "not_run", "reason": "missing_final_state"}


def test_grade_execution_treats_missing_files_key_as_empty_tree() -> None:
    key = execution_hash(SPEC, {})
    grade = grade_execution(
        spec=SPEC,
        trajectory=_trajectory({"not_files": 1}),
        verdicts={key: _verdict(FAILED_RESULT, key)},
    )
    assert grade.passed is False
    assert grade.evidence["execution"] == "run"


def test_grade_execution_reports_verdict_missing_with_hash() -> None:
    key = execution_hash(SPEC, TREE)
    grade = grade_execution(
        spec=SPEC, trajectory=_trajectory({"files": TREE}), verdicts={}
    )
    assert grade.passed is False
    assert grade.evidence == {
        "execution": "not_run",
        "reason": "verdict_missing",
        "execution_hash": key,
    }


def test_grade_execution_is_total_over_foreign_values_at_the_key() -> None:
    from agent_eval_lab.graders.judge import JudgeVerdict

    key = execution_hash(SPEC, TREE)
    foreign = JudgeVerdict(
        score=5, rationale="r", raw="SCORE: 5", judge_model="m", prompt_hash=key
    )
    grade = grade_execution(
        spec=SPEC, trajectory=_trajectory({"files": TREE}), verdicts={key: foreign}
    )
    assert grade.passed is False
    assert grade.evidence["execution"] == "error"
    assert grade.evidence["execution_error"]["kind"] == "unknown"


def test_failure_category_member_set_is_unchanged() -> None:
    assert typing.get_args(FailureCategory) == (
        "malformed_call",
        "schema_violation",
        "wrong_tool",
        "wrong_args",
        "missing_call",
        "extra_call",
        "order_mismatch",
        "forbidden_action",
        "step_limit_exceeded",
    )


def test_execution_grader_module_imports_nothing_effectful() -> None:
    import agent_eval_lab.graders.execution as execution_mod

    src = open(execution_mod.__file__).read()
    assert "subprocess" not in src
    assert "from agent_eval_lab.runners" not in src
    assert "import agent_eval_lab.runners" not in src
