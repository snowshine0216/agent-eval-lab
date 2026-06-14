"""The MSTR client boundary is a Protocol + plain frozen structs. No live I/O.
A fake client (a plain object with the four methods) must satisfy the Protocol
shape used by the isolation helpers and the runner."""

from agent_eval_lab.runners.mstr_client import (
    MstrReadbackClient,
    ReadbackResult,
    SaveTarget,
)


def test_readback_result_is_a_frozen_struct() -> None:
    r = ReadbackResult(
        exists=True,
        cube="X",
        rows=("A", "B"),
        columns=("C",),
        prompt="South",
        grid=(("h",), ("v",)),
    )
    assert r.exists is True
    assert r.rows == ("A", "B")


def test_save_target_carries_folder_and_name() -> None:
    t = SaveTarget(project_id="P", folder="/runs", name="m-c-0001")
    assert t.name == "m-c-0001"


def test_fake_client_satisfies_protocol() -> None:
    class _Fake:
        def name_exists(self, target: SaveTarget) -> bool:
            return False

        def created_object_id(self, target: SaveTarget) -> str:
            return "fake-id"

        def readback(self, *, project_id: str, object_id: str, prompt: str):
            return ReadbackResult(
                exists=True, cube="X", rows=(), columns=(), prompt=prompt, grid=()
            )

        def delete_object(self, *, project_id: str, object_id: str) -> None:
            return None

    client: MstrReadbackClient = _Fake()  # structural check
    target = SaveTarget(project_id="P", folder="/r", name="n")
    assert client.name_exists(target) is False
