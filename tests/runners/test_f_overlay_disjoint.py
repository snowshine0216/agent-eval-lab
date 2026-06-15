"""§10.4 overlay-disjointness invariant: every seeded (candidate-visible) path of
an F task must be disjoint under `prefix_collision` from that task's held-out
oracle paths, so enrichment can never turn an arm's runs into tree_collision.

Covers BOTH builders' F tasks (production build_f_tasks + the 12 ablation arms).
For each task we materialize its real seeded tree (build_candidate_tree at the
pinned base SHA) and assert seeded_held_out_disjoint against EACH NodeExecutionSpec
collected from the task's verification.
"""

from pathlib import Path

import pytest

from agent_eval_lab.datasets.f_tasks import build_f_task_arms, build_f_tasks
from agent_eval_lab.graders.node_execution import collect_node_execution_specs
from agent_eval_lab.runners.f_candidate import (
    build_candidate_tree,
    seeded_held_out_disjoint,
)

_REPO = Path.home() / "Documents/Repository/web-dossier"
_STORE = (
    Path.home()
    / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"
)

requires_repo = pytest.mark.skipif(
    not _REPO.exists()
    or not (_STORE / "golden-files" / "f1.held_out.test.js").exists(),
    reason="local web-dossier repo + golden store required",
)


def _all_f_tasks():
    return list(build_f_tasks(evaluator_store=_STORE)) + list(
        build_f_task_arms(evaluator_store=_STORE)
    )


@requires_repo
def test_every_f_task_seeded_paths_disjoint_from_held_out() -> None:
    tasks = _all_f_tasks()
    assert len(tasks) == 3 + 12  # production trio + 12 arms
    for task in tasks:
        tree = build_candidate_tree(task, repo=_REPO)
        seeded = tuple(tree)  # the candidate-visible paths actually seeded
        specs = collect_node_execution_specs(task.verification)
        assert specs, f"{task.id} has no NodeExecutionSpec to check"
        for spec in specs:
            assert seeded_held_out_disjoint(seeded, spec.held_out_files), (
                f"{task.id}: seeded paths collide with held-out "
                f"{sorted(spec.held_out_files)} under prefix_collision"
            )


@requires_repo
def test_f3_held_out_golden_never_in_seeded_tree() -> None:
    # belt-and-suspenders for D19: the F3 golden grading test is never seeded
    from agent_eval_lab.datasets.f3_oracle import F3_TEST_REL

    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    for arm in ("bare", "prompt", "feedback", "both"):
        tree = build_candidate_tree(arms[f"f-f3-{arm}"], repo=_REPO)
        assert F3_TEST_REL not in tree


@requires_repo
def test_f1_arm_tree_carries_the_curated_siblings() -> None:
    # the enrichment actually lands the chosen F1 siblings in the arm tree
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    tree = build_candidate_tree(arms["f-f1-bare"], repo=_REPO)
    assert "tests/wdio/pageObjects/common/Alert.js" in tree
    assert "tests/wdio/pageObjects/common/SearchBox.js" in tree
    assert "tests/wdio/pageObjects/common/Panel.js" in tree
    # the held-out throw-on-timeout golden is NOT seeded
    assert "tests/wdio/f1.held_out.test.js" not in tree


@requires_repo
def test_f2_arm_tree_carries_analyzeFailure_source() -> None:
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    tree = build_candidate_tree(arms["f-f2-bare"], repo=_REPO)
    assert "tests/wdio/utils/failure-analysis/index.js" in tree
    # the two visible tests that ASSERT the signal+confidence split are NOT seeded
    assert (
        "tests/wdio/utils/failure-analysis/__tests__/index.test.js" not in tree
    )
    assert (
        "tests/wdio/utils/failure-analysis/__tests__/compose.test.js" not in tree
    )
