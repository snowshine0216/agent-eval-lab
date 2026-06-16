"""Pure node-execution grading core (F3 oracle). Mirrors graders/execution.py.

No I/O, total. The node oracle edge precomputes verdicts keyed by
node_execution_hash; this module only reads them.
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.tasks.schema import AllOf, NodeExecutionSpec, VerificationSpec
from agent_eval_lab.tools.code_world import prefix_collision

GRADER_ID = "node_execution"


@dataclass(frozen=True, kw_only=True)
class NodeExecutionVerdict:
    result: ExecutionResult
    execution_hash: str
    displaced_paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class OverlaidNodeTree:
    files: Mapping[str, str]
    displaced_paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class NodeOverlayCollision:
    pairs: tuple[tuple[str, str], ...]


def overlay_node_oracle(
    base_tree: Mapping[str, str], held_out_files: Mapping[str, str]
) -> "OverlaidNodeTree | NodeOverlayCollision":
    """Oracle-wins overlay of held-out files over the candidate base tree."""
    pairs = tuple(
        (base_path, oracle_path)
        for base_path in sorted(base_tree)
        for oracle_path in sorted(held_out_files)
        if prefix_collision(base_path, oracle_path)
    )
    if pairs:
        return NodeOverlayCollision(pairs=pairs)
    displaced = tuple(sorted(set(base_tree) & set(held_out_files)))
    return OverlaidNodeTree(
        files={**base_tree, **held_out_files}, displaced_paths=displaced
    )


def node_execution_hash(spec: NodeExecutionSpec, base_tree: Mapping[str, str]) -> str:
    blob = json.dumps(
        {
            "held_out_files": dict(spec.held_out_files),
            "test_paths": list(spec.test_paths),
            "base_tree": dict(base_tree),
            "timeout_s": spec.timeout_s,
        },
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def collect_node_execution_specs(
    verification: VerificationSpec,
) -> tuple[NodeExecutionSpec, ...]:
    if isinstance(verification, NodeExecutionSpec):
        return (verification,)
    if isinstance(verification, AllOf):
        return tuple(
            spec
            for sub in verification.specs
            for spec in collect_node_execution_specs(sub)
        )
    return ()


def is_incapable_node_result(result: ExecutionResult) -> bool:
    """True iff the node oracle could not RUN the suite because node rejected the
    harness's own invocation — e.g. ``--test-reporter=junit`` is unsupported on
    node < 20, which exits with code 9 (node's 'bad option' / invalid-argument
    code) having parsed zero test cases. This is an ENVIRONMENT incapability, not
    a model failure: the model's produced tree never got a fair trial, so the run
    is env-invalid (D34 analogue), masked from pass^k rather than scored a 0 FAIL.
    Pure.

    A model that merely breaks the code under a CAPABLE node yields status="error"
    with exit_code 1 (an import/load crash that ran zero tests) — NOT code 9 — so
    it stays a real model FAIL. Exit code 9 is reachable only from node's own CLI
    parser rejecting the oracle's flags, never from user/model code running inside
    an already-started test runner.
    """
    return result.status == "error" and result.exit_code == 9 and not result.tests


def grade_node_execution(
    *, spec: NodeExecutionSpec, trajectory: Trajectory, verdicts: Mapping[str, Any]
) -> GradeResult:
    if trajectory.final_state is None:
        return _non_pass({"execution": "not_run", "reason": "missing_final_state"})
    base_tree = trajectory.final_state.get("files", {})
    key = node_execution_hash(spec, base_tree)
    value = verdicts.get(key)
    if value is None:
        return _non_pass(
            {
                "execution": "error",
                "execution_error": {"kind": "verdict_missing", "execution_hash": key},
                "execution_hash": key,
            }
        )
    if not isinstance(value, NodeExecutionVerdict):
        kind = getattr(value, "kind", "unknown")
        evidence = {
            "execution": "error",
            "execution_error": {
                "kind": kind,
                "detail": getattr(value, "detail", repr(value)),
            },
            "execution_hash": key,
        }
        # A harness exec error (node binary missing, OSError launching the
        # subprocess) means the ORACLE could not run — env-invalid, not a model
        # FAIL. A tree_collision / verdict_missing is a model/wiring fault and
        # stays a plain non-pass.
        if kind == "harness":
            evidence = {
                **evidence,
                "env_invalid": True,
                "env_invalid_reason": "oracle_harness_error",
            }
        return _non_pass(evidence)
    return _interpret(value)


def _interpret(verdict: NodeExecutionVerdict) -> GradeResult:
    result = verdict.result
    passed = result.status == "passed"
    evidence = {
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
    }
    if is_incapable_node_result(result):
        evidence = {
            **evidence,
            "env_invalid": True,
            "env_invalid_reason": "incapable_node",
        }
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence=evidence,
        failure_reason=None,
    )


def _non_pass(evidence: Mapping[str, Any]) -> GradeResult:
    return GradeResult(
        grader_id=GRADER_ID,
        passed=False,
        score=0.0,
        evidence=evidence,
        failure_reason=None,
    )
