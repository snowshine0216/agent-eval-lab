"""The grade-less B-set trial record (ADR-0021).

`BTrial` is the on-disk unit of `trials-b-*.jsonl`: everything `run-b` records for
one trial EXCEPT the grade. The grade is the later **owner verdict** (CONTEXT.md:
*owner verdict*), joined to the trial at report time by `report_b` — never a
`GradeResult` fabricated at run time. Frozen + serializable; the Trajectory
round-trip delegates to records/serialize so it stays single-sourced.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.serialize import trajectory_from_dict, trajectory_to_dict
from agent_eval_lab.records.trajectory import Trajectory

# The auto-tag the runner stamps when a trial did not get a fair trial. None for a
# valid (gradeable) trial. "provider_error" / "no_choices" are provider-side
# (is_env_invalid analogue); "env_unhealthy" is health-probe-side.
InvalidReason = Literal["provider_error", "no_choices", "env_unhealthy"]


@dataclass(frozen=True, kw_only=True)
class BTrial:
    run_uid: str
    condition_id: str
    task_id: str  # the ARM: b-b1-noskill / b-b1-skill (arm rides task_id, CONTEXT.md)
    save_name: str
    folder: str
    trajectory: Trajectory
    invalid: bool
    invalid_reason: InvalidReason | None = None


def b_trial_to_dict(trial: BTrial) -> dict[str, Any]:
    return {
        "run_uid": trial.run_uid,
        "condition_id": trial.condition_id,
        "task_id": trial.task_id,
        "save_name": trial.save_name,
        "folder": trial.folder,
        "trajectory": trajectory_to_dict(trial.trajectory),
        "invalid": trial.invalid,
        "invalid_reason": trial.invalid_reason,
    }


def b_trial_from_dict(data: Mapping[str, Any]) -> BTrial:
    return BTrial(
        run_uid=data["run_uid"],
        condition_id=data["condition_id"],
        task_id=data["task_id"],
        save_name=data["save_name"],
        folder=data["folder"],
        trajectory=trajectory_from_dict(data["trajectory"]),
        invalid=data["invalid"],
        invalid_reason=data.get("invalid_reason"),
    )
