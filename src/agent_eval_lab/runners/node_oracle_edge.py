"""EDGE: the node oracle precompute boundary (F3, §18.6). Mirrors oracle_edge.py."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from agent_eval_lab.graders.node_execution import (
    NodeExecutionVerdict,
    NodeOverlayCollision,
    collect_node_execution_specs,
    node_execution_hash,
    overlay_node_oracle,
)
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.runners.node_edge import DEFAULT_TIMEOUT_S, run_node_tests
from agent_eval_lab.tasks.schema import NodeExecutionSpec, VerificationSpec


@dataclass(frozen=True, kw_only=True)
class NodeExecutionError:
    kind: Literal["tree_collision", "harness"]
    detail: str
    execution_hash: str


def _collision_detail(collision: NodeOverlayCollision) -> str:
    pairs = ", ".join(
        f"base {b!r} vs oracle {o!r}" for b, o in collision.pairs
    )
    return f"canonical-prefix collision: {pairs}"


def _verdict_for(
    *, spec: NodeExecutionSpec, base_tree: Mapping[str, str], key: str
) -> NodeExecutionVerdict | NodeExecutionError:
    overlaid = overlay_node_oracle(base_tree, spec.held_out_files)
    if isinstance(overlaid, NodeOverlayCollision):
        return NodeExecutionError(
            kind="tree_collision",
            detail=_collision_detail(overlaid),
            execution_hash=key,
        )
    timeout_s = spec.timeout_s if spec.timeout_s is not None else DEFAULT_TIMEOUT_S
    try:
        result = run_node_tests(overlaid.files, spec.test_paths, timeout_s=timeout_s)
    except (RuntimeError, OSError) as exc:
        return NodeExecutionError(kind="harness", detail=repr(exc), execution_hash=key)
    return NodeExecutionVerdict(
        result=result, execution_hash=key, displaced_paths=overlaid.displaced_paths
    )


def _entry(spec: NodeExecutionSpec, base_tree: Mapping[str, str]):
    key = node_execution_hash(spec, base_tree)
    return key, _verdict_for(spec=spec, base_tree=base_tree, key=key)


def precompute_node_verdicts(
    *, verification: VerificationSpec, trajectory: Trajectory
) -> dict[str, NodeExecutionVerdict | NodeExecutionError]:
    specs = collect_node_execution_specs(verification)
    if not specs or trajectory.final_state is None:
        return {}
    base_tree = trajectory.final_state.get("files", {})
    return dict(_entry(spec, base_tree) for spec in specs)
