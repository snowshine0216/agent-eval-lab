"""F-domain candidate-edit runner: the model edits the pinned repo tree, the
held-out node oracle grades the model's REAL trajectory (D-set parity).

Unit tests inject build_tree_fn + run_fn so no provider/network is touched; one
node-graded integration test (gated on node>=20 + the local golden store + repo)
proves a golden-fix trajectory passes end to end.
"""

from pathlib import Path

import pytest

from agent_eval_lab.datasets.f_tasks import build_f_tasks
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.f_candidate import (
    F_EDIT_TOOL_NAMES,
    build_candidate_tree,
    make_edit_task,
    run_f_candidate,
)
from agent_eval_lab.runners.multi_run import ReplacementOutcome
from agent_eval_lab.runners.node_edge import node_supports_junit
from agent_eval_lab.tasks.schema import (
    AllOf,
    NodeExecutionSpec,
    Task,
    TaskInput,
    TaskMetadata,
)

_REPO = Path.home() / "Documents/Repository/web-dossier"
_STORE = (
    Path.home()
    / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"
)
_GF = _STORE / "golden-files"

requires_node = pytest.mark.skipif(
    not node_supports_junit()
    or not (_GF / "Snapshots_SendBackground.spec.js.golden").exists()
    or not _REPO.exists(),
    reason="node>=20 + local web-dossier golden store + repo required",
)


def _fake_task() -> Task:
    return Task(
        id="t1",
        capability="repo_fix",
        input=TaskInput(
            messages=(
                MessageTurn(role="system", content="orig system"),
                MessageTurn(role="user", content="fix the bug in a.js"),
            ),
            available_tools=("bash",),
        ),
        verification=AllOf(
            specs=(
                NodeExecutionSpec(
                    held_out_files={"pkg.json": "{}"}, test_paths=("a.test.js",)
                ),
            )
        ),
        metadata=TaskMetadata(
            split="held_out", version="f-test-v1", provenance="unit test"
        ),
        initial_state={"repo": "x", "candidate_base_sha": "deadbeef"},
    )


def _traj_with_files(files: dict[str, str], *, run_index: int = 0) -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=11, completion_tokens=7, latency_s=1.5),
        run_index=run_index,
        stop_reason="completed_natural",
        final_state={"files": dict(files)},
        rounds=3,
        wall_time_s=1.5,
    )


# ---- make_edit_task -------------------------------------------------------


def test_make_edit_task_seeds_files_and_swaps_in_edit_tools() -> None:
    base = {"a.js": "buggy\n"}
    src = _fake_task()
    edit = make_edit_task(src, base_tree=base)
    assert set(edit.input.available_tools) == set(F_EDIT_TOOL_NAMES)
    assert "bash" not in edit.input.available_tools
    assert edit.initial_state is not None
    assert edit.initial_state["files"] == base
    # verification + identity are preserved (the oracle is untouched)
    assert edit.verification == src.verification
    assert edit.id == src.id


def test_make_edit_task_preserves_user_instruction_and_describes_tools() -> None:
    src = _fake_task()
    edit = make_edit_task(src, base_tree={"a.js": "x\n"})
    system = next(m for m in edit.input.messages if m.role == "system").content
    user = next(m for m in edit.input.messages if m.role == "user").content
    assert "fix the bug in a.js" in user
    for name in F_EDIT_TOOL_NAMES:
        assert name in system


def test_make_edit_task_does_not_mutate_source_or_base_tree() -> None:
    src = _fake_task()
    base = {"a.js": "x\n"}
    make_edit_task(src, base_tree=base)
    assert base == {"a.js": "x\n"}
    assert src.input.available_tools == ("bash",)


# ---- run_f_candidate (stubbed model) --------------------------------------


def test_run_f_candidate_yields_k_runs_per_task_with_real_usage() -> None:
    task = _fake_task()

    def build_tree_fn(_t: Task) -> dict[str, str]:
        return {"a.js": "buggy\n"}

    calls: list[int] = []

    def run_fn(edit_task: Task, run_index: int) -> Trajectory:
        calls.append(run_index)
        # the model "edits" the file; final_state carries the produced tree
        return _traj_with_files({"a.js": "fixed\n"}, run_index=run_index)

    outcomes = list(
        run_f_candidate(
            tasks=(task,),
            k=5,
            condition_id="deepseek:deepseek-v4-pro",
            build_tree_fn=build_tree_fn,
            run_fn=run_fn,
        )
    )
    assert len(outcomes) == 1
    o = outcomes[0]
    assert isinstance(o, ReplacementOutcome)
    assert o.void is False
    assert len(o.valid_runs) == 5  # k independent attempts (env-free -> all valid)
    assert calls == [0, 1, 2, 3, 4]  # one model call per attempt, not 1 graded x5
    # real usage is preserved on every run (not zeroed)
    assert all(r.trajectory.usage.completion_tokens == 7 for r in o.valid_runs)
    assert all(r.condition_id == "deepseek:deepseek-v4-pro" for r in o.valid_runs)
    assert [r.run_index for r in o.valid_runs] == [0, 1, 2, 3, 4]


