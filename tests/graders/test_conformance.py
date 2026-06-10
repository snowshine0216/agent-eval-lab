import json
from pathlib import Path

import pytest

from agent_eval_lab.graders.ast_tool_match import grade_tool_calls
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS

CASES = json.loads((Path(__file__).parent / "conformance" / "cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_conformance_matches_oracle(case):
    spec = ToolCallMatchSpec(
        expected_tool_calls=tuple(
            ExpectedToolCall(name=e["name"], arguments=e["arguments"]) for e in case["expected"]
        ),
        match=case["match"],
    )
    observed = tuple(
        ToolCall(call_id=o["call_id"], name=o["name"], arguments=o["arguments"])
        for o in case["observed"]
    )
    result = grade_tool_calls(spec, observed, TOOL_SCHEMAS)
    assert result.passed is case["oracle"]["passed"]
    assert result.failure_reason == case["oracle"]["failure_reason"]
