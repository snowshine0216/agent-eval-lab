import json
from pathlib import Path

import httpx

from agent_eval_lab.cli import _run_f_ablation_command
from agent_eval_lab.experiments.ablation_order import ablation_run_order
from agent_eval_lab.experiments.f_ablation_spec import ABLATION_SEED
from agent_eval_lab.records.trajectory import Trajectory, Usage

# The committed default roster (3 models, F-ablation-v2). Driver reads args.roster.
_ROSTER = Path(__file__).resolve().parents[2] / "f-ablation-roster.toml"
_MODELS = (
    "deepseek:deepseek-v4-pro",
    "minimax:MiniMax-M3",
    "siliconflow:Qwen/Qwen3.6-35B-A3B",
)
# 3 models × 3 bases × 4 arms × k=5 = 180 units (was 240 with the 4-model roster).
_N_UNITS = len(_MODELS) * 3 * 4 * 5


def _fake_traj(run_index: int) -> Trajectory:
    return Trajectory(
        turns=(),
        final_state={"files": {"x.js": "// fake edit"}},
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
        run_index=run_index,
        stop_reason="completed_natural",
    )


class _Args:
    """argparse.Namespace stand-in for the driver."""

    def __init__(self, out: Path, *, dry_run: bool, roster: Path = _ROSTER, arms=None):
        self.out = out
        self.evaluator_config = Path("/nonexistent/evaluator.toml")
        self.roster = roster
        self.temperature = 0.0
        self.max_tokens = 16384
        self.dry_run = dry_run
        self.arms = arms


def _make_recording_factory(calls: list):
    """A run_fn_factory that records every (condition, task_id, run_index) and
    NEVER touches the network — proves the driver makes no real provider call."""

    def factory(*, condition_id: str, **_):
        def run_fn(edit_task, run_index: int) -> Trajectory:
            calls.append((condition_id, edit_task.id, run_index))
            return _fake_traj(run_index)

        return run_fn

    return factory


def test_dry_run_writes_order_and_makes_zero_run_fn_calls(tmp_path, monkeypatch):
    # Avoid the real held-out store / candidate-tree git reads on the dry path.
    calls: list = []
    monkeypatch.setattr(
        "agent_eval_lab.cli._ablation_arm_tasks", lambda store: _stub_arm_tasks()
    )
    rc = _run_f_ablation_command(
        _Args(tmp_path, dry_run=True),
        http_client=None,
        run_fn_factory=_make_recording_factory(calls),
    )
    assert rc == 0
    assert calls == []  # NO run_fn call on the dry path → NO provider call
    sidecars = list(tmp_path.glob("*.realized-order.json"))
    assert len(sidecars) == 1
    payload = json.loads(sidecars[0].read_text())
    # 4 arms × 3 models × 3 bases × 5 reps = 180 units recorded, none executed.
    assert len(payload["realized_order"]) == _N_UNITS == 180
    # the sidecar records the resolved roster identity so the run is auditable.
    assert payload["experiment_id"] == "F-ablation-v2"
    assert payload["spec_hash"]  # non-empty frozen hash
    assert not list(tmp_path.glob("runs-ablation-*-F.jsonl"))  # no run artifacts


def test_real_path_with_fake_run_fn_writes_one_artifact_per_condition(
    tmp_path, monkeypatch
):
    calls: list = []
    monkeypatch.setattr(
        "agent_eval_lab.cli._ablation_arm_tasks", lambda store: _stub_arm_tasks()
    )
    monkeypatch.setattr(
        "agent_eval_lab.cli.build_candidate_tree",
        lambda task, repo: {"x.js": "// base"},
    )
    rc = _run_f_ablation_command(
        _Args(tmp_path, dry_run=False),
        http_client=None,
        run_fn_factory=_make_recording_factory(calls),
    )
    assert rc == 0
    # consumed the WHOLE frozen order: 180 attempts, no provider/network call.
    assert len(calls) == _N_UNITS == 180
    # one artifact per condition (3 conditions), all 12 task-arms inside each.
    artifacts = sorted(tmp_path.glob("runs-ablation-*-F.jsonl"))
    assert len(artifacts) == 3
    for art in artifacts:
        rows = [
            json.loads(line) for line in art.read_text().splitlines() if line.strip()
        ]
        task_ids = {r["task_id"] for r in rows}
        assert len(task_ids) == 12  # all 12 task-arms in this condition's single file
        assert len(rows) == 12 * 5  # 12 arms × k=5
    # the realized-order sidecar records the executed API-call order.
    sidecars = list(tmp_path.glob("*.realized-order.json"))
    assert len(sidecars) == 1
    realized = json.loads(sidecars[0].read_text())["realized_order"]
    assert len(realized) == _N_UNITS


