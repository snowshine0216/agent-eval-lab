import json
from pathlib import Path

from agent_eval_lab.cli import _run_f_ablation_command
from agent_eval_lab.experiments.ablation_order import ablation_run_order
from agent_eval_lab.experiments.f_ablation_spec import ABLATION_SEED
from agent_eval_lab.records.trajectory import Trajectory, Usage


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

    def __init__(self, out: Path, *, dry_run: bool):
        self.out = out
        self.evaluator_config = Path("/nonexistent/evaluator.toml")
        self.temperature = 0.0
        self.max_tokens = 16384
        self.dry_run = dry_run


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
    order = json.loads(sidecars[0].read_text())["realized_order"]
    # 4 arms × 4 models × 3 bases × 5 reps = 240 units recorded, none executed.
    assert len(order) == 240
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
    # consumed the WHOLE frozen order: 240 attempts, no provider/network call.
    assert len(calls) == 240
    # one artifact per condition (4 conditions), all 12 task-arms inside each.
    artifacts = sorted(tmp_path.glob("runs-ablation-*-F.jsonl"))
    assert len(artifacts) == 4
    for art in artifacts:
        rows = [json.loads(line) for line in art.read_text().splitlines() if line.strip()]
        task_ids = {r["task_id"] for r in rows}
        assert len(task_ids) == 12  # all 12 task-arms in this condition's single file
        assert len(rows) == 12 * 5  # 12 arms × k=5
    # the realized-order sidecar records the executed API-call order.
    sidecars = list(tmp_path.glob("*.realized-order.json"))
    assert len(sidecars) == 1
    realized = json.loads(sidecars[0].read_text())["realized_order"]
    assert len(realized) == 240


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
        models=(
            "deepseek:deepseek-v4-pro",
            "glm:Pro/zai-org/GLM-5.1",
            "minimax:MiniMax-M3",
            "siliconflow:Qwen/Qwen3.6-35B-A3B",
        ),
        base_tasks=("f1", "f2", "f3"),
        k=5,
    )
    assert [
        (u["model"], u["task_id"], u["repetition"]) for u in realized
    ] == [(u.model, u.task_id, u.repetition) for u in expected]


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
