"""PURE: the B-1 verdict sheet (spec §5 / §11.9).

emit_verdict_sheet(trials) -> (markdown, csv): the definition-match checklist on
top, one evidence row per trial (model, arm, instructed save-name, folder,
stop_reason — max_rounds flagged distinctly as (censored), rounds, tokens, cost*,
wall-time, transcript path) + a BLANK verdict column the owner fills. Distinct from
the blind annotation packet: the owner inspects the live MSTR object, so the sheet
carries the save-name + folder (not blind). *cost is left blank here — it is
derived at report time from tokens x pricing (chat) / total_cost_usd (claude); the
sheet shows tokens + any per-run total_cost_usd for at-a-glance review.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from agent_eval_lab.records.b_trial import BTrial

_CHECKLIST = (
    "## B-1 definition-match checklist (owner verdict: PASS | FAIL | INVALID)\n\n"
    "A trial PASSES iff all five hold:\n"
    "- **R1** — an object exists, saved under the instructed unique name, "
    "in the candidate folder.\n"
    "- **R2** — source dataset = SAPBW > AV_TUTO > "
    "Query_CharacteristicValue_Mandatory.\n"
    "- **R3** — Rows include Years Hierarchy AND Region.\n"
    "- **R4** — Columns include Cost.\n"
    "- **R5** — the mandatory prompt is answered South and the report renders "
    "the prompted result.\n\n"
    "PASS = R1 ∧ R2 ∧ R3 ∧ R4 ∧ R5; otherwise FAIL. INVALID = env/provider failure "
    "(auto-tagged; owner may override).\n"
)

_COLUMNS = (
    "model",
    "arm",
    "save_name",
    "folder",
    "stop_reason",
    "rounds",
    "prompt_tokens",
    "completion_tokens",
    "total_cost_usd",
    "wall_time_s",
    "verdict",
)


def _stop_display(trial: BTrial) -> str:
    """A max_rounds (or safety_cap) cap is a CENSORED task-failure — flag it
    distinctly so the owner does not read it as a clean completion (spec §6.3)."""
    sr = trial.trajectory.stop_reason
    if sr in ("max_rounds", "safety_cap"):
        return f"{sr} (censored)"
    return sr


def _row_values(trial: BTrial) -> tuple[str, ...]:
    t = trial.trajectory
    return (
        trial.condition_id,
        trial.task_id,
        trial.save_name,
        trial.folder,
        _stop_display(trial),
        str(t.rounds),
        str(t.usage.prompt_tokens),
        str(t.usage.completion_tokens),
        "" if t.total_cost_usd is None else f"{t.total_cost_usd:.4f}",
        f"{t.wall_time_s:.1f}",
        "",  # blank verdict — the owner fills PASS | FAIL | INVALID
    )


def emit_verdict_sheet(trials: Sequence[BTrial]) -> tuple[str, str]:
    """Return (markdown, csv). PURE — no I/O; the CLI writes the strings to disk."""
    rows = [_row_values(t) for t in trials]

    header = "| " + " | ".join(_COLUMNS) + " |"
    sep = "| " + " | ".join("---" for _ in _COLUMNS) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    markdown = f"{_CHECKLIST}\n## Evidence rows\n\n{header}\n{sep}\n{body}\n"

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_COLUMNS)
    writer.writerows(rows)
    return markdown, buf.getvalue()
