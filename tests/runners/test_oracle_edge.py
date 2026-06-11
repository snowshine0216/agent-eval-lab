"""Oracle edge: precompute integration over real sandboxed pytest (ADR-0010/0011)."""

import dataclasses
import json

import pytest

from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    execution_hash,
    grade_execution,
)
from agent_eval_lab.records.serialize import grade_result_to_dict
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.oracle_edge import (
    ExecutionError,
    precompute_execution_verdicts,
)
from agent_eval_lab.tasks.schema import AllOf, ExecutionSpec, TrajectorySpec

ORACLE = {
    "test_oracle_calc.py": (
        "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
}

FIXED_TREE = {"calc.py": "def add(a, b):\n    return a + b\n"}
BROKEN_TREE = {"calc.py": "def add(a, b):\n    return a - b\n"}

SPEC = ExecutionSpec(held_out_tests=ORACLE)


def _trajectory(final_state) -> Trajectory:
    return Trajectory(
        turns=(MessageTurn(role="assistant", content="done"),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def _single_verdict(verification, final_state):
    verdicts = precompute_execution_verdicts(
        verification=verification, trajectory=_trajectory(final_state)
    )
    assert len(verdicts) == 1
    return next(iter(verdicts.values()))


def test_execution_error_is_frozen() -> None:
    error = ExecutionError(kind="harness", detail="boom", execution_hash="h")
    with pytest.raises(dataclasses.FrozenInstanceError):
        error.detail = "other"  # type: ignore[misc]


def test_precompute_returns_empty_map_when_no_execution_specs() -> None:
    verdicts = precompute_execution_verdicts(
        verification=TrajectorySpec(constraints=()),
        trajectory=_trajectory({"files": FIXED_TREE}),
    )
    assert verdicts == {}


def test_precompute_returns_empty_map_when_final_state_is_none() -> None:
    verdicts = precompute_execution_verdicts(
        verification=SPEC, trajectory=_trajectory(None)
    )
    assert verdicts == {}


def test_precompute_keys_the_verdict_by_the_grader_side_hash() -> None:
    verdicts = precompute_execution_verdicts(
        verification=SPEC, trajectory=_trajectory({"files": FIXED_TREE})
    )
    key = execution_hash(SPEC, FIXED_TREE)
    assert sorted(verdicts) == [key]
    assert verdicts[key].execution_hash == key


def test_oracle_pass_yields_passed_verdict() -> None:
    verdict = _single_verdict(SPEC, {"files": FIXED_TREE})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "passed"
    assert verdict.displaced_paths == ()


def test_oracle_fail_yields_failed_verdict() -> None:
    verdict = _single_verdict(SPEC, {"files": BROKEN_TREE})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "failed"
    assert verdict.result.failed == 1


def test_collection_error_yields_error_verdict() -> None:
    spec = ExecutionSpec(
        held_out_tests={
            "test_oracle_app.py": (
                "import missing_dependency\n\n\ndef test_app():\n    assert True\n"
            )
        }
    )
    verdict = _single_verdict(spec, {"files": {"app.py": "x = 1\n"}})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "error"
    assert verdict.result.exit_code == 2


def test_per_spec_timeout_yields_timeout_verdict() -> None:
    spec = ExecutionSpec(
        held_out_tests={
            "test_oracle_slow.py": (
                "from slow import busy\n\n\ndef test_busy():\n    assert busy() == 1\n"
            )
        },
        timeout_s=1.0,
    )
    tree = {
        "slow.py": ("import time\n\n\ndef busy():\n    time.sleep(30)\n    return 1\n")
    }
    verdict = _single_verdict(spec, {"files": tree})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "timeout"


def test_oracle_collecting_nothing_yields_no_tests_verdict() -> None:
    spec = ExecutionSpec(held_out_tests={"test_oracle_empty.py": "HELPER = 1\n"})
    verdict = _single_verdict(spec, {"files": FIXED_TREE})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "no_tests"


def test_displaced_oracle_path_runs_oracle_content() -> None:
    # The agent pre-wrote a trivial suite at the oracle's path over a BROKEN
    # repair: agent-wins would pass; oracle-wins fails — the reward-hack probe.
    tree = {
        **BROKEN_TREE,
        "test_oracle_calc.py": "def test_fake():\n    assert True\n",
    }
    verdict = _single_verdict(SPEC, {"files": tree})
    assert isinstance(verdict, ExecutionVerdict)
    assert verdict.result.status == "failed"
    assert verdict.displaced_paths == ("test_oracle_calc.py",)


def test_tree_collision_yields_structured_execution_error() -> None:
    spec = ExecutionSpec(
        held_out_tests={"tests/test_app.py": "def test_real():\n    assert True\n"}
    )
    tree = {"Tests/test_app.py": "def test_fake():\n    assert True\n"}
    verdict = _single_verdict(spec, {"files": tree})
    assert verdict == ExecutionError(
        kind="tree_collision",
        detail=(
            "canonical-prefix collision: "
            "agent 'Tests/test_app.py' vs oracle 'tests/test_app.py'"
        ),
        execution_hash=execution_hash(spec, tree),
    )


def test_agent_internal_collision_is_captured_as_harness_error() -> None:
    # A hand-authored fixture defect the pure tools would never produce:
    # two agent paths colliding with each other (not with the oracle) reach
    # the materializer's guard; the RuntimeError is captured, never raised.
    tree = {"Lib/a.py": "x = 1\n", "lib/b.py": "y = 2\n"}
    verdict = _single_verdict(SPEC, {"files": tree})
    assert isinstance(verdict, ExecutionError)
    assert verdict.kind == "harness"
    assert "collision" in verdict.detail


def test_all_of_precomputes_every_reachable_execution_spec() -> None:
    other = ExecutionSpec(
        held_out_tests={"test_oracle_other.py": "def test_ok():\n    assert True\n"}
    )
    verification = AllOf(specs=(SPEC, TrajectorySpec(constraints=()), other))
    verdicts = precompute_execution_verdicts(
        verification=verification, trajectory=_trajectory({"files": FIXED_TREE})
    )
    assert sorted(verdicts) == sorted(
        [execution_hash(SPEC, FIXED_TREE), execution_hash(other, FIXED_TREE)]
    )


def test_programming_error_from_edge_propagates_loudly() -> None:
    # Regression: broad `except Exception` silently swallowed TypeError/KeyError
    # (programming bugs). Only (RuntimeError, OSError) — known harness-fault
    # classes — must be captured; everything else must propagate.
    #
    # We inject a TypeError by passing a spec whose held_out_tests is a non-Mapping
    # type that will surface inside run_pytest (materialization) and NOT be a
    # RuntimeError or OSError, so it must escape.
    import unittest.mock as mock

    # Patch run_pytest to raise TypeError (a programming error).
    with mock.patch(
        "agent_eval_lab.runners.oracle_edge.run_pytest",
        side_effect=TypeError("programming bug"),
    ):
        spec = ExecutionSpec(held_out_tests={"test_oracle_calc.py": "def test_x(): pass\n"})
        import pytest as pytest_mod
        with pytest_mod.raises(TypeError, match="programming bug"):
            _single_verdict(spec, {"files": FIXED_TREE})


def test_runtime_error_from_edge_is_captured_as_execution_error() -> None:
    # (RuntimeError, OSError) are known harness-fault classes and must be captured.
    import unittest.mock as mock

    with mock.patch(
        "agent_eval_lab.runners.oracle_edge.run_pytest",
        side_effect=RuntimeError("sandbox invariant violated"),
    ):
        spec = ExecutionSpec(held_out_tests={"test_oracle_calc.py": "def test_x(): pass\n"})
        verdict = _single_verdict(spec, {"files": FIXED_TREE})
        assert isinstance(verdict, ExecutionError)
        assert verdict.kind == "harness"
        assert "sandbox invariant violated" in verdict.detail


def test_malicious_conftest_cannot_subvert_oracle_verdict() -> None:
    # Regression: PYTEST_DISABLE_PLUGIN_AUTOLOAD does not block conftest.py.
    # A conftest.py with a pytest_runtest_makereport hookwrapper forcing
    # outcome="passed" must NOT flip a genuinely failing test to passed.
    malicious_conftest = (
        "import pytest\n\n"
        "@pytest.hookimpl(hookwrapper=True)\n"
        "def pytest_runtest_makereport(item, call):\n"
        "    outcome = yield\n"
        "    rep = outcome.get_result()\n"
        "    rep.outcome = 'passed'\n"
    )
    spec = ExecutionSpec(
        held_out_tests={
            "test_oracle_fail.py": (
                "def test_always_fails():\n    assert False, 'oracle must stay failed'\n"
            )
        }
    )
    tree = {"conftest.py": malicious_conftest}
    verdict = _single_verdict(spec, {"files": tree})
    assert isinstance(verdict, ExecutionVerdict)
    # The oracle test must remain failed — conftest.py is inert with --noconftest.
    assert verdict.result.status == "failed", (
        f"conftest subversion succeeded: status={verdict.result.status!r}"
    )


def test_edge_plus_grader_pipeline_is_byte_identical_across_runs() -> None:
    # MASTER-SPEC hard constraint made executable: same (spec, trajectory)
    # twice through the full pipeline => byte-identical serialized GradeResult.
    def _grade_bytes() -> bytes:
        trajectory = _trajectory({"files": BROKEN_TREE})
        verdicts = precompute_execution_verdicts(
            verification=SPEC, trajectory=trajectory
        )
        grade = grade_execution(spec=SPEC, trajectory=trajectory, verdicts=verdicts)
        return json.dumps(grade_result_to_dict(grade), sort_keys=True).encode()

    assert _grade_bytes() == _grade_bytes()
