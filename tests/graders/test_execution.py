"""Pure execution-grading core: overlay, hash, collector, grader (no sandbox)."""

from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    OverlaidTree,
    OverlayCollision,
    execution_hash,
    overlay_oracle,
)
from agent_eval_lab.records.execution import ExecutionResult, TestCaseResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import ExecutionSpec

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
