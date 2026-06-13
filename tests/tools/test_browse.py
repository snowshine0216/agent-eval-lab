from agent_eval_lab.records.bash import BashRequest
from agent_eval_lab.records.turns import ToolFailure
from agent_eval_lab.tools.browse import BROWSE_TOOLS, apply_browse


def test_bash_apply_returns_execution_request():
    state, applied = apply_browse(
        registry=BROWSE_TOOLS,
        name="bash",
        arguments={"command": "playwright-cli -s=S open http://x"},
        state={},
    )
    assert state == {}  # pure: state unchanged (the effect is at the edge)
    assert isinstance(applied, BashRequest)
    assert applied.command == "playwright-cli -s=S open http://x"


def test_bash_schema_rejects_missing_command():
    state, applied = apply_browse(
        registry=BROWSE_TOOLS, name="bash", arguments={}, state={}
    )
    assert isinstance(applied, ToolFailure)
    assert "schema violation" in applied.error


def test_bash_is_the_only_tool():
    # §18.10: a SINGLE bash tool is all the candidate gets.
    assert tuple(BROWSE_TOOLS) == ("bash",)


def test_unknown_tool_is_failure():
    _, applied = apply_browse(
        registry=BROWSE_TOOLS, name="nope", arguments={}, state={}
    )
    assert isinstance(applied, ToolFailure)
    assert "unknown tool" in applied.error
