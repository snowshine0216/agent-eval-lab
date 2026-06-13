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
        turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed", final_state={"files": base_tree},
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
        result=ExecutionResult(status="passed", exit_code=0, passed=1, failed=0,
                               errors=0, skipped=0, tests=(), stdout="", stderr=""),
        execution_hash=key, displaced_paths=(),
    )
    res = grade_node_execution(
        spec=spec, trajectory=_traj(base), verdicts={key: verdict}
    )
    assert res.passed is True and res.score == 1.0


def test_grade_fails_on_failed_verdict() -> None:
    spec, base = _spec(), {"src.js": "v1"}
    key = node_execution_hash(spec, base)
    verdict = NodeExecutionVerdict(
        result=ExecutionResult(status="failed", exit_code=1, passed=33, failed=2,
                               errors=0, skipped=0, tests=(), stdout="", stderr=""),
        execution_hash=key, displaced_paths=(),
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
