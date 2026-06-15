"""Pure per-domain `max_rounds` resolution (ADR-0017, §A.2/§11.3).

The user-facing turn budget. A per-task `metadata.max_rounds` override WINS over
the per-domain default; an unmapped domain (B is config-only/deferred — §9.9)
yields the task override if present, else None (unbounded — never invent a cap).
Lives here, NOT on ExperimentSpec: adding a spec field would re-hash the frozen
M1 spec (experiments/schema.py forbids field changes; verify_spec_hash must keep
passing — item-002 spec Constraints). This is a runtime resolver, not pre-reg.
"""

from __future__ import annotations

from agent_eval_lab.tasks.schema import Task

# Per-domain defaults (ADR-0017 Decision): code 20, browser 50. The F-ablation
# pins {F:40} at its own experiment level (item 003+), not here.
DOMAIN_MAX_ROUNDS: dict[str, int] = {"F": 20, "D": 50}


def resolve_max_rounds(*, domain: str, task: Task) -> int | None:
    """Resolution order: task override (`metadata.max_rounds`) > domain default.

    Returns None (unbounded) for an unmapped domain with no task override.
    Raises ValueError if the resolved value is <= 0 (a config error: 0 or
    negative fires one API call then stops, and is never a real budget).
    None (unbounded) is always valid.
    """
    override = task.metadata.max_rounds
    resolved = override if override is not None else DOMAIN_MAX_ROUNDS.get(domain)
    if resolved is not None and resolved <= 0:
        raise ValueError(
            f"max_rounds must be a positive integer, got {resolved!r} "
            f"(task={task.id!r}, domain={domain!r})"
        )
    return resolved
