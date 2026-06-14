"""The thin injectable MSTR / playwright-cli readback boundary (D20/§18.7).

ALL live MSTR I/O is behind MstrReadbackClient — a Protocol with four methods.
Tests pass a deterministic fake; the live implementation (evaluator-credentialed
playwright-cli readback) is built in the DEFERRED execute phase (EXECUTE-DEFERRED).
The structs are plain frozen dataclasses (immutable, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, kw_only=True)
class SaveTarget:
    """Where a run saves its created object: the project, the run's isolated
    folder, and the unique save-name derived from run_uid (D20)."""

    project_id: str
    folder: str
    name: str


@dataclass(frozen=True, kw_only=True)
class ReadbackResult:
    """The evaluator-credentialed readback of a created object (§18.7).

    `exists` is the captured object's presence in the run folder; the remaining
    fields are the object's definition + executed grid under the prompt. `grid`
    is a tuple of row-tuples (header row first), order-preserving."""

    exists: bool
    cube: str
    rows: tuple[str, ...]
    columns: tuple[str, ...]
    prompt: str
    grid: tuple[tuple[str, ...], ...]


class MstrReadbackClient(Protocol):
    """Injectable boundary for all MSTR/playwright-cli I/O (D20/§18.7).

    Implementations: a deterministic fake in tests; the evaluator-credentialed
    playwright-cli readback in the deferred execute phase."""

    def name_exists(self, target: SaveTarget) -> bool:
        """True iff an object with `target.name` already exists in the folder
        (the preflight-absence check, D20)."""
        ...

    def created_object_id(self, target: SaveTarget) -> str:
        """The object id created at `target` (captured on save, D20). The grader
        keys on THIS id, never a name search."""
        ...

    def readback(
        self, *, project_id: str, object_id: str, prompt: str
    ) -> ReadbackResult:
        """Open the captured object by id, run it under `prompt`, read it back."""
        ...

    def delete_object(self, *, project_id: str, object_id: str) -> None:
        """Delete/reset the created object after grading (D20)."""
        ...
