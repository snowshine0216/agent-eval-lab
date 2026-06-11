"""Pure Tier-2 execution grading core (ADR-0010, ADR-0011): no I/O, total.

The oracle edge (runners/oracle_edge.precompute_execution_verdicts) overlays
the oracle tests onto the trajectory's final tree, runs the sandboxed pytest,
and threads an immutable verdict map keyed by `execution_hash` into this pure
grader, which only reads it. This module imports no process or filesystem
machinery; importing it never executes anything.
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.tasks.schema import AllOf, ExecutionSpec, VerificationSpec
from agent_eval_lab.tools.code_world import prefix_collision

GRADER_ID = "execution"


@dataclass(frozen=True, kw_only=True)
class ExecutionVerdict:
    """The oracle run's record plus its hash and displaced paths (ADR-0011)."""

    result: ExecutionResult
    execution_hash: str
    displaced_paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class OverlaidTree:
    """Combined agent+oracle tree; the oracle wins exact-path collisions."""

    files: Mapping[str, str]
    displaced_paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class OverlayCollision:
    """Canonical-prefix collisions between agent and oracle paths (ADR-0010)."""

    pairs: tuple[tuple[str, str], ...]  # (agent_path, oracle_path), sorted


def overlay_oracle(
    final_tree: Mapping[str, str], held_out_tests: Mapping[str, str]
) -> OverlaidTree | OverlayCollision:
    """Pure oracle-wins overlay; detects collisions before materialization."""
    pairs = tuple(
        (agent_path, oracle_path)
        for agent_path in sorted(final_tree)
        for oracle_path in sorted(held_out_tests)
        if prefix_collision(agent_path, oracle_path)
    )
    if pairs:
        return OverlayCollision(pairs=pairs)
    displaced = tuple(sorted(set(final_tree) & set(held_out_tests)))
    return OverlaidTree(
        files={**final_tree, **held_out_tests}, displaced_paths=displaced
    )


def execution_hash(spec: ExecutionSpec, final_tree: Mapping[str, str]) -> str:
    """sha256 over canonical JSON of oracle tests + final tree + raw timeout_s.

    The `prompt_hash` convention (ADR-0011): computable on both sides of the
    boundary, well-defined even when the overlay would collide, and covering
    the RAW `timeout_s` field (null when None), never the edge default.
    """
    blob = json.dumps(
        {
            "held_out_tests": dict(spec.held_out_tests),
            "final_tree": dict(final_tree),
            "timeout_s": spec.timeout_s,
        },
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def collect_execution_specs(
    verification: VerificationSpec,
) -> tuple[ExecutionSpec, ...]:
    """Pure walk of the spec tree (recurses AllOf, the judge-collector precedent)."""
    if isinstance(verification, ExecutionSpec):
        return (verification,)
    if isinstance(verification, AllOf):
        return tuple(
            spec for sub in verification.specs for spec in collect_execution_specs(sub)
        )
    return ()


def grade_execution(
    *,
    spec: ExecutionSpec,
    trajectory: Trajectory,
    verdicts: Mapping[str, Any],
) -> GradeResult:
    """Read the precomputed verdict and interpret it. No I/O, total."""
    if trajectory.final_state is None:
        return _non_pass({"execution": "not_run", "reason": "missing_final_state"})
    final_tree = trajectory.final_state.get("files", {})
    key = execution_hash(spec, final_tree)
    value = verdicts.get(key)
    if value is None:
        return _non_pass(
            {
                "execution": "error",
                "execution_error": {"kind": "verdict_missing", "execution_hash": key},
                "execution_hash": key,
            }
        )
    if not isinstance(value, ExecutionVerdict):
        return _non_pass(_error_evidence(key, value))
    return _interpret(value)


def _interpret(verdict: ExecutionVerdict) -> GradeResult:
    result = verdict.result
    passed = result.status == "passed"
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={
            "execution": "run",
            "status": result.status,
            "exit_code": result.exit_code,
            "counts": {
                "passed": result.passed,
                "failed": result.failed,
                "errors": result.errors,
                "skipped": result.skipped,
            },
            "tests": [[case.test_id, case.status] for case in result.tests],
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_hash": verdict.execution_hash,
            "displaced_paths": list(verdict.displaced_paths),
        },
        failure_reason=None,
    )


def _error_evidence(key: str, value: Any) -> dict[str, Any]:
    # An ExecutionError (or ANY foreign value, e.g. a JudgeVerdict on a
    # pathological hash collision) at the key: structured error evidence with
    # kind "unknown" as the getattr fallback — the judge precedent. The
    # three-valued evidence["execution"] ("run" | "not_run" | "error") is the
    # MECHANICAL DISCRIMINATOR item 004's classifier reads.
    return {
        "execution": "error",
        "execution_error": {
            "kind": getattr(value, "kind", "unknown"),
            "detail": getattr(value, "detail", repr(value)),
        },
        "execution_hash": key,
    }


def _non_pass(evidence: Mapping[str, Any]) -> GradeResult:
    # Every execution non-pass is an outcome miss or infra record, never a
    # policy breach: failure_reason stays None (the closed taxonomy untouched).
    return GradeResult(
        grader_id=GRADER_ID,
        passed=False,
        score=0.0,
        evidence=evidence,
        failure_reason=None,
    )
