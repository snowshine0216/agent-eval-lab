from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.records.turns import ToolFailure, ToolSuccess
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


_V2_STATE = {
    "docs": {"doc-1": {"title": "Refund", "body": "5 days"}},
    "tickets": {
        "T-1": {
            "title": "A",
            "priority": "high",
            "status": "open",
            "assignee": "u-1",
            "created": "2026-01-10",
        }
    },
    "accounts": {
        "u-1": {
            "name": "Ada",
            "email": "ada@example.com",
            "plan": "pro",
            "tickets": ["T-1"],
            "created": "2025-11-01",
        }
    },
    "emails": {},
}

_FIXED_CALLS = [
    ("get_account", {"user_id": "u-1"}),
    ("list_tickets", {"status": "open"}),
    ("send_email", {"to": "ada@example.com", "subject": "S", "body": "B"}),
    ("archive_ticket", {"ticket_id": "T-1"}),
    ("find_account", {"email": "ada@example.com"}),
    ("draft_email", {"to": "ada@example.com", "subject": "S", "body": "B"}),
]


def test_every_v2_tool_is_deterministic_over_fixed_input() -> None:
    for name, arguments in _FIXED_CALLS:
        first_state, first_outcome = apply(
            registry=WORKSPACE_TOOLS, name=name, arguments=arguments, state=_V2_STATE
        )
        second_state, second_outcome = apply(
            registry=WORKSPACE_TOOLS, name=name, arguments=arguments, state=_V2_STATE
        )
        assert first_state == second_state, name
        assert isinstance(first_outcome, ToolSuccess), name
        assert first_outcome.result == second_outcome.result, name
