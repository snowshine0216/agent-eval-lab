from agent_eval_lab.graders.node_execution import (
    NodeExecutionVerdict,
    collect_node_execution_specs,
    grade_node_execution,
    node_execution_hash,
    overlay_node_oracle,
)
from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec


def _spec(**kw):
    base = dict(
        held_out_files={"tests/wdio/package.json": '{"type":"module"}'},
        test_paths=("a.test.js",),
    )
    base.update(kw)
    return NodeExecutionSpec(**base)


def _traj(base_tree):
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state={"files": base_tree},
    )


def test_overlay_is_oracle_wins() -> None:
    base = {"src.js": "candidate", "tests/wdio/package.json": "BASE"}
    held = {"tests/wdio/package.json": '{"type":"module"}', "a.test.js": "T"}
    overlaid = overlay_node_oracle(base, held)
    assert overlaid.files["tests/wdio/package.json"] == '{"type":"module"}'  # oracle
    assert overlaid.files["src.js"] == "candidate"  # candidate source preserved
    assert "tests/wdio/package.json" in overlaid.displaced_paths


def test_hash_is_deterministic_and_input_sensitive() -> None:
    s = _spec()
    h1 = node_execution_hash(s, {"src.js": "v1"})
    h2 = node_execution_hash(s, {"src.js": "v1"})
    h3 = node_execution_hash(s, {"src.js": "v2"})
    assert h1 == h2 and h1 != h3


def test_collect_recurses_all_of() -> None:
    a, b = _spec(test_paths=("a.test.js",)), _spec(test_paths=("b.test.js",))
    assert collect_node_execution_specs(AllOf(specs=(a, b))) == (a, b)


def test_grade_reads_passed_verdict() -> None:
    spec, base = _spec(), {"src.js": "v1"}
    key = node_execution_hash(spec, base)
    verdict = NodeExecutionVerdict(
        result=ExecutionResult(
            status="passed",
            exit_code=0,
            passed=1,
            failed=0,
            errors=0,
            skipped=0,
            tests=(),
            stdout="",
            stderr="",
        ),
        execution_hash=key,
        displaced_paths=(),
    )
    res = grade_node_execution(
        spec=spec, trajectory=_traj(base), verdicts={key: verdict}
    )
    assert res.passed is True and res.score == 1.0


def test_grade_fails_on_failed_verdict() -> None:
    spec, base = _spec(), {"src.js": "v1"}
    key = node_execution_hash(spec, base)
    verdict = NodeExecutionVerdict(
        result=ExecutionResult(
            status="failed",
            exit_code=1,
            passed=33,
            failed=2,
            errors=0,
            skipped=0,
            tests=(),
            stdout="",
            stderr="",
        ),
        execution_hash=key,
        displaced_paths=(),
    )
    res = grade_node_execution(
        spec=spec, trajectory=_traj(base), verdicts={key: verdict}
    )
    assert res.passed is False


def test_grade_non_pass_when_verdict_missing() -> None:
    spec, base = _spec(), {"src.js": "v1"}
    res = grade_node_execution(spec=spec, trajectory=_traj(base), verdicts={})
    assert res.passed is False
    assert res.evidence["execution"] == "error"


# ---- incapable-node / oracle-exec error -> env-invalid (defense-in-depth) ---
# An incapable node (e.g. node < 20 rejects `--test-reporter=junit`: exit 9,
# 'bad option', zero tests) or a NodeExecutionError(kind='harness') means the
# ORACLE could not run — the model's tree never got a fair trial. The grade must
# carry an `env_invalid` marker so such a run is masked from pass^k (D34) rather
# than silently scored 0 as a model FAIL (f-ablation-v2 incident).


def _error_verdict(base, *, exit_code: int, stderr: str) -> NodeExecutionVerdict:
    spec = _spec()
    key = node_execution_hash(spec, base)
    return NodeExecutionVerdict(
        result=ExecutionResult(
            status="error",
            exit_code=exit_code,
            passed=0,
            failed=0,
            errors=0,
            skipped=0,
            tests=(),
            stdout="",
            stderr=stderr,
        ),
        execution_hash=key,
        displaced_paths=(),
    )


def test_grade_marks_incapable_node_env_invalid() -> None:
    spec, base = _spec(), {"src.js": "v1"}
    key = node_execution_hash(spec, base)
    verdict = _error_verdict(
        base, exit_code=9, stderr="node: bad option: --test-reporter=junit"
    )
    res = grade_node_execution(
        spec=spec, trajectory=_traj(base), verdicts={key: verdict}
    )
    assert res.evidence.get("env_invalid") is True
    assert res.evidence.get("env_invalid_reason") == "incapable_node"
    assert res.passed is False


def test_grade_model_import_crash_is_not_env_invalid() -> None:
    # A model that breaks the code under a CAPABLE node yields status='error' with
    # exit_code 1 (load/import crash) — a real FAIL, never env-invalid.
    spec, base = _spec(), {"src.js": "v1"}
    key = node_execution_hash(spec, base)
    verdict = _error_verdict(
        base, exit_code=1, stderr="SyntaxError: Unexpected token in src.js"
    )
    res = grade_node_execution(
        spec=spec, trajectory=_traj(base), verdicts={key: verdict}
    )
    assert res.passed is False
    assert res.evidence.get("env_invalid") is not True


def test_grade_marks_oracle_harness_error_env_invalid() -> None:
    from agent_eval_lab.runners.node_oracle_edge import NodeExecutionError

    spec, base = _spec(), {"src.js": "v1"}
    key = node_execution_hash(spec, base)
    err = NodeExecutionError(
        kind="harness",
        detail="RuntimeError('node binary not found')",
        execution_hash=key,
    )
    res = grade_node_execution(spec=spec, trajectory=_traj(base), verdicts={key: err})
    assert res.evidence.get("env_invalid") is True
    assert res.evidence.get("env_invalid_reason") == "oracle_harness_error"
    assert res.passed is False


def test_grade_tree_collision_is_not_env_invalid() -> None:
    # A tree_collision is the model's produced tree colliding with a held-out
    # oracle path — a model-side fault, NOT an oracle environment error.
    from agent_eval_lab.runners.node_oracle_edge import NodeExecutionError

    spec, base = _spec(), {"src.js": "v1"}
    key = node_execution_hash(spec, base)
    err = NodeExecutionError(
        kind="tree_collision",
        detail="canonical-prefix collision: base 'a' vs oracle 'A'",
        execution_hash=key,
    )
    res = grade_node_execution(spec=spec, trajectory=_traj(base), verdicts={key: err})
    assert res.passed is False
    assert res.evidence.get("env_invalid") is not True
