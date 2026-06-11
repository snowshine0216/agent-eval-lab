import dataclasses
import json

import pytest

from agent_eval_lab.records.execution import (
    OUTPUT_CAP_BYTES,
    TRUNCATION_MARKER,
    ExecutionRequest,
    ExecutionResult,
    TestCaseResult,
    execution_request_from_dict,
    execution_request_to_dict,
    execution_result_from_dict,
    execution_result_to_dict,
    truncate_output,
)

RESULT = ExecutionResult(
    status="failed",
    exit_code=1,
    passed=1,
    failed=1,
    errors=0,
    skipped=1,
    tests=(
        TestCaseResult(test_id="test_mod::test_a", status="failed"),
        TestCaseResult(test_id="test_mod::test_b", status="passed"),
        TestCaseResult(test_id="test_mod::test_c", status="skipped"),
    ),
    stdout="1 failed, 1 passed, 1 skipped in <duration>",
    stderr="",
)


def test_execution_request_round_trips() -> None:
    request = ExecutionRequest(files={"a.py": "x = 1\n", "test_a.py": "import a\n"})
    assert execution_request_from_dict(execution_request_to_dict(request)) == (request)


def test_execution_result_round_trips() -> None:
    assert execution_result_from_dict(execution_result_to_dict(RESULT)) == RESULT


def test_execution_result_dict_is_json_shaped() -> None:
    data = execution_result_to_dict(RESULT)
    assert json.loads(json.dumps(data)) == data


def test_execution_result_dict_has_exact_keys_no_duration() -> None:
    assert sorted(execution_result_to_dict(RESULT)) == [
        "errors",
        "exit_code",
        "failed",
        "passed",
        "skipped",
        "status",
        "stderr",
        "stdout",
        "tests",
    ]


def test_records_are_frozen() -> None:
    request = ExecutionRequest(files={})
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.files = {}  # type: ignore[misc]


def test_truncate_output_passes_short_text_through() -> None:
    assert truncate_output("short") == "short"


def test_truncate_output_keeps_head_and_appends_marker() -> None:
    text = "x" * (OUTPUT_CAP_BYTES + 100)
    assert truncate_output(text) == "x" * OUTPUT_CAP_BYTES + TRUNCATION_MARKER


def test_truncate_output_never_splits_a_multibyte_char() -> None:
    text = "€" * OUTPUT_CAP_BYTES  # 3 UTF-8 bytes each — far over the cap
    truncated = truncate_output(text)
    assert truncated.endswith(TRUNCATION_MARKER)
    body = truncated.removesuffix(TRUNCATION_MARKER)
    assert body == "€" * (OUTPUT_CAP_BYTES // 3)
