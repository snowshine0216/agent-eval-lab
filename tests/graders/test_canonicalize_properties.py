from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.graders.ast_tool_match import grade_tool_calls
from agent_eval_lab.graders.canonicalize import canonicalize
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS

# JSON-ish values the grader may encounter.
json_scalars = st.none() | st.booleans() | st.integers() | st.text()
json_values = st.recursive(
    json_scalars,
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=8,
)


@given(json_values)
def test_canonicalize_is_idempotent(value):
    once = canonicalize(value)
    assert canonicalize(value) == once  # stable across repeated calls
    assert canonicalize(once) == once  # true fixed point: f(f(x)) == f(x)


@given(st.text(min_size=1))
def test_schema_invalid_priority_never_passes(bad_priority):
    # Any priority outside the enum must never grade as pass.
    from hypothesis import assume

    assume(bad_priority not in ("low", "medium", "high"))
    spec = ToolCallMatchSpec(
        expected_tool_calls=(
            ExpectedToolCall(
                name="create_ticket", arguments={"title": "x", "priority": "low"}
            ),
        )
    )
    observed = (
        ToolCall(
            call_id="c1",
            name="create_ticket",
            arguments={"title": "x", "priority": bad_priority},
        ),
    )
    result = grade_tool_calls(spec, observed, TOOL_SCHEMAS)
    assert result.passed is False
    assert result.failure_reason == "schema_violation"


@given(st.integers())
def test_type_coercion_title_never_passes(bad_title):
    # An int title (type-coercion attempt) must never pass.
    spec = ToolCallMatchSpec(
        expected_tool_calls=(
            ExpectedToolCall(
                name="create_ticket", arguments={"title": "x", "priority": "low"}
            ),
        )
    )
    observed = (
        ToolCall(
            call_id="c1",
            name="create_ticket",
            arguments={"title": bad_title, "priority": "low"},
        ),
    )
    result = grade_tool_calls(spec, observed, TOOL_SCHEMAS)
    assert result.passed is False
    assert result.failure_reason == "schema_violation"