def test_realized_order_matches_the_frozen_pure_order(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agent_eval_lab.cli._ablation_arm_tasks", lambda store: _stub_arm_tasks()
    )
    monkeypatch.setattr(
        "agent_eval_lab.cli.build_candidate_tree",
        lambda task, repo: {"x.js": "// base"},
    )
    _run_f_ablation_command(
        _Args(tmp_path, dry_run=False),
        http_client=None,
        run_fn_factory=_make_recording_factory([]),
    )
    sidecar = next(tmp_path.glob("*.realized-order.json"))
    realized = json.loads(sidecar.read_text())["realized_order"]
    expected = ablation_run_order(
        seed=ABLATION_SEED,
        models=_MODELS,
        base_tasks=("f1", "f2", "f3"),
        k=5,
    )
    assert [(u["model"], u["task_id"], u["repetition"]) for u in realized] == [
        (u.model, u.task_id, u.repetition) for u in expected
    ]


# --- shared stub: 12 arm-tasks with ids matching the dataset builder ----------
def _stub_arm_tasks():
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import (
        AllOf,
        NodeExecutionSpec,
        Task,
        TaskInput,
        TaskMetadata,
    )

    def _arm(base: str, arm: str) -> Task:
        return Task(
            id=f"f-{base}-{arm}",
            capability="repo_fix",
            input=TaskInput(
                messages=(MessageTurn(role="user", content="fix"),),
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
                split="held_out", version="v", provenance="stub", max_rounds=40
            ),
            initial_state={"repo": "x", "candidate_base_sha": "deadbeef"},
        )

    return {
        f"f-{base}-{arm}": _arm(base, arm)
        for base in ("f1", "f2", "f3")
        for arm in ("bare", "prompt", "feedback", "both")
    }


def test_parser_exposes_run_f_ablation_with_dry_run():
    from agent_eval_lab.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(
        [
            "run-f-ablation",
            "--evaluator-config",
            "evaluator.toml",
            "--out",
            "reports",
            "--dry-run",
        ]
    )
    assert args.command == "run-f-ablation"
    assert args.dry_run is True
    assert args.max_tokens == 16384  # F default
    # roster path defaults to the committed file; overridable for add/remove-a-model.
    assert args.roster == Path("f-ablation-roster.toml")
    assert args.arms is None  # default = all four arms


def test_arms_filter_runs_only_selected_arms(tmp_path, monkeypatch):
    """`--arms feedback both` re-runs ONLY the two V arms (the contaminated-V
    recovery path): 2 arms × 3 bases × 5 reps × 3 models = 90 attempts, and every
    executed task_id is a feedback/both arm. The full seeded order is filtered, so
    no skew error despite arm_tasks carrying all 12 ids."""
    calls: list = []
    monkeypatch.setattr(
        "agent_eval_lab.cli._ablation_arm_tasks", lambda store: _stub_arm_tasks()
    )
    monkeypatch.setattr(
        "agent_eval_lab.cli.build_candidate_tree",
        lambda task, repo: {"x.js": "// base"},
    )
    args = _Args(tmp_path, dry_run=False, arms=["feedback", "both"])
    rc = _run_f_ablation_command(
        args, http_client=None, run_fn_factory=_make_recording_factory(calls)
    )
    assert rc == 0
    assert len(calls) == 2 * 3 * 5 * 3 == 90
    assert {c[1].rsplit("-", 1)[1] for c in calls} == {"feedback", "both"}


def test_parser_accepts_arms_filter():
    from agent_eval_lab.cli import _build_parser

    args = _build_parser().parse_args(
        [
            "run-f-ablation",
            "--evaluator-config",
            "evaluator.toml",
            "--arms",
            "feedback",
            "both",
            "--dry-run",
        ]
    )
    assert args.arms == ["feedback", "both"]


def test_parser_accepts_roster_override():
    from agent_eval_lab.cli import _build_parser

    args = _build_parser().parse_args(
        [
            "run-f-ablation",
            "--evaluator-config",
            "evaluator.toml",
            "--roster",
            "/tmp/custom-roster.toml",
            "--dry-run",
        ]
    )
    assert args.roster == Path("/tmp/custom-roster.toml")


def test_dispatch_routes_run_f_ablation(tmp_path, monkeypatch):
    import agent_eval_lab.cli as cli

    seen = {}

    def _spy(args, http_client):
        seen["called"] = True
        return 0

    monkeypatch.setattr(cli, "_run_f_ablation_command", _spy)
    rc = cli.main(
        ["run-f-ablation", "--evaluator-config", "x.toml", "--dry-run"],
        http_client=None,
    )
    assert rc == 0 and seen["called"]


