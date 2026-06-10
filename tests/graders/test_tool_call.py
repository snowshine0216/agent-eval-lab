from agent_eval_lab.graders.tool_call import grade_tool_call_match
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.tasks.schema import ExpectedToolCall, ToolCallMatchSpec
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

SEARCH = ExpectedToolCall(name="search_docs", arguments={"query": "refund policy"})
CREATE = ExpectedToolCall(
    name="create_ticket", arguments={"title": "Printer offline", "priority": "low"}
)


def _spec(
    *expected: ExpectedToolCall, match: str = "exact_sequence"
) -> ToolCallMatchSpec:
    return ToolCallMatchSpec(expected_tool_calls=expected, match=match)


def _call(name: str, arguments: dict, call_id: str = "c1") -> ToolCall:
    return ToolCall(call_id=call_id, name=name, arguments=arguments)


def _trajectory(
    *calls: ToolCall, parse_failure: ParseFailure | None = None
) -> Trajectory:
    turns = (ToolCallTurn(tool_calls=calls),) if calls else ()
    return Trajectory(
        turns=turns,
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="parse_failure" if parse_failure else "completed",
        parse_failure=parse_failure,
    )


def _grade(spec: ToolCallMatchSpec, trajectory: Trajectory) -> GradeResult:
    return grade_tool_call_match(
        spec=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )


def test_exact_sequence_pass_ignores_key_order() -> None:
    observed = _call("create_ticket", {"priority": "low", "title": "Printer offline"})

    result = _grade(_spec(CREATE), _trajectory(observed))

    assert result.passed is True
    assert result.failure_reason is None
    assert result.grader_id == "ast_tool_match"


def test_parse_failure_grades_as_malformed_call() -> None:
    failure = ParseFailure(raw='{"query": ', error="arguments not valid JSON")

    result = _grade(_spec(SEARCH), _trajectory(parse_failure=failure))

    assert result.passed is False
    assert result.failure_reason == "malformed_call"
    assert result.evidence["error"] == "arguments not valid JSON"


def test_schema_invalid_args_grade_as_schema_violation_never_repaired() -> None:
    observed = _call("create_ticket", {"title": "x", "priority": 1})

    result = _grade(_spec(CREATE), _trajectory(observed))

    assert result.failure_reason == "schema_violation"


def test_unknown_tool_name_grades_as_wrong_tool() -> None:
    observed = _call("send_email", {"to": "a@b.c"})

    result = _grade(_spec(SEARCH), _trajectory(observed))

    assert result.failure_reason == "wrong_tool"


def test_unknown_tool_outranks_count_mismatch() -> None:
    result = _grade(
        _spec(SEARCH, CREATE), _trajectory(_call("send_email", {"to": "a@b.c"}))
    )

    assert result.failure_reason == "wrong_tool"
    assert result.evidence["unknown_tool"] == "send_email"


def test_same_position_name_mismatch_is_wrong_tool() -> None:
    observed = _call("create_ticket", {"title": "x", "priority": "low"})

    result = _grade(_spec(SEARCH), _trajectory(observed))

    assert result.failure_reason == "wrong_tool"


def test_same_tool_different_args_is_wrong_args() -> None:
    observed = _call("search_docs", {"query": "billing"})

    result = _grade(_spec(SEARCH), _trajectory(observed))

    assert result.failure_reason == "wrong_args"
    assert result.evidence["position"] == 0


def test_fewer_calls_than_expected_is_missing_call() -> None:
    result = _grade(
        _spec(SEARCH, CREATE),
        _trajectory(_call("search_docs", {"query": "refund policy"})),
    )

    assert result.failure_reason == "missing_call"


def test_more_calls_than_expected_is_extra_call() -> None:
    observed = (
        _call("search_docs", {"query": "refund policy"}, "c1"),
        _call("create_ticket", {"title": "x", "priority": "low"}, "c2"),
    )

    result = _grade(_spec(SEARCH), _trajectory(*observed))

    assert result.failure_reason == "extra_call"


def test_swapped_order_is_order_mismatch_in_exact_sequence() -> None:
    observed = (
        _call("create_ticket", {"title": "Printer offline", "priority": "low"}, "c1"),
        _call("search_docs", {"query": "refund policy"}, "c2"),
    )

    result = _grade(_spec(SEARCH, CREATE), _trajectory(*observed))

    assert result.failure_reason == "order_mismatch"


def test_swapped_order_passes_in_multiset_mode() -> None:
    observed = (
        _call("create_ticket", {"title": "Printer offline", "priority": "low"}, "c1"),
        _call("search_docs", {"query": "refund policy"}, "c2"),
    )

    result = _grade(_spec(SEARCH, CREATE, match="multiset"), _trajectory(*observed))

    assert result.passed is True


def test_multiset_same_names_different_args_is_wrong_args() -> None:
    observed = _call("search_docs", {"query": "billing"})

    result = _grade(_spec(SEARCH, match="multiset"), _trajectory(observed))

    assert result.failure_reason == "wrong_args"


def test_no_calls_expected_and_none_observed_passes() -> None:
    trajectory = Trajectory(
        turns=(MessageTurn(role="assistant", content="No action needed."),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
    )

    result = _grade(_spec(), trajectory)

    assert result.passed is True
