import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f3_oracle import (
    F3_SOURCE_REL,
    FAILURE_ANALYSIS_DIR,
    build_f3_verification,
)
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
from agent_eval_lab.runners.node_edge import node_supports_junit  # noqa: E402

requires_node = pytest.mark.skipif(
    not node_supports_junit(), reason="node >=20 (junit reporter) required"
)
_REPO = Path.home() / "Documents/Repository/web-dossier"
_STORE = Path.home() / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"  # noqa: E501


def _candidate_base(report_src: str) -> dict[str, str]:
    tree = {"tests/wdio/package.json": '{"type":"module"}'}
    src_dir = _REPO / FAILURE_ANALYSIS_DIR
    for p in src_dir.rglob("*.js"):
        rel = f"{FAILURE_ANALYSIS_DIR}/{p.relative_to(src_dir).as_posix()}"
        if rel.endswith("__tests__/report-to-allure.test.js"):
            continue  # oracle overlays the golden test; candidate never holds it
        tree[rel] = p.read_text(encoding="utf-8")
    tree[F3_SOURCE_REL] = report_src
    return tree


def _grade(verification, base) -> bool:
    traj = Trajectory(
        turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed", final_state={"files": base})
    verdicts = precompute_node_verdicts(verification=verification, trajectory=traj)
    return grade_trajectory(
        verification=verification, trajectory=traj, registry={}, verdicts=verdicts
    ).passed


def test_build_f3_does_not_leak_golden_source_into_held_out() -> None:
    v = build_f3_verification(_STORE)
    # the held-out files must contain the golden TEST, never the golden SOURCE
    all_held = {p for spec in v.specs for p in spec.held_out_files}
    assert any(p.endswith("__tests__/report-to-allure.test.js") for p in all_held)
    assert F3_SOURCE_REL not in all_held  # oracle never supplies the source under test


@requires_node
def test_f3_passes_golden_fails_base_mutant_and_causal_tamper() -> None:
    v = build_f3_verification(_STORE)
    golden_src = (_STORE / "golden-files/report-to-allure.js.golden").read_text("utf-8")
    base_src = subprocess.run(
        ["git", "-C", str(_REPO), "show",
         "5b0c13a6:tests/wdio/utils/failure-analysis/report-to-allure.js"],
        check=True, capture_output=True, text=True).stdout
    mutant_src = golden_src.replace(
        "e.status < 200 || e.status >= 300", "e.status >= 600"
    )

    assert _grade(v, _candidate_base(golden_src)) is True   # golden fix PASSES
    assert _grade(v, _candidate_base(base_src)) is False    # pre-fix base FAILS
    assert _grade(v, _candidate_base(mutant_src)) is False  # surfaces-2xx mutant FAILS

    tampered = _candidate_base(golden_src)
    sig = f"{FAILURE_ANALYSIS_DIR}/signal.js"
    tampered[sig] = tampered[sig].replace(
        "backend-error-present", "backend-error-BROKEN"
    )
    assert _grade(v, tampered) is False  # causal tamper FAILS (D31 guard)
