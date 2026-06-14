import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f1_oracle import (
    F1_PAGE_REL,
    F1_SPEC_REL,
    build_f1_verification,
)
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
from agent_eval_lab.runners.node_edge import node_supports_junit  # noqa: E402

_REPO = Path.home() / "Documents/Repository/web-dossier"
_AGENT = Path.home() / "Documents/Repository/agent-eval-lab"
_STORE = _AGENT / "evaluator-only/web-dossier-golden"
_GF = _STORE / "golden-files"
_MUTANTS_FILE = _STORE / "mutants/f1-mutants.json"

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


def _show(sha: str, rel: str) -> str:
    return subprocess.run(
        ["git", "-C", str(_REPO), "show", f"{sha}:{rel}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _base(spec: str, page: str) -> dict[str, str]:
    return {
        "tests/wdio/package.json": '{"type":"module"}\n',
        F1_SPEC_REL: spec,
        F1_PAGE_REL: page,
    }


def _grade(verification, base) -> bool:
    traj = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state={"files": base},
    )
    verdicts = precompute_node_verdicts(verification=verification, trajectory=traj)
    return grade_trajectory(
        verification=verification, trajectory=traj, registry={}, verdicts=verdicts
    ).passed


def _apply_mutant(spec: str, page: str, mutant: dict) -> tuple[str, str]:
    """Apply a single mutant spec from evaluator-only JSON; returns (spec, page)."""
    target = mutant["target"]
    if "find_regex" in mutant:
        pattern = mutant["find_regex"]
        replacement = mutant["replace"]
        if target == "spec":
            result = re.sub(pattern, replacement, spec, flags=re.S)
            return result, page
        else:
            result = re.sub(pattern, replacement, page, flags=re.S)
            return spec, result
    else:
        find = mutant["find"]
        replacement = mutant["replace"]
        if target == "spec":
            return spec.replace(find, replacement, 1), page
        else:
            return spec, page.replace(find, replacement, 1)


@requires_store
def test_build_f1_does_not_leak_golden_source_into_held_out() -> None:
    v = build_f1_verification(_STORE)
    all_held = {p for spec in v.specs for p in spec.held_out_files}
    # the held-out files carry the F1 TEST, never the golden SOURCE under test
    assert any(p.endswith("f1.held_out.test.js") for p in all_held)
    assert F1_SPEC_REL not in all_held
    assert F1_PAGE_REL not in all_held


@requires_node
def test_f1_passes_golden_fails_prefix_and_mutants() -> None:
    v = build_f1_verification(_STORE)
    gspec = (_GF / "Snapshots_SendBackground.spec.js.golden").read_text("utf-8")
    gpage = (_GF / "LibraryNotification.js.golden").read_text("utf-8")
    pspec = _show("5b0c13a6", F1_SPEC_REL)
    ppage = _show("5b0c13a6", F1_PAGE_REL)

    assert _grade(v, _base(gspec, gpage)) is True  # golden fix PASSES
    assert _grade(v, _base(pspec, ppage)) is False  # pre-fix base FAILS

    # Load mutants from evaluator-only (gitignored); no golden answer strings here.
    mutants = json.loads(_MUTANTS_FILE.read_text("utf-8"))
    for m in mutants:
        mut_spec, mut_page = _apply_mutant(gspec, gpage, m)
        # Confirm the mutant actually changed something (sanity-guard).
        assert (mut_spec, mut_page) != (gspec, gpage), (
            f"mutant '{m['name']}' was a no-op"
        )
        assert _grade(v, _base(mut_spec, mut_page)) is False, (
            f"mutant '{m['name']}' should FAIL but PASSED"
        )
