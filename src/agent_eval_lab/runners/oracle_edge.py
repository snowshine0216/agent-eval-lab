"""EDGE: the oracle precompute boundary (ADR-0010, ADR-0011).

Collect the reachable ExecutionSpecs, overlay each onto the trajectory's
final tree (pure, oracle-wins), run the execution edge's sandboxed pytest,
and emit a verdict map keyed by execution_hash — post-trajectory, because
the final tree is only knowable then. An exception never escapes into the
map: every failure is a serializable ExecutionError at the same key (the
judge-edge precedent). Distinct from the execution edge (pytest_edge), the
sandbox boundary this module calls.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from agent_eval_lab.graders.execution import (
    ExecutionVerdict,
    OverlayCollision,
    collect_execution_specs,
    execution_hash,
    overlay_oracle,
)
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.runners.pytest_edge import DEFAULT_TIMEOUT_S, run_pytest
from agent_eval_lab.tasks.schema import ExecutionSpec, VerificationSpec


@dataclass(frozen=True, kw_only=True)
class ExecutionError:
    """Serializable precompute failure at the verdict key (never an exception)."""

    kind: Literal["tree_collision", "harness"]
    detail: str
    execution_hash: str


def _collision_detail(collision: OverlayCollision) -> str:
    pairs = ", ".join(
        f"agent {agent!r} vs oracle {oracle!r}" for agent, oracle in collision.pairs
    )
    return f"canonical-prefix collision: {pairs}"


def _verdict_for(
    *, spec: ExecutionSpec, final_tree: Mapping[str, str], key: str
) -> ExecutionVerdict | ExecutionError:
    overlaid = overlay_oracle(final_tree, spec.held_out_tests)
    if isinstance(overlaid, OverlayCollision):
        return ExecutionError(
            kind="tree_collision",
            detail=_collision_detail(overlaid),
            execution_hash=key,
        )
    timeout_s = spec.timeout_s if spec.timeout_s is not None else DEFAULT_TIMEOUT_S
    try:
        result = run_pytest(overlaid.files, timeout_s=timeout_s)
    except Exception as exc:  # an exception never escapes into the map
        return ExecutionError(kind="harness", detail=repr(exc), execution_hash=key)
    return ExecutionVerdict(
        result=result,
        execution_hash=key,
        displaced_paths=overlaid.displaced_paths,
    )


def _entry(
    spec: ExecutionSpec, final_tree: Mapping[str, str]
) -> tuple[str, ExecutionVerdict | ExecutionError]:
    key = execution_hash(spec, final_tree)
    return key, _verdict_for(spec=spec, final_tree=final_tree, key=key)


def precompute_execution_verdicts(
    *, verification: VerificationSpec, trajectory: Trajectory
) -> dict[str, ExecutionVerdict | ExecutionError]:
    """Build the verdict-map contribution for every reachable ExecutionSpec.

    Returns {} when no ExecutionSpec is reachable or final_state is None —
    the grader then reports its own structured non-pass without any lookup.
    """
    specs = collect_execution_specs(verification)
    if not specs or trajectory.final_state is None:
        return {}
    final_tree = trajectory.final_state.get("files", {})
    return dict(_entry(spec, final_tree) for spec in specs)
