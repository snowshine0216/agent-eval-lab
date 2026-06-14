"""B-1 readback oracle (§18.7/D24). golden-correct => PASS; each failure mode =>
FAIL (>=1 negative fixture per mode). Golden/mutant fixtures are gitignored
evaluator-only JSON — this test READS them by path and SKIPS when absent (CI has
no golden store), and NEVER inlines a golden value into this tracked file."""

import json
from pathlib import Path

import pytest

from agent_eval_lab.datasets.b1_oracle import (
    _grid_matches,
    build_b1_verification,
    grade_b1_readback,
)
from agent_eval_lab.runners.mstr_client import ReadbackResult
from agent_eval_lab.tasks.schema import ReadbackSpec

_GOLDEN_DIR = (
    Path.home() / "Documents/Repository/agent-eval-lab/evaluator-only/b-set-golden"
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


# ---------------------------------------------------------------------------
# Order-insensitive grid compare (Finding 2 / pr-review F2)
# ---------------------------------------------------------------------------
# These tests use inline grids (no golden file) so they run on CI too.
# The golden has only 1 data row; we construct 2-row grids inline.

_INLINE_SPEC = ReadbackSpec(
    expected_cube="Query_CharacteristicValue_Mandatory",
    required_rows=("Years Hierarchy", "Region"),
    required_columns=("Cost",),
    expected_prompt="South",
    golden_grid=(
        ("Region", "Cost"),  # header row — positional
        ("North", "100"),
        ("South", "200"),
    ),
)


def _inline_result(grid: tuple) -> ReadbackResult:
    return ReadbackResult(
        exists=True,
        cube="Query_CharacteristicValue_Mandatory",
        rows=("Years Hierarchy", "Region"),
        columns=("Cost",),
        prompt="South",
        grid=grid,
    )


def test_reordered_data_rows_pass() -> None:
    """A correct readback whose data rows arrive in reversed order must PASS.

    This FAILS on the current strict-equality code (pr-review F2 RED) and must
    PASS after _grid_matches is wired in.  Data-row order is non-significant
    (MSTR grid row order is not guaranteed run-to-run; header row is positional).
    """
    reordered_result = _inline_result(
        (
            ("Region", "Cost"),  # header unchanged
            ("South", "200"),  # rows reversed
            ("North", "100"),
        )
    )
    g = grade_b1_readback(_INLINE_SPEC, reordered_result)
    assert g.passed is True, (
        "data rows in different order should PASS but FAILED — "
        "fix: use _grid_matches instead of strict equality"
    )


def test_wrong_value_in_reordered_rows_still_fails() -> None:
    """Even with reordering, a wrong data VALUE must FAIL (discrimination kept)."""
    wrong_value_result = _inline_result(
        (
            ("Region", "Cost"),
            ("South", "999"),  # wrong cost value
            ("North", "100"),
        )
    )
    g = grade_b1_readback(_INLINE_SPEC, wrong_value_result)
    assert g.passed is False, "wrong data value must FAIL even when rows are reordered"


def test_grid_matches_helper_empty_grids() -> None:
    """_grid_matches handles empty/None-like grids symmetrically."""
    assert _grid_matches((), ()) is True
    assert _grid_matches((), (("h",),)) is False
    assert _grid_matches((("h",),), ()) is False


def test_grid_matches_helper_header_order_is_positional() -> None:
    """_grid_matches treats the header row (row 0) as positional — swapped header fails."""
    g1 = (("A", "B"), ("1", "2"))
    g2 = (("B", "A"), ("1", "2"))
    assert _grid_matches(g1, g1) is True
    assert _grid_matches(g1, g2) is False  # header mismatch
