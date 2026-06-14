"""B-1 readback oracle (§18.7 / D24): build the ReadbackSpec from the evaluator
golden, and grade a ReadbackResult against it. The grader is PURE — it takes the
already-read-back struct (the live readback I/O is the injectable MstrReadbackClient,
performed by the runner) and returns a GradeResult. Three golden-discriminating
checks (see ReadbackSpec). The golden grid is loaded from the gitignored
evaluator-only store, never authored into this tracked source (D19)."""

from __future__ import annotations

import json
from pathlib import Path

from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.runners.mstr_client import ReadbackResult
from agent_eval_lab.tasks.schema import ReadbackSpec

_GOLDEN_REL = "b1-golden.json"


def _grid_matches(
    result_grid: tuple[tuple[str, ...], ...],
    golden_grid: tuple[tuple[str, ...], ...],
) -> bool:
    """Compare two grids: header row is positional; data rows are order-insensitive.

    Data-row order is treated as non-significant (MSTR grid row order is not
    guaranteed run-to-run); the header row (row 0) is positional; grading is
    over row CONTENT.  An empty result_grid matches an empty golden_grid only.
    """
    if not result_grid or not golden_grid:
        return result_grid == golden_grid
    header_ok = result_grid[0] == golden_grid[0]
    data_ok = sorted(result_grid[1:]) == sorted(golden_grid[1:])
    return header_ok and data_ok


def build_b1_verification(golden_dir: Path) -> ReadbackSpec:
    """Read the evaluator-only golden and assemble the B-1 ReadbackSpec. The cube
    name + required rows/cols + prompt come from the golden; the golden grid is
    the held-out executed grid under prompt = South (D19 — read here, never in a
    candidate-visible location)."""
    golden = json.loads((golden_dir / _GOLDEN_REL).read_text(encoding="utf-8"))
    return ReadbackSpec(
        expected_cube=golden["cube"],
        required_rows=tuple(golden["rows"]),
        required_columns=tuple(golden["columns"]),
        expected_prompt=golden["prompt"],
        golden_grid=tuple(tuple(row) for row in golden["grid"]),
    )


def grade_b1_readback(spec: ReadbackSpec, result: ReadbackResult) -> GradeResult:
    """Grade a ReadbackResult against the B-1 ReadbackSpec (PURE, total).

    PASS iff ALL of:
      (1) the captured object exists in the run folder;
      (2) definition matches: cube == expected, rows superset of required_rows,
          columns superset of required_columns, prompt == expected_prompt;
      (3) executed grid == golden grid (under prompt = expected_prompt).
    Any failure => FAIL, with the failing check recorded in evidence."""
    checks: dict[str, bool] = {}
    checks["exists"] = result.exists
    checks["cube"] = result.cube == spec.expected_cube
    checks["rows_superset"] = set(spec.required_rows).issubset(set(result.rows))
    checks["columns_superset"] = set(spec.required_columns).issubset(
        set(result.columns)
    )
    checks["prompt"] = result.prompt == spec.expected_prompt
    checks["grid"] = _grid_matches(result.grid, spec.golden_grid)
    passed = all(checks.values())
    failing = tuple(name for name, ok in checks.items() if not ok)
    return GradeResult(
        grader_id="b1_readback",
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={"checks": checks, "failing": failing},
    )
