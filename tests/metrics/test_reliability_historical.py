"""§D.1 verified blast radius: enforcing the pass^k censor moves ZERO historical
pass^k numbers, because no committed record both graded-passed AND was budget-
capped. This test loads every reports/**/*.jsonl run record and proves it."""

import glob
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _iter_records():
    pattern = str(_REPO_ROOT / "reports/**/*.jsonl")
    for path in sorted(glob.glob(pattern, recursive=True)):
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "grade" not in row or "trajectory" not in row:
                continue
            yield path, row


def test_no_historical_record_is_a_passed_and_capped_run() -> None:
    offenders = [
        (path, row.get("task_id"), row.get("run_index"))
        for path, row in _iter_records()
        if row["grade"].get("passed") and row["trajectory"].get("safety_cap_bound")
    ]
    assert offenders == [], (
        "the pass^k censor would MOVE these historical numbers (passed=True AND "
        f"safety_cap_bound=True): {offenders}"
    )


def test_historical_corpus_is_non_empty() -> None:
    # Guard against a glob that silently matches nothing (which would make the
    # 0-moves assertion vacuously true).
    assert sum(1 for _ in _iter_records()) >= 1000
