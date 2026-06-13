import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_eval_lab.datasets.f3_oracle import WDIO_PKG_CONTENT
from agent_eval_lab.graders.node_execution import (
    NodeExecutionVerdict,
    node_execution_hash,
)
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts
from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
from agent_eval_lab.runners.node_edge import node_supports_junit  # noqa: E402

requires_node = pytest.mark.skipif(
    not node_supports_junit(), reason="node >=20 (junit reporter) required"
)
_FA = "tests/wdio/utils/failure-analysis"
_REPO = Path.home() / "Documents/Repository/web-dossier"
_EVAL = Path.home() / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden/golden-files"  # noqa: E501


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _base_tree(report_to_allure_src: str) -> dict[str, str]:
    """A candidate base tree: real failure-analysis dir, with report-to-allure.js
    swapped to the given source. Excludes the golden test (oracle overlays it)."""
    tree = {"tests/wdio/package.json": WDIO_PKG_CONTENT}
    src_dir = _REPO / _FA
    for path in src_dir.rglob("*.js"):
        rel = f"{_FA}/{path.relative_to(src_dir).as_posix()}"
        # exclude the F3 attachment test (oracle supplies the golden one)
        if rel.endswith("__tests__/report-to-allure.test.js"):
            continue
        tree[rel] = _read(path)
    tree[f"{_FA}/report-to-allure.js"] = report_to_allure_src
    return tree


def _f3_allof() -> AllOf:
    golden_test = _read(_EVAL / "report-to-allure.test.js.golden")
    held = {
        "tests/wdio/package.json": WDIO_PKG_CONTENT,
        f"{_FA}/__tests__/report-to-allure.test.js": golden_test,
    }
    f3 = NodeExecutionSpec(
        held_out_files=held,
        test_paths=(f"{_FA}/__tests__/report-to-allure.test.js",),
    )
    causal = NodeExecutionSpec(
        held_out_files={"tests/wdio/package.json": WDIO_PKG_CONTENT},
        test_paths=tuple(
            f"{_FA}/__tests__/{n}"
            for n in ("correlate.test.js", "signal.test.js",
                      "compose.test.js", "index.test.js")
        ),
    )
    return AllOf(specs=(f3, causal))


def _traj(base_tree):
    return Trajectory(
        turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed", final_state={"files": base_tree},
    )


def test_returns_empty_when_no_node_spec() -> None:
    from agent_eval_lab.tasks.schema import OutputMatchSpec
    out = precompute_node_verdicts(
        verification=OutputMatchSpec(expected_output="x"), trajectory=_traj({}))
    assert out == {}


@requires_node
def test_golden_fix_passes_both_specs() -> None:
    allof = _f3_allof()
    golden_src = _read(_EVAL / "report-to-allure.js.golden")
    base = _base_tree(golden_src)
    verdicts = precompute_node_verdicts(verification=allof, trajectory=_traj(base))
    for spec in allof.specs:
        v = verdicts[node_execution_hash(spec, base)]
        assert isinstance(v, NodeExecutionVerdict)
        assert v.result.status == "passed", v.result.stderr


@requires_node
def test_prefix_base_fails_the_f3_spec_but_passes_causal() -> None:
    allof = _f3_allof()
    base_js = subprocess.run(
        ["git", "-C", str(_REPO), "show",
         "5b0c13a6:tests/wdio/utils/failure-analysis/report-to-allure.js"],
        check=True, capture_output=True, text=True,
    ).stdout
    base = _base_tree(base_js)
    verdicts = precompute_node_verdicts(verification=allof, trajectory=_traj(base))
    f3, causal = allof.specs
    assert verdicts[node_execution_hash(f3, base)].result.status == "failed"
    assert verdicts[node_execution_hash(causal, base)].result.status == "passed"


@requires_node
def test_mutant_surfaces_2xx_fails_f3() -> None:
    allof = _f3_allof()
    golden_src = _read(_EVAL / "report-to-allure.js.golden")
    mutant = golden_src.replace("e.status < 200 || e.status >= 300", "e.status >= 600")
    assert mutant != golden_src
    base = _base_tree(mutant)
    verdicts = precompute_node_verdicts(verification=allof, trajectory=_traj(base))
    f3 = allof.specs[0]
    assert verdicts[node_execution_hash(f3, base)].result.status == "failed"


@requires_node
def test_causal_tamper_passes_f3_but_fails_causal_guard() -> None:
    allof = _f3_allof()
    golden_src = _read(_EVAL / "report-to-allure.js.golden")
    base = _base_tree(golden_src)
    tampered = base[f"{_FA}/signal.js"].replace(
        "backend-error-present", "backend-error-BROKEN")
    assert tampered != base[f"{_FA}/signal.js"]
    base[f"{_FA}/signal.js"] = tampered
    verdicts = precompute_node_verdicts(verification=allof, trajectory=_traj(base))
    f3, causal = allof.specs
    assert verdicts[node_execution_hash(f3, base)].result.status == "passed"
    assert verdicts[node_execution_hash(causal, base)].result.status == "failed"