def test_run_f_candidate_threads_each_tasks_edited_tree_into_its_grade() -> None:
    """The grade must come from the model's produced tree — a per-task stub that
    returns a tree the (stub) verdict marks passing flows through to grade.passed."""
    task = _fake_task()

    def run_fn(edit_task: Task, run_index: int) -> Trajectory:
        # final_state.files present -> precompute_node_verdicts has a tree to grade
        return _traj_with_files(edit_task.initial_state["files"])

    outcomes = list(
        run_f_candidate(
            tasks=(task,),
            k=2,
            condition_id="c",
            build_tree_fn=lambda _t: {"a.js": "x\n"},
            run_fn=run_fn,
        )
    )
    # grading ran (a GradeResult is attached) without raising
    assert all(r.grade is not None for r in outcomes[0].valid_runs)


# ---- build_candidate_tree (integration: real repo at pinned base) ---------


@requires_node
def test_build_candidate_tree_f1_has_target_paths_at_base_sha() -> None:
    [t] = [t for t in build_f_tasks(evaluator_store=_STORE) if t.id == "f-f1"]
    tree = build_candidate_tree(t, repo=_REPO)
    assert (
        "tests/wdio/specs/regression/snapshot/snapshots/"
        "Snapshots_SendBackground.spec.js" in tree
    )
    assert "tests/wdio/pageObjects/common/LibraryNotification.js" in tree


@requires_node
def test_build_candidate_tree_f3_includes_causal_layer_minus_held_out() -> None:
    [t] = [t for t in build_f_tasks(evaluator_store=_STORE) if t.id == "f-f3"]
    tree = build_candidate_tree(t, repo=_REPO)
    fa = "tests/wdio/utils/failure-analysis"
    # the editable source + the causal layer the guard tests import are present
    assert f"{fa}/report-to-allure.js" in tree
    assert f"{fa}/signal.js" in tree
    assert f"{fa}/__tests__/correlate.test.js" in tree
    # the held-out golden grading test is NEVER seeded into the candidate tree
    assert f"{fa}/__tests__/report-to-allure.test.js" not in tree


# ---- end-to-end: a golden-fix trajectory passes the real node oracle ------


@requires_node
def test_run_f_candidate_golden_trajectory_passes_f1() -> None:
    [t] = [t for t in build_f_tasks(evaluator_store=_STORE) if t.id == "f-f1"]
    gspec = (_GF / "Snapshots_SendBackground.spec.js.golden").read_text("utf-8")
    gpage = (_GF / "LibraryNotification.js.golden").read_text("utf-8")

    def run_fn(edit_task: Task, run_index: int) -> Trajectory:
        # stand in for a perfect model: apply the golden fix to the seeded tree
        files = dict(edit_task.initial_state["files"])
        files[
            "tests/wdio/specs/regression/snapshot/snapshots/"
            "Snapshots_SendBackground.spec.js"
        ] = gspec
        files["tests/wdio/pageObjects/common/LibraryNotification.js"] = gpage
        return _traj_with_files(files, run_index=run_index)

    outcomes = list(
        run_f_candidate(
            tasks=(t,),
            k=1,
            condition_id="(golden)",
            build_tree_fn=lambda task: build_candidate_tree(task, repo=_REPO),
            run_fn=run_fn,
        )
    )
    assert outcomes[0].valid_runs[0].grade.passed is True


@requires_node
def test_run_f_candidate_unedited_base_fails_f1() -> None:
    [t] = [t for t in build_f_tasks(evaluator_store=_STORE) if t.id == "f-f1"]

    def run_fn(edit_task: Task, run_index: int) -> Trajectory:
        # model made no useful edit -> base tree -> oracle FAILS
        return _traj_with_files(edit_task.initial_state["files"], run_index=run_index)

    outcomes = list(
        run_f_candidate(
            tasks=(t,),
            k=1,
            condition_id="(noop)",
            build_tree_fn=lambda task: build_candidate_tree(task, repo=_REPO),
            run_fn=run_fn,
        )
    )
    assert outcomes[0].valid_runs[0].grade.passed is False
