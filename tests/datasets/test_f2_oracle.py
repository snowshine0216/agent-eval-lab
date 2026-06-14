import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f2_oracle import F2_CONF_REL, build_f2_verification
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
from agent_eval_lab.runners.node_edge import node_supports_junit  # noqa: E402

_REPO = Path.home() / "Documents/Repository/web-dossier"
_AGENT = Path.home() / "Documents/Repository/agent-eval-lab"
_STORE = _AGENT / "evaluator-only/web-dossier-golden"
_GF = _STORE / "golden-files"
_MUTANTS_FILE = _STORE / "mutants/f2-mutants.json"

requires_node = pytest.mark.skipif(
    not node_supports_junit()
    or not (_GF / "f2.held_out.test.js").exists()
    or not _REPO.exists(),
    reason="node>=20 + local web-dossier golden store + repo required",
)
requires_store = pytest.mark.skipif(
    not (_GF / "f2.held_out.test.js").exists(),
    reason="local web-dossier golden store required",
)


def _show(sha: str, rel: str) -> str:
    return subprocess.run(
        ["git", "-C", str(_REPO), "show", f"{sha}:{rel}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _base(conf: str) -> dict[str, str]:
    return {"tests/wdio/package.json": '{"type":"module"}\n', F2_CONF_REL: conf}


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


def _apply_mutant(conf: str, mutant: dict) -> str:
    """Apply a single mutant spec from evaluator-only JSON; returns mutated conf."""
    if "find_regex" in mutant:
        return re.sub(mutant["find_regex"], mutant["replace"], conf, flags=re.S)
    return conf.replace(mutant["find"], mutant["replace"], 1)


@requires_store
def test_build_f2_does_not_leak_golden_source_into_held_out() -> None:
    v = build_f2_verification(_STORE)
    all_held = {p for spec in v.specs for p in spec.held_out_files}
    assert any(p.endswith("f2.held_out.test.js") for p in all_held)
    assert F2_CONF_REL not in all_held


@requires_node
def test_f2_passes_golden_fails_prefix_and_mutants() -> None:
    v = build_f2_verification(_STORE)
    gconf = (_GF / "wdio.conf.ts.golden").read_text("utf-8")
    pconf = _show("5b0c13a6", F2_CONF_REL)

    assert _grade(v, _base(gconf)) is True  # golden fix PASSES
    assert _grade(v, _base(pconf)) is False  # pre-fix base FAILS

    # Load mutants from evaluator-only (gitignored); no golden answer strings here.
    mutants = json.loads(_MUTANTS_FILE.read_text("utf-8"))
    for m in mutants:
        mut_conf = _apply_mutant(gconf, m)
        assert mut_conf != gconf, f"mutant '{m['name']}' was a no-op"
        assert _grade(v, _base(mut_conf)) is False, (
            f"mutant '{m['name']}' should FAIL but PASSED"
        )
