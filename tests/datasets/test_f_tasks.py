from pathlib import Path

import pytest

from agent_eval_lab.datasets.f_tasks import build_f_task_arms, build_f_tasks
from agent_eval_lab.tasks.schema import AllOf

_STORE = (
    Path.home()
    / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"
)

requires_store = pytest.mark.skipif(
    not (_STORE / "golden-files" / "f1.held_out.test.js").exists(),
    reason="local web-dossier golden store required",
)


def _arm_ids() -> list[str]:
    return [
        f"f-{base}-{arm}"
        for base in ("f1", "f2", "f3")
        for arm in ("bare", "prompt", "feedback", "both")
    ]


@requires_store
def test_build_f_task_arms_returns_twelve_arms_with_suffixed_ids() -> None:
    arms = build_f_task_arms(evaluator_store=_STORE)
    assert sorted(t.id for t in arms) == sorted(_arm_ids())
    assert len(arms) == 12
    for t in arms:
        assert t.capability == "repo_fix"
        assert t.metadata.split == "held_out"
        assert t.initial_state is not None
        assert t.initial_state["candidate_base_sha"].startswith("5b0c13a6")


@requires_store
def test_build_f_tasks_returns_three_node_oracle_tasks() -> None:
    tasks = build_f_tasks(evaluator_store=_STORE)
    assert [t.id for t in tasks] == ["f-f1", "f-f2", "f-f3"]
    for t in tasks:
        assert t.capability == "repo_fix"
        assert isinstance(t.verification, AllOf)  # node-execution AllOf
        assert t.metadata.split == "held_out"
        # the pinned candidate base SHA travels on initial_state (D32)
        assert t.initial_state is not None
        assert t.initial_state["candidate_base_sha"].startswith("5b0c13a6")
        assert t.initial_state["repo"] == "web-dossier"


@requires_store
def test_f_tasks_carry_the_repo_relative_target_paths() -> None:
    tasks = {t.id: t for t in build_f_tasks(evaluator_store=_STORE)}
    assert (
        "Snapshots_SendBackground.spec.js"
        in tasks["f-f1"].initial_state["target_paths"][0]
    )
    assert tasks["f-f2"].initial_state["target_paths"] == ("tests/wdio/wdio.conf.ts",)
