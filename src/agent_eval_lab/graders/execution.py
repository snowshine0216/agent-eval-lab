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

from agent_eval_lab.records.execution import ExecutionResult
from agent_eval_lab.tasks.schema import ExecutionSpec
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
