"""Content-verified ExperimentRunRecord hydration (§18.3).

Reads JSONL artifact files, locates exactly one record by run_uid,
computes SHA256 over canonical bytes, and hard-fails on any anomaly.
Never silently picks a record.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from agent_eval_lab.experiments.schema import ExperimentRunRecord, ExperimentRunRef
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.serialize import run_result_to_dict, trajectory_from_dict

# ---------------------------------------------------------------------------
# Canonical bytes for SHA256 — must match how freeze-spec hashes
# ---------------------------------------------------------------------------

def _canonical_bytes(run: RunResult) -> bytes:
    """Deterministic JSON bytes of a RunResult (sorted keys, no extra whitespace)."""
    d = run_result_to_dict(run)
    return json.dumps(
        d, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def _sha256_hex(run: RunResult) -> str:
    return hashlib.sha256(_canonical_bytes(run)).hexdigest()


# ---------------------------------------------------------------------------
# JSONL parsing
# ---------------------------------------------------------------------------

def _load_run_results_from_jsonl(path: Path) -> list[RunResult]:
    """Parse a JSONL artifact file into RunResult objects."""
    results: list[RunResult] = []
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    for lineno, line in enumerate(raw_lines, start=1):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        g = row["grade"]
        results.append(
            RunResult(
                task_id=row["task_id"],
                condition_id=row["condition_id"],
                run_index=row["run_index"],
                trajectory=trajectory_from_dict(row["trajectory"]),
                grade=GradeResult(
                    grader_id=g["grader_id"],
                    passed=g["passed"],
                    score=g["score"],
                    evidence=g["evidence"],
                    failure_reason=g.get("failure_reason"),
                ),
            )
        )
    return results


# ---------------------------------------------------------------------------
# hydrate_run_record — the public API
# ---------------------------------------------------------------------------

def hydrate_run_record(
    *,
    ref: ExperimentRunRef,
    artifact_paths: Sequence[Path],
) -> ExperimentRunRecord:
    """Locate, verify, and return an ExperimentRunRecord.

    Args:
        ref: The pre-registered reference (run_uid + expected SHA256).
        artifact_paths: JSONL files to search for the record.

    Returns:
        ExperimentRunRecord with ref and the verified RunResult.

    Raises:
        LookupError: if zero or more than one record matches run_uid.
        ValueError: if SHA256 of the found record does not match ref.artifact_sha256.
    """
    matches: list[RunResult] = []

    for path in artifact_paths:
        for run in _load_run_results_from_jsonl(path):
            if run.trajectory.run_uid == ref.run_uid:
                matches.append(run)

    if len(matches) == 0:
        raise LookupError(
            f"No record found for run_uid={ref.run_uid!r} "
            f"in {[str(p) for p in artifact_paths]}"
        )
    if len(matches) > 1:
        raise LookupError(
            f"Duplicate run_uid={ref.run_uid!r}: found {len(matches)} records "
            f"(expected exactly 1)"
        )

    run = matches[0]
    actual_sha = _sha256_hex(run)
    if actual_sha != ref.artifact_sha256:
        raise ValueError(
            f"SHA256 mismatch for run_uid={ref.run_uid!r}: "
            f"expected {ref.artifact_sha256!r}, got {actual_sha!r}"
        )

    return ExperimentRunRecord(ref=ref, run=run)
