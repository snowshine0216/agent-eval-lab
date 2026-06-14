"""run_b yields one ReplacementOutcome per B task over a FAKE MstrReadbackClient
(no live MSTR I/O). The fake returns a configurable readback; the grader's verdict
flows into the outcome. The isolation lifecycle (preflight/capture/reset) is
exercised against the fake — preflight on an occupied name VOIDs/raises per D20."""

from agent_eval_lab.datasets.b1_oracle import build_b1_verification
from agent_eval_lab.runners.b_run import run_b
from agent_eval_lab.runners.mstr_client import ReadbackResult, SaveTarget
from agent_eval_lab.runners.multi_run import ReplacementOutcome
from agent_eval_lab.tasks.schema import ReadbackSpec, Task, TaskInput, TaskMetadata


def _golden_result() -> ReadbackResult:
    return ReadbackResult(
        exists=True,
        cube="Query_CharacteristicValue_Mandatory",
        rows=("Years Hierarchy", "Region"),
        columns=("Cost",),
        prompt="South",
        grid=(("h",), ("v",)),
    )


def _spec() -> ReadbackSpec:
    return ReadbackSpec(
        expected_cube="Query_CharacteristicValue_Mandatory",
        required_rows=("Years Hierarchy", "Region"),
        required_columns=("Cost",),
        expected_prompt="South",
        golden_grid=(("h",), ("v",)),
    )


class _FakeClient:
    def __init__(self, *, exists_before: bool, result: ReadbackResult) -> None:
        self._exists_before = exists_before
        self._result = result
        self.deleted: list[str] = []

    def name_exists(self, target: SaveTarget) -> bool:
        return self._exists_before

    def created_object_id(self, target: SaveTarget) -> str:
        return "obj-created-1"

    def readback(self, *, project_id, object_id, prompt) -> ReadbackResult:
        return self._result

    def delete_object(self, *, project_id, object_id) -> None:
        self.deleted.append(object_id)


def _b_task() -> Task:
    return Task(
        id="b-b1-skill",
        capability="browser_mstr",
        input=TaskInput(messages=(), available_tools=("bash",)),
        verification=_spec(),
        metadata=TaskMetadata(split="held_out", version="b-domain-v1", provenance="x"),
        initial_state={"task_key": "B-1"},
    )


def test_run_b_golden_readback_passes_and_resets() -> None:
    client = _FakeClient(exists_before=False, result=_golden_result())
    outcomes = list(
        run_b(
            tasks=(_b_task(),),
            client=client,
            project_id="FAKE_PROJECT",
            folder="/runs",
            condition_id="local:m",
            k=1,
        )
    )
    assert len(outcomes) == 1
    assert isinstance(outcomes[0], ReplacementOutcome)
    assert outcomes[0].valid_runs[0].grade.passed is True
    # the captured object was reset after grading (D20)
    assert client.deleted == ["obj-created-1"]


def test_run_b_wrong_cube_readback_fails() -> None:
    bad = ReadbackResult(
        exists=True,
        cube="SOME_OTHER_CUBE",
        rows=("Years Hierarchy", "Region"),
        columns=("Cost",),
        prompt="South",
        grid=(("h",), ("v",)),
    )
    client = _FakeClient(exists_before=False, result=bad)
    outcomes = list(
        run_b(
            tasks=(_b_task(),),
            client=client,
            project_id="FAKE_PROJECT",
            folder="/runs",
            condition_id="local:m",
            k=1,
        )
    )
    assert outcomes[0].valid_runs[0].grade.passed is False


def test_run_b_preflight_occupied_name_voids_outcome() -> None:
    client = _FakeClient(exists_before=True, result=_golden_result())
    outcomes = list(
        run_b(
            tasks=(_b_task(),),
            client=client,
            project_id="FAKE_PROJECT",
            folder="/runs",
            condition_id="local:m",
            k=1,
        )
    )
    # an occupied save target is an env/isolation invalidity -> VOID, never scored
    assert outcomes[0].void is True
    assert outcomes[0].valid_runs == ()
