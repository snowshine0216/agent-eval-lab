from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.records.turns import ToolFailure
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS, apply

invalid_priority = st.text(max_size=20).filter(
    lambda s: s not in {"low", "medium", "high"}
)


@given(priority=invalid_priority)
def test_schema_invalid_priority_never_succeeds(priority: str) -> None:
    state = {"docs": {}, "tickets": {}}

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="create_ticket",
        arguments={"title": "x", "priority": priority},
        state=state,
    )

    assert isinstance(outcome, ToolFailure)
    assert new_state == state
