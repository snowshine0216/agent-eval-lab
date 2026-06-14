"""Per-run isolation (D20) over a deterministic FAKE client. No live MSTR I/O.

The save-name is derived from run_uid (f"{condition_id}__{run_index:04d}"); a `:`
or `/` in a condition_id (e.g. "deepseek:deepseek-v4-pro") must be slugged so the
save-name is a legal MSTR object name."""

import pytest

from agent_eval_lab.runners.b_isolation import (
    capture_created_id,
    preflight_absent,
    reset_after_grading,
    save_name_from_run_uid,
)
from agent_eval_lab.runners.mstr_client import ReadbackResult, SaveTarget


class _FakeClient:
    def __init__(self, *, exists: bool, object_id: str) -> None:
        self._exists = exists
        self._object_id = object_id
        self.deleted: list[str] = []

    def name_exists(self, target: SaveTarget) -> bool:
        return self._exists

    def created_object_id(self, target: SaveTarget) -> str:
        return self._object_id

    def readback(self, *, project_id, object_id, prompt) -> ReadbackResult:
        return ReadbackResult(
            exists=True, cube="X", rows=(), columns=(), prompt=prompt, grid=()
        )

    def delete_object(self, *, project_id, object_id) -> None:
        self.deleted.append(object_id)


def test_save_name_is_derived_from_run_uid_and_slugged() -> None:
    name = save_name_from_run_uid("deepseek:deepseek-v4-pro__0003")
    # the condition_id colon must not survive as a raw object-name char
    assert ":" not in name
    assert name.endswith("__0003") or name.endswith("-0003")
    assert "deepseek" in name


def test_save_name_rejects_empty_run_uid() -> None:
    with pytest.raises(ValueError):
        save_name_from_run_uid("")


def test_preflight_absent_passes_when_name_is_free() -> None:
    client = _FakeClient(exists=False, object_id="obj-1")
    target = SaveTarget(project_id="P", folder="/runs", name="m-c-0001")
    # does not raise
    preflight_absent(client, target)


def test_preflight_absent_raises_when_name_is_occupied() -> None:
    client = _FakeClient(exists=True, object_id="obj-1")
    target = SaveTarget(project_id="P", folder="/runs", name="m-c-0001")
    with pytest.raises(ValueError, match="already exists"):
        preflight_absent(client, target)


def test_capture_created_id_returns_the_clients_object_id() -> None:
    client = _FakeClient(exists=False, object_id="obj-xyz")
    target = SaveTarget(project_id="P", folder="/runs", name="m-c-0001")
    assert capture_created_id(client, target) == "obj-xyz"


def test_reset_after_grading_deletes_the_captured_object() -> None:
    client = _FakeClient(exists=False, object_id="obj-xyz")
    reset_after_grading(client, project_id="P", object_id="obj-xyz")
    assert client.deleted == ["obj-xyz"]
