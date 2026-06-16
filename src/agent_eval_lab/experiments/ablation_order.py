"""Pure seeded block-randomized execution order for the F-set ablation (§B.7).

A *unit* is one (model, base-task, arm, repetition) attempt. A *block* is one
(model, base-task, repetition); it holds exactly the four arms. Within each block
the four arms are SHUFFLED TOGETHER (interleaved), so provider drift across a
block cannot align with one arm and masquerade as a P/V effect (§B.7). Blocks are
emitted in a fixed nested traversal (model, base-task, rep); the single seeded RNG
is advanced in that fixed traversal, so the order is a pure deterministic function
of (seed, models, base_tasks, k) — no wall-clock, no module-level RNG (§11.9).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

# The 2×2 arms (003 §B.1), in canonical order. The arm rides the task_id (§B.2).
ARMS: tuple[str, ...] = ("bare", "prompt", "feedback", "both")


@dataclass(frozen=True, kw_only=True)
class RunUnit:
    """One scheduled attempt. `model` is the condition_id (provider:model); the arm
    is encoded in `task_id` (`f-{base_task}-{arm}`), never a separate field."""

    model: str
    base_task: str
    arm: str
    repetition: int

    @property
    def task_id(self) -> str:
        return f"f-{self.base_task}-{self.arm}"


def ablation_run_order(
    *, seed: int, models: Sequence[str], base_tasks: Sequence[str], k: int
) -> tuple[RunUnit, ...]:
    """Deterministic block-randomized order over (model × base-task × arm × rep).

    Coverage: exactly each (model, base_task, arm, repetition) once — length
    `len(models) × len(base_tasks) × k × len(ARMS)`. Within every (model, base, rep)
    block the four arms are shuffled together (interleaved). Same seed ⇒ identical
    order; different seed ⇒ (almost surely) different order. Pure: no I/O, no clock.
    """
    rng = random.Random(seed)
    units: list[RunUnit] = []
    for model in models:
        for base in base_tasks:
            for rep in range(k):
                block = [
                    RunUnit(model=model, base_task=base, arm=arm, repetition=rep)
                    for arm in ARMS
                ]
                rng.shuffle(block)  # interleave the 4 arms WITHIN this block
                units.extend(block)
    return tuple(units)
