import pytest

from agent_eval_lab.records.node_execution import (
    NodeExecutionRequest,
    node_execution_request_from_dict,
    node_execution_request_to_dict,
)


def test_request_round_trips() -> None:
    req = NodeExecutionRequest(
        files={"tests/wdio/package.json": '{"type":"module"}'},
        test_paths=("tests/wdio/utils/failure-analysis/__tests__/report-to-allure.test.js",),
    )
    assert node_execution_request_from_dict(node_execution_request_to_dict(req)) == req


def test_request_is_frozen() -> None:
    req = NodeExecutionRequest(files={}, test_paths=())
    with pytest.raises(Exception):
        req.files = {"x": "y"}  # type: ignore[misc]
