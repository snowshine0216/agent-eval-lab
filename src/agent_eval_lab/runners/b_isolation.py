"""Per-run isolation (D20): a unique save-name from run_uid, a preflight-absence
assert, capture-the-created-object-id on save, and reset after grading.

Pure orchestration over the injectable MstrReadbackClient — the helpers contain
NO I/O of their own beyond delegating to the client, so they unit-test against a
fake with zero live infra. The grader keys on the CAPTURED object id (never a
name search), so a name collision after capture cannot mis-grade."""

from __future__ import annotations

import re

from agent_eval_lab.runners.mstr_client import MstrReadbackClient, SaveTarget

_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def save_name_from_run_uid(run_uid: str) -> str:
    """Derive the isolated save-name `<model>-<condition>-<run_id>` from run_uid
    (D20). run_uid is f"{condition_id}__{run_index:04d}"; condition_id may carry a
    colon (provider:model), so non-name-safe chars are slugged to '-'. The result
    is unique per (condition, run_index) — the isolation guarantee."""
    if not run_uid:
        raise ValueError("run_uid must be non-empty to derive a save-name (D20)")
    return _SLUG_RE.sub("-", run_uid).strip("-")


def preflight_absent(client: MstrReadbackClient, target: SaveTarget) -> None:
    """Assert the target save-name is empty BEFORE the run writes (D20). Raises
    ValueError if occupied so a stale object never contaminates a fresh run."""
    if client.name_exists(target):
        raise ValueError(
            f"preflight: object name {target.name!r} already exists in "
            f"{target.folder!r} — refusing to run over an occupied save target (D20)"
        )


def capture_created_id(client: MstrReadbackClient, target: SaveTarget) -> str:
    """Capture the object id created at `target` on save (D20). The grader keys
    on THIS id, never a name search."""
    return client.created_object_id(target)


def reset_after_grading(
    client: MstrReadbackClient, *, project_id: str, object_id: str
) -> None:
    """Delete/reset the captured object after grading (D20)."""
    client.delete_object(project_id=project_id, object_id=object_id)
