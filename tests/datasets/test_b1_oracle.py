"""B-1 readback oracle (§18.7/D24). golden-correct => PASS; each failure mode =>
FAIL (>=1 negative fixture per mode). Golden/mutant fixtures are gitignored
evaluator-only JSON — this test READS them by path and SKIPS when absent (CI has
no golden store), and NEVER inlines a golden value into this tracked file."""

import json
from pathlib import Path

import pytest

from agent_eval_lab.datasets.b1_oracle import build_b1_verification, grade_b1_readback
from agent_eval_lab.runners.mstr_client import ReadbackResult

_GOLDEN_DIR = (
    Path.home()
    / "Documents/Repository/agent-eval-lab/evaluator-only/b-set-golden"
)
_GOLDEN = _GOLDEN_DIR / "b1-golden.json"
_MUTANTS = _GOLDEN_DIR / "b1-mutants.json"

requires_store = pytest.mark.skipif(
    not _GOLDEN.exists() or not _MUTANTS.exists(),
    reason="local b-set golden store required (gitignored evaluator-only)",
)


def _result_from(d: dict) -> ReadbackResult:
    return ReadbackResult(
        exists=d["exists"],
        cube=d["cube"],
        rows=tuple(d["rows"]),
        columns=tuple(d["columns"]),
        prompt=d["prompt"],
        grid=tuple(tuple(row) for row in d["grid"]),
    )


@requires_store
def test_golden_correct_readback_passes() -> None:
    spec = build_b1_verification(_GOLDEN_DIR)
    golden = _result_from(json.loads(_GOLDEN.read_text("utf-8")))
    g = grade_b1_readback(spec, golden)
    assert g.passed is True


@requires_store
def test_missing_object_fails() -> None:
    spec = build_b1_verification(_GOLDEN_DIR)
    golden = json.loads(_GOLDEN.read_text("utf-8"))
    gone = _result_from({**golden, "exists": False})
    assert grade_b1_readback(spec, gone).passed is False


@requires_store
@pytest.mark.parametrize(
    "mode",
    ["wrong_cube", "missing_required_row", "missing_cost_col", "wrong_prompt"],
)
def test_each_failure_mode_fails(mode: str) -> None:
    spec = build_b1_verification(_GOLDEN_DIR)
    mutants = json.loads(_MUTANTS.read_text("utf-8"))
    bad = _result_from(mutants[mode])
    g = grade_b1_readback(spec, bad)
    assert g.passed is False, f"mutant {mode!r} should FAIL but PASSED"
