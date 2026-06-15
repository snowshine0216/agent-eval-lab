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
def test_four_arms_of_a_base_share_verification_and_tree_state() -> None:
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    for base in ("f1", "f2", "f3"):
        suffixes = ("bare", "prompt", "feedback", "both")
        group = [arms[f"f-{base}-{s}"] for s in suffixes]
        ref = group[0]
        for t in group[1:]:
            # SAME held-out oracle object (identity, not just equality)
            assert t.verification is ref.verification
            # byte-identical tree-driving state: same repo, base SHA, target paths
            assert t.initial_state["repo"] == ref.initial_state["repo"]
            assert (
                t.initial_state["candidate_base_sha"]
                == ref.initial_state["candidate_base_sha"]
            )
            assert t.initial_state["target_paths"] == ref.initial_state["target_paths"]
            assert t.initial_state["context_paths"] == ref.initial_state["context_paths"]


@requires_store
def test_arms_differ_only_in_factor_flags_and_tools() -> None:
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    # 2x2 factor mapping
    assert arms["f-f1-bare"].initial_state["factor_p"] is False
    assert arms["f-f1-bare"].initial_state["factor_v"] is False
    assert arms["f-f1-prompt"].initial_state["factor_p"] is True
    assert arms["f-f1-prompt"].initial_state["factor_v"] is False
    assert arms["f-f1-feedback"].initial_state["factor_p"] is False
    assert arms["f-f1-feedback"].initial_state["factor_v"] is True
    assert arms["f-f1-both"].initial_state["factor_p"] is True
    assert arms["f-f1-both"].initial_state["factor_v"] is True
    # V arms declare the run_tests tool surface; non-V arms do not
    assert "run_tests" in arms["f-f1-feedback"].input.available_tools
    assert "run_tests" in arms["f-f1-both"].input.available_tools
    assert "run_tests" not in arms["f-f1-bare"].input.available_tools
    assert "run_tests" not in arms["f-f1-prompt"].input.available_tools


@requires_store
def test_each_arm_carries_the_40_round_ablation_override() -> None:
    from agent_eval_lab.runners.round_budget import resolve_max_rounds

    for t in build_f_task_arms(evaluator_store=_STORE):
        assert t.metadata.max_rounds == 40
        # the per-task override path is reachable: it WINS over the F default (20)
        assert resolve_max_rounds(domain="F", task=t) == 40


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


# the concrete context sets enumerated from web-dossier @ 5b0c13a6 (004 §B.5/§C)
_F1_CONTEXT = (
    "tests/wdio/pageObjects/common/Alert.js",
    "tests/wdio/pageObjects/common/SearchBox.js",
    "tests/wdio/pageObjects/common/Panel.js",
)
_F2_CONTEXT = ("tests/wdio/utils/failure-analysis/index.js",)
_F3_CONTEXT: tuple[str, ...] = ()  # F3 layer already broad; no new context paths


@requires_store
def test_arms_carry_the_curated_context_paths() -> None:
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    for arm in ("bare", "prompt", "feedback", "both"):
        assert arms[f"f-f1-{arm}"].initial_state["context_paths"] == _F1_CONTEXT
        assert arms[f"f-f2-{arm}"].initial_state["context_paths"] == _F2_CONTEXT
        assert arms[f"f-f3-{arm}"].initial_state["context_paths"] == _F3_CONTEXT


@requires_store
def test_four_arms_of_a_base_share_context_paths() -> None:
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    for base in ("f1", "f2", "f3"):
        suffixes = ("bare", "prompt", "feedback", "both")
        group = [arms[f"f-{base}-{s}"] for s in suffixes]
        ref = group[0].initial_state["context_paths"]
        for t in group[1:]:
            assert t.initial_state["context_paths"] == ref  # byte-identical


@requires_store
def test_production_f_tasks_carry_no_context_paths() -> None:
    # enrichment is for the ablation arms only; production stays minimal
    for t in build_f_tasks(evaluator_store=_STORE):
        assert "context_paths" not in t.initial_state
