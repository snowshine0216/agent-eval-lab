from agent_eval_lab.graders.ast_tool_match import grade_tool_calls
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS


def _observed(name, args, call_id="c1"):
    return (ToolCall(call_id=call_id, name=name, arguments=args),)


def _spec(*expected, match="exact_sequence"):
    return ToolCallMatchSpec(expected_tool_calls=tuple(expected), match=match)


def test_exact_match_passes():
    spec = _spec(
        ExpectedToolCall(
            name="create_ticket", arguments={"title": "x", "priority": "low"}
        )
    )
    obs = _observed("create_ticket", {"title": "x", "priority": "low"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.passed is True
    assert result.failure_reason is None


def test_schema_violation_type_coercion_never_passes():
    spec = _spec(
        ExpectedToolCall(
            name="create_ticket", arguments={"title": "x", "priority": "low"}
        )
    )
    obs = _observed("create_ticket", {"title": 1, "priority": "low"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.passed is False
    assert result.failure_reason == "schema_violation"


def test_enum_violation_is_schema_violation():
    spec = _spec(
        ExpectedToolCall(
            name="create_ticket", arguments={"title": "x", "priority": "low"}
        )
    )
    obs = _observed("create_ticket", {"title": "x", "priority": "urgent"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "schema_violation"


def test_unknown_tool_name_is_malformed_call():
    spec = _spec(
        ExpectedToolCall(
            name="create_ticket", arguments={"title": "x", "priority": "low"}
        )
    )
    obs = _observed("nonexistent_tool", {})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "malformed_call"


def test_wrong_tool():
    spec = _spec(ExpectedToolCall(name="search_docs", arguments={"query": "x"}))
    obs = _observed("create_ticket", {"title": "x", "priority": "low"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "wrong_tool"


def test_wrong_args():
    spec = _spec(ExpectedToolCall(name="search_docs", arguments={"query": "install"}))
    obs = _observed("search_docs", {"query": "deploy"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "wrong_args"


def test_missing_call():
    spec = _spec(
        ExpectedToolCall(
            name="create_ticket", arguments={"title": "x", "priority": "low"}
        ),
        ExpectedToolCall(
            name="update_ticket", arguments={"ticket_id": "T-1", "status": "closed"}
        ),
    )
    obs = _observed("create_ticket", {"title": "x", "priority": "low"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "missing_call"


def test_extra_call():
    spec = _spec(ExpectedToolCall(name="search_docs", arguments={"query": "x"}))
    obs = (
        ToolCall(call_id="c1", name="search_docs", arguments={"query": "x"}),
        ToolCall(call_id="c2", name="search_docs", arguments={"query": "y"}),
    )
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "extra_call"


def test_order_mismatch_in_exact_sequence():
    spec = _spec(
        ExpectedToolCall(
            name="create_ticket", arguments={"title": "x", "priority": "low"}
        ),
        ExpectedToolCall(
            name="update_ticket", arguments={"ticket_id": "T-1", "status": "closed"}
        ),
    )
    obs = (
        ToolCall(
            call_id="c1",
            name="update_ticket",
            arguments={"ticket_id": "T-1", "status": "closed"},
        ),
        ToolCall(
            call_id="c2",
            name="create_ticket",
            arguments={"title": "x", "priority": "low"},
        ),
    )
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "order_mismatch"


def test_multiset_ignores_order_but_keeps_count():
    spec = _spec(
        ExpectedToolCall(
            name="create_ticket", arguments={"title": "x", "priority": "low"}
        ),
        ExpectedToolCall(
            name="update_ticket", arguments={"ticket_id": "T-1", "status": "closed"}
        ),
        match="multiset",
    )
    obs = (
        ToolCall(
            call_id="c1",
            name="update_ticket",
            arguments={"ticket_id": "T-1", "status": "closed"},
        ),
        ToolCall(
            call_id="c2",
            name="create_ticket",
            arguments={"title": "x", "priority": "low"},
        ),
    )
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.passed is True


def test_order_mismatch_same_tool_swapped_args():
    spec = _spec(
        ExpectedToolCall(name="search_docs", arguments={"query": "first"}),
        ExpectedToolCall(name="search_docs", arguments={"query": "second"}),
    )
    obs = (
        ToolCall(call_id="c1", name="search_docs", arguments={"query": "second"}),
        ToolCall(call_id="c2", name="search_docs", arguments={"query": "first"}),
    )
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.passed is False
    assert result.failure_reason == "order_mismatch"


def test_multiset_duplicate_count_mismatch_fails():
    spec = _spec(
        ExpectedToolCall(name="search_docs", arguments={"query": "x"}),
        ExpectedToolCall(name="search_docs", arguments={"query": "x"}),
        match="multiset",
    )
    obs = _observed("search_docs", {"query": "x"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.passed is False
    assert result.failure_reason == "missing_call"
