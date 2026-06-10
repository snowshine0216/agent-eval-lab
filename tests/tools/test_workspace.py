from agent_eval_lab.records.turns import ToolFailure, ToolSuccess
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS, apply

STATE = {
    "docs": {
        "doc-1": {"title": "Refund policy", "body": "Refunds take 5 business days."},
        "doc-2": {"title": "Onboarding guide", "body": "Verify email to activate."},
    },
    "tickets": {"T-7": {"title": "Login broken", "priority": "high", "status": "open"}},
}


def test_registry_exposes_three_tools_with_schemas() -> None:
    assert set(WORKSPACE_TOOLS) == {"search_docs", "create_ticket", "update_ticket"}
    for tool in WORKSPACE_TOOLS.values():
        assert tool.parameters["type"] == "object"
        assert tool.description


def test_search_docs_matches_title_and_body_case_insensitive() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="search_docs",
        arguments={"query": "refund"},
        state=STATE,
    )

    assert new_state == STATE
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"doc_ids": ["doc-1"]}


def test_create_ticket_assigns_next_id_and_does_not_mutate_input() -> None:
    before = {
        "docs": {},
        "tickets": {"T-7": {"title": "a", "priority": "low", "status": "open"}},
    }
    snapshot = {
        "docs": {},
        "tickets": {"T-7": {"title": "a", "priority": "low", "status": "open"}},
    }

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="create_ticket",
        arguments={"title": "Printer offline", "priority": "low"},
        state=before,
    )

    assert before == snapshot
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"ticket_id": "T-8"}
    assert new_state["tickets"]["T-8"] == {
        "title": "Printer offline",
        "priority": "low",
        "status": "open",
    }


def test_update_ticket_changes_status() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="update_ticket",
        arguments={"ticket_id": "T-7", "status": "closed"},
        state=STATE,
    )

    assert isinstance(outcome, ToolSuccess)
    assert new_state["tickets"]["T-7"]["status"] == "closed"
    assert STATE["tickets"]["T-7"]["status"] == "open"


def test_update_unknown_ticket_is_a_business_failure() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="update_ticket",
        arguments={"ticket_id": "T-99", "status": "closed"},
        state=STATE,
    )

    assert new_state == STATE
    assert isinstance(outcome, ToolFailure)
    assert "T-99" in outcome.error


def test_schema_invalid_args_fail_like_a_real_api() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="create_ticket",
        arguments={"title": "x", "priority": "urgent"},
        state=STATE,
    )

    assert new_state == STATE
    assert isinstance(outcome, ToolFailure)
    assert outcome.error.startswith("schema violation")


def test_unknown_tool_fails() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS, name="send_email", arguments={}, state=STATE
    )

    assert new_state == STATE
    assert isinstance(outcome, ToolFailure)
    assert "unknown tool" in outcome.error


def test_every_registered_tool_has_an_implementation() -> None:
    from agent_eval_lab.tools.workspace import _IMPLS

    assert set(WORKSPACE_TOOLS) == set(_IMPLS)