def test_per_arm_pass_pow_k_separates_by_task_id_no_report_change():
    """The arm rides task_id, so pass_pow_k (keyed on task_id) yields one
    reliability per task-arm — 12 here, partitioning into 4 arms × 3 bases. This
    asserts the EXISTING reliability.pass_pow_k contract; it changes nothing."""
    from agent_eval_lab.metrics.reliability import pass_pow_k
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage

    def _run(task_id: str, passed: bool, idx: int) -> RunResult:
        return RunResult(
            task_id=task_id,
            condition_id="prov:m",
            run_index=idx,
            trajectory=Trajectory(
                turns=(),
                usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
                run_index=idx,
                stop_reason="completed_natural",
            ),
            grade=GradeResult(
                grader_id="node_oracle",
                passed=passed,
                score=1.0 if passed else 0.0,
                evidence={},
            ),
        )

    # f1: bare fails, prompt/feedback/both pass (k=2 each, all-pass = reliable).
    runs = []
    for arm, ok in (
        ("bare", False),
        ("prompt", True),
        ("feedback", True),
        ("both", True),
    ):
        for i in range(2):
            runs.append(_run(f"f-f1-{arm}", ok, i))
    # pass_pow_k over the 4 task-arms: 3 of 4 are all-pass → 0.75.
    assert pass_pow_k(runs) == 0.75
    # grouping is by task_id (the arm) — 4 distinct task-arms seen.
    assert len({r.task_id for r in runs}) == 4


def test_transport_error_mid_run_aborts_cleanly_and_preserves_partial_results(
    tmp_path, monkeypatch
):
    """B1: a TransportError mid-loop returns non-zero, completed rows are on disk,
    sidecar exists — no raw traceback, no total loss."""
    calls: list = []
    # Raise on the 6th call so a handful of results are already written first.
    _RAISE_AFTER = 5

    def _raising_factory(*, condition_id: str, **_):
        def run_fn(edit_task, run_index: int) -> Trajectory:
            calls.append((condition_id, edit_task.id, run_index))
            if len(calls) > _RAISE_AFTER:
                raise httpx.TransportError("simulated network failure")
            return _fake_traj(run_index)

        return run_fn

    monkeypatch.setattr(
        "agent_eval_lab.cli._ablation_arm_tasks", lambda store: _stub_arm_tasks()
    )
    monkeypatch.setattr(
        "agent_eval_lab.cli.build_candidate_tree",
        lambda task, repo: {"x.js": "// base"},
    )
    rc = _run_f_ablation_command(
        _Args(tmp_path, dry_run=False),
        http_client=None,
        run_fn_factory=_raising_factory,
    )
    # Driver must return non-zero on abort.
    assert rc != 0
    # The realized-order sidecar must exist (written in finally).
    sidecars = list(tmp_path.glob("*.realized-order.json"))
    assert len(sidecars) == 1
    realized = json.loads(sidecars[0].read_text())["realized_order"]
    # Exactly _RAISE_AFTER units completed before the error.
    assert len(realized) == _RAISE_AFTER
    # At least some JSONL rows must be on disk (streaming, not buffered).
    all_rows = []
    for art in tmp_path.glob("runs-ablation-*-F.jsonl"):
        lines = [ln for ln in art.read_text().splitlines() if ln.strip()]
        all_rows.extend(lines)
    assert len(all_rows) == _RAISE_AFTER, (
        f"expected {_RAISE_AFTER} streamed rows on disk, got {len(all_rows)}"
    )


def test_incapable_node_is_caught_before_any_paid_call(tmp_path, monkeypatch):
    """The held-out oracle needs Node >=20 (--test-reporter=junit). If the
    resolvable node can't run it, the production path must FAIL FAST (rc 1) before
    any provider call rather than silently grading every attempt FAIL — the
    node-v16 incident. The test seam (injected run_fn_factory) is exempt."""
    import agent_eval_lab.cli as cli

    monkeypatch.setattr(cli, "node_supports_junit", lambda: False)
    rc = cli._run_f_ablation_command(
        _Args(tmp_path, dry_run=False),
        http_client=None,
        # run_fn_factory=None → the real production path, which is gated.
    )
    assert rc == 1
    assert not list(tmp_path.glob("runs-ablation-*-F.jsonl")), (
        "no run artifacts may be written when the node oracle is incapable"
    )


def test_task_id_skew_is_caught_before_any_run_fn_call(tmp_path, monkeypatch):
    """B1: if the frozen order references a task_id not in arm_tasks, the driver
    must return 1 with zero run_fn calls (validate before any paid call)."""
    calls: list = []

    # Provide arm_tasks missing one task_id so the skew check triggers.
    def _short_arm_tasks(store):
        full = _stub_arm_tasks()
        # Remove one key so expected_ids != actual_ids.
        full.pop("f-f1-bare")
        return full

    monkeypatch.setattr("agent_eval_lab.cli._ablation_arm_tasks", _short_arm_tasks)
    rc = _run_f_ablation_command(
        _Args(tmp_path, dry_run=False),
        http_client=None,
        run_fn_factory=_make_recording_factory(calls),
    )
    assert rc == 1
    assert calls == [], "run_fn must NOT be called when task_id skew is detected"
