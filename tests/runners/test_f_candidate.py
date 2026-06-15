"""F-domain candidate-edit runner: the model edits the pinned repo tree, the
held-out node oracle grades the model's REAL trajectory (D-set parity).

Unit tests inject build_tree_fn + run_fn so no provider/network is touched; one
node-graded integration test (gated on node>=20 + the local golden store + repo)
proves a golden-fix trajectory passes end to end.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f_tasks import build_f_task_arms, build_f_tasks
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


def _flagged_task(*, factor_p: bool, factor_v: bool) -> Task:
    base = _fake_task()
    state = {**base.initial_state, "factor_p": factor_p, "factor_v": factor_v}
    if factor_v:
        return replace(
            base,
            input=TaskInput(
                messages=base.input.messages,
                available_tools=("bash", "run_tests"),
            ),
            initial_state=state,
        )
    return replace(base, initial_state=state)


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


def test_factor_p_block_present_only_on_prompt_and_both_arms() -> None:
    from agent_eval_lab.runners.f_candidate import _FACTOR_P_BLOCK

    def sys_of(task: Task) -> str:
        edit = make_edit_task(task, base_tree={"a.js": "x\n"})
        return next(m for m in edit.input.messages if m.role == "system").content

    # P arms: block present
    assert _FACTOR_P_BLOCK in sys_of(_flagged_task(factor_p=True, factor_v=False))
    assert _FACTOR_P_BLOCK in sys_of(_flagged_task(factor_p=True, factor_v=True))
    # non-P arms: block absent, base _EDIT_SYSTEM unmodified
    assert _FACTOR_P_BLOCK not in sys_of(_flagged_task(factor_p=False, factor_v=False))
    assert _FACTOR_P_BLOCK not in sys_of(_flagged_task(factor_p=False, factor_v=True))


def test_factor_p_block_uses_visible_tests_vocabulary() -> None:
    from agent_eval_lab.runners.f_candidate import _FACTOR_P_BLOCK

    assert "visible tests" in _FACTOR_P_BLOCK
    assert "public tests" not in _FACTOR_P_BLOCK


def test_make_edit_task_without_flag_keeps_unmodified_edit_system() -> None:
    # a task with NO factor_p key (e.g. an un-armed task) gets the bare _EDIT_SYSTEM
    from agent_eval_lab.runners.f_candidate import _FACTOR_P_BLOCK

    edit = make_edit_task(_fake_task(), base_tree={"a.js": "x\n"})
    sys = next(m for m in edit.input.messages if m.role == "system").content
    assert _FACTOR_P_BLOCK not in sys


def test_make_edit_task_offers_run_tests_only_on_v_arms() -> None:
    v_edit = make_edit_task(
        _flagged_task(factor_p=False, factor_v=True), base_tree={"a.js": "x\n"}
    )
    non_v_edit = make_edit_task(
        _flagged_task(factor_p=False, factor_v=False), base_tree={"a.js": "x\n"}
    )
    assert "run_tests" in v_edit.input.available_tools
    # edit tools still all present on V arm (run_tests is ADDED, not swapped)
    for name in F_EDIT_TOOL_NAMES:
        assert name in v_edit.input.available_tools
    assert "run_tests" not in non_v_edit.input.available_tools


# ---- build_candidate_tree context_paths enrichment (pure, no repo) --------


def _task_with_context(context_paths: tuple[str, ...]) -> Task:
    base = _fake_task()
    return replace(
        base,
        initial_state={
            "repo": "x",
            "candidate_base_sha": "5b0c13a6bc9e7b9a3c60083da511f3efd0d39505",
            "target_paths": ("src/a.js",),
            "context_paths": context_paths,
        },
    )


def test_build_candidate_tree_seeds_context_paths(monkeypatch) -> None:
    import agent_eval_lab.runners.f_candidate as fc
    import agent_eval_lab.runners.f_run as fr

    # stub the SHA reader used by BOTH the prefix path and the enrichment
    monkeypatch.setattr(fc, "_git_show", lambda repo, rel: f"// {rel}\n")
    monkeypatch.setattr(
        fr.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"stdout": f"// {a[0][-1].split(':')[-1]}\n"})(),
    )
    task = _task_with_context(("sib/One.js", "sib/Two.js"))
    tree = fc.build_candidate_tree(task, repo=Path("/nonexistent"))
    # target path + both context paths are present; pkg.json still seeded
    assert "src/a.js" in tree
    assert tree["sib/One.js"] == "// sib/One.js\n"
    assert tree["sib/Two.js"] == "// sib/Two.js\n"
    assert tree["tests/wdio/package.json"] == '{"type":"module"}\n'


def test_build_candidate_tree_empty_context_paths_is_minimal(monkeypatch) -> None:
    import agent_eval_lab.runners.f_candidate as fc
    import agent_eval_lab.runners.f_run as fr

    monkeypatch.setattr(fc, "_git_show", lambda repo, rel: f"// {rel}\n")
    monkeypatch.setattr(
        fr.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"stdout": "x\n"})(),
    )
    task = _task_with_context(())
    tree = fc.build_candidate_tree(task, repo=Path("/nonexistent"))
    # no context paths -> only target + pkg.json (production-shape)
    assert set(tree) == {"src/a.js", "tests/wdio/package.json"}


def test_build_candidate_tree_missing_context_key_defaults_to_none(monkeypatch) -> None:
    # production build_f_tasks sets NO context_paths key -> must not raise
    import agent_eval_lab.runners.f_candidate as fc
    import agent_eval_lab.runners.f_run as fr

    monkeypatch.setattr(fr, "subprocess", fr.subprocess)
    monkeypatch.setattr(
        fr.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"stdout": "x\n"})(),
    )
    base = _fake_task()
    task = replace(
        base,
        initial_state={
            "repo": "x",
            "candidate_base_sha": "5b0c13a6bc9e7b9a3c60083da511f3efd0d39505",
            "target_paths": ("src/a.js",),
        },
    )
    tree = fc.build_candidate_tree(task, repo=Path("/nonexistent"))
    assert set(tree) == {"src/a.js", "tests/wdio/package.json"}


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


def test_run_f_candidate_masks_provider_error_and_voids_under_k() -> None:
    """A provider HTTP rejection (e.g. 403/429) is env-invalid: excluded from
    valid_runs, flagged invalid in attempts, and if fewer than k clean trials
    result the task is VOID — never scored over <k (D-set parity)."""
    from agent_eval_lab.records.trajectory import PROVIDER_ERROR, ParseFailure

    task = _fake_task()

    def run_fn(edit_task: Task, run_index: int) -> Trajectory:
        if run_index < 3:
            return Trajectory(
                turns=(),
                usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
                run_index=run_index,
                stop_reason="parse_failure",
                parse_failure=ParseFailure(raw="HTTP 403", error=PROVIDER_ERROR),
            )
        return _traj_with_files({"a.js": "fixed\n"}, run_index=run_index)

    [o] = list(
        run_f_candidate(
            tasks=(task,),
            k=5,
            condition_id="c",
            build_tree_fn=lambda _t: {"a.js": "x\n"},
            run_fn=run_fn,
        )
    )
    assert len(o.valid_runs) == 2  # 3 provider errors masked, 2 clean
    assert sum(1 for a in o.attempts if not a.valid) == 3
    assert o.void is True  # only 2 < k=5 clean trials -> INCOMPLETE


def test_run_uid_is_task_scoped(monkeypatch) -> None:
    import httpx

    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig

    captured: list[str] = []

    def fake_run_single(**kwargs):
        captured.append(kwargs["run_uid"])
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(fc, "run_single", fake_run_single)
    cfg = ProviderConfig(
        id="local", base_url="http://x/v1", api_key_env="", model_id="m"
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    run_fn = fc.make_f_run_fn(
        config=cfg,
        http_client=client,
        temperature=0.0,
        max_tokens=64,
        condition_id="deepseek:deepseek-v4-pro",
        safety_cap=200,
        max_rounds=40,
    )
    edit = make_edit_task(
        _flagged_task(factor_p=True, factor_v=False), base_tree={"a.js": "x\n"}
    )
    run_fn(edit, 3)
    # {condition_id}__{task_id}__{run_index:04d} — derive task_id from the arm
    assert captured == [f"deepseek:deepseek-v4-pro__{edit.id}__0003"]
    assert "__f__" not in captured[0]  # the old literal is gone


def test_run_uid_collision_free_across_arms_in_one_condition(monkeypatch) -> None:
    import httpx

    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig

    seen: list[str] = []

    def fake_run_single(**kwargs):
        seen.append(kwargs["run_uid"])
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(fc, "run_single", fake_run_single)
    cfg = ProviderConfig(
        id="local", base_url="http://x/v1", api_key_env="", model_id="m"
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    run_fn = fc.make_f_run_fn(
        config=cfg,
        http_client=client,
        temperature=0.0,
        max_tokens=64,
        condition_id="c",
        safety_cap=200,
        max_rounds=40,
    )
    # simulate the 12 task-arms (3 bases x 4 arms) x k=5 in one condition's space
    arm_ids = [
        f"f-{b}-{a}"
        for b in ("f1", "f2", "f3")
        for a in ("bare", "prompt", "feedback", "both")
    ]
    for aid in arm_ids:
        # a minimal edit-task carrying the arm id; tree/flags irrelevant to the uid
        edit = replace(
            _fake_task(),
            id=aid,
            initial_state={**_fake_task().initial_state, "files": {}},
        )
        for k in range(5):
            run_fn(edit, k)
    assert len(seen) == 60  # 12 arms x k=5
    assert len(set(seen)) == 60  # all distinct -> no collision in the run space


def test_make_f_run_fn_refuses_live_v_arm_until_005(monkeypatch) -> None:
    """A V arm (factor_v=True) declares run_tests but has NO executor in 003.
    Driving it against the live loop must raise, not silently run a no-op V loop."""
    import httpx

    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.runners.config import ProviderConfig

    cfg = ProviderConfig(
        id="local", base_url="http://x/v1", api_key_env="", model_id="m"
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    run_fn = fc.make_f_run_fn(
        config=cfg,
        http_client=client,
        temperature=0.0,
        max_tokens=64,
        condition_id="c",
        safety_cap=200,
        max_rounds=40,
    )
    v_edit = make_edit_task(
        _flagged_task(factor_p=False, factor_v=True), base_tree={"a.js": "x\n"}
    )
    with pytest.raises(NotImplementedError, match="Factor V"):
        run_fn(v_edit, 0)


def test_make_f_run_fn_runs_bare_and_prompt_arms_today(monkeypatch) -> None:
    """bare/prompt (factor_v=False) stay fully runnable in 003."""
    import httpx

    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig

    def fake_run_single(**kwargs):
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(fc, "run_single", fake_run_single)
    cfg = ProviderConfig(
        id="local", base_url="http://x/v1", api_key_env="", model_id="m"
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    run_fn = fc.make_f_run_fn(
        config=cfg,
        http_client=client,
        temperature=0.0,
        max_tokens=64,
        condition_id="c",
        safety_cap=200,
        max_rounds=40,
    )
    for flags in ((False, False), (True, False)):  # bare, prompt
        edit = make_edit_task(
            _flagged_task(factor_p=flags[0], factor_v=flags[1]),
            base_tree={"a.js": "x\n"},
        )
        traj = run_fn(edit, 0)
        assert traj.stop_reason == "completed_natural"


def test_make_f_run_fn_forwards_max_rounds(monkeypatch) -> None:
    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig

    _config = ProviderConfig(
        id="local", base_url="http://localhost:11434/v1", api_key_env="", model_id="m"
    )
    import httpx

    def _noop_handler(r):
        return httpx.Response(200, json={})

    _client = httpx.Client(transport=httpx.MockTransport(_noop_handler))

    captured = {}

    def fake_run_single(**kwargs):
        captured["max_rounds"] = kwargs.get("max_rounds")
        captured["safety_cap"] = kwargs.get("safety_cap")
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(fc, "run_single", fake_run_single)

    run_fn = fc.make_f_run_fn(
        config=_config,
        http_client=_client,
        temperature=0.0,
        max_tokens=4096,
        condition_id="cond__bare",
        safety_cap=200,
        max_rounds=40,
    )
    run_fn(_fake_task(), 0)
    assert captured["max_rounds"] == 40
    assert captured["safety_cap"] == 200


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


@requires_node
def test_build_candidate_tree_armed_f3_routes_to_f3_tree() -> None:
    # Regression for B1: armed F3 ids (f-f3-bare, etc.) must route to
    # _f3_candidate_tree, not fall through to prefix_candidate_tree.
    # Would FAIL before the "or task.id.startswith('f-f3-')" dispatch fix.
    [t] = [t for t in build_f_task_arms(evaluator_store=_STORE) if t.id == "f-f3-bare"]
    tree = build_candidate_tree(t, repo=_REPO)
    fa = "tests/wdio/utils/failure-analysis"
    # same causal-layer assertions as the un-armed F3 test above
    assert f"{fa}/report-to-allure.js" in tree
    assert f"{fa}/signal.js" in tree
    assert f"{fa}/__tests__/correlate.test.js" in tree
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
