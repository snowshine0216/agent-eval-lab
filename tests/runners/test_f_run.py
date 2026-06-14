import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f_tasks import build_f_tasks
from agent_eval_lab.runners.f_run import prefix_candidate_tree, run_f
from agent_eval_lab.runners.multi_run import ReplacementOutcome

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
from agent_eval_lab.runners.node_edge import node_supports_junit  # noqa: E402

_REPO = Path.home() / "Documents/Repository/web-dossier"
_STORE = (
    Path.home()
    / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"
)
_GF = _STORE / "golden-files"

requires_node = pytest.mark.skipif(
    not node_supports_junit()
    or not (_GF / "f1.held_out.test.js").exists()
    or not _REPO.exists(),
    reason="node>=20 + local web-dossier golden store + repo required",
)
requires_store = pytest.mark.skipif(
    not (_GF / "f1.held_out.test.js").exists(),
    reason="local web-dossier golden store required",
)


@requires_store
def test_run_f_yields_one_outcome_per_task_with_stubbed_tree() -> None:
    tasks = build_f_tasks(evaluator_store=_STORE)

    # stub tree producer: return an empty tree (no candidate edit) -> grade FAILS,
    # but the loop still yields a well-formed ReplacementOutcome per task.
    def build_tree_fn(task):
        return {"tests/wdio/package.json": '{"type":"module"}\n'}

    outcomes = list(run_f(tasks=tasks, build_tree_fn=build_tree_fn, k=1))
    assert len(outcomes) == len(tasks)
    assert all(isinstance(o, ReplacementOutcome) for o in outcomes)
    # empty candidate tree -> the node oracle cannot pass
    assert all(not o.valid_runs[0].grade.passed for o in outcomes)


@requires_node
def test_run_f_golden_tree_passes_f1() -> None:
    tasks = [t for t in build_f_tasks(evaluator_store=_STORE) if t.id == "f-f1"]
    gspec = (_GF / "Snapshots_SendBackground.spec.js.golden").read_text("utf-8")
    gpage = (_GF / "LibraryNotification.js.golden").read_text("utf-8")

    def build_tree_fn(task):
        tree = prefix_candidate_tree(task, repo=_REPO)  # pinned 5b0c13a6 base
        # apply the golden fix (stands in for the candidate's edit)
        tree[
            "tests/wdio/specs/regression/snapshot/snapshots/"
            "Snapshots_SendBackground.spec.js"
        ] = gspec
        tree["tests/wdio/pageObjects/common/LibraryNotification.js"] = gpage
        return tree

    outcomes = list(run_f(tasks=tasks, build_tree_fn=build_tree_fn, k=1))
    assert outcomes[0].valid_runs[0].grade.passed is True


@requires_node
def test_prefix_candidate_tree_pins_5b0c13a6_not_head() -> None:
    [t] = [t for t in build_f_tasks(evaluator_store=_STORE) if t.id == "f-f2"]
    tree = prefix_candidate_tree(t, repo=_REPO)
    conf = tree["tests/wdio/wdio.conf.ts"]
    # sanity: it is the same bytes git emits for the pinned sha
    expected = subprocess.run(
        ["git", "-C", str(_REPO), "show", "5b0c13a6:tests/wdio/wdio.conf.ts"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert conf == expected
