import pytest

from agent_eval_lab.records.turns import ToolFailure, ToolSuccess
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS, ToolDef, apply

STATE = {
    "docs": {
        "doc-1": {"title": "Refund policy", "body": "Refunds take 5 business days."},
        "doc-2": {"title": "Onboarding guide", "body": "Verify email to activate."},
    },
    "tickets": {"T-7": {"title": "Login broken", "priority": "high", "status": "open"}},
}


def test_registry_exposes_eight_tools_with_schemas() -> None:
    assert set(WORKSPACE_TOOLS) == {
        "search_docs",
        "create_ticket",
        "update_ticket",
        "get_account",
        "list_tickets",
        "send_email",
        "archive_ticket",
        "find_account",
        "draft_email",
    }
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
        registry=WORKSPACE_TOOLS, name="no_such_tool", arguments={}, state=STATE
    )

    assert new_state == STATE
    assert isinstance(outcome, ToolFailure)
    assert "unknown tool" in outcome.error


def test_every_registered_tool_has_an_implementation() -> None:
    from agent_eval_lab.tools.workspace import _IMPLS

    assert set(WORKSPACE_TOOLS) == set(_IMPLS)


def test_registered_tool_without_implementation_raises_loudly() -> None:
    ghost = ToolDef(
        name="ghost_tool",
        description="registered, no impl",
        parameters={"type": "object"},
    )
    registry = {**WORKSPACE_TOOLS, "ghost_tool": ghost}

    with pytest.raises(RuntimeError, match="harness misconfiguration"):
        apply(registry=registry, name="ghost_tool", arguments={}, state=STATE)


# ---------------------------------------------------------------------------
# v2 tool tests
# ---------------------------------------------------------------------------

V2_STATE = {
    "docs": {},
    "tickets": {
        "T-1": {
            "title": "Login broken",
            "priority": "high",
            "status": "open",
            "assignee": "u-1",
            "created": "2026-01-10",
        }
    },
    "accounts": {
        "u-1": {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "plan": "pro",
            "tickets": ["T-1"],
            "created": "2025-11-01",
        }
    },
    "emails": {},
}


def test_get_account_returns_exact_account_and_does_not_mutate() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="get_account",
        arguments={"user_id": "u-1"},
        state=V2_STATE,
    )

    assert new_state == V2_STATE
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {
        "user_id": "u-1",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "plan": "pro",
        "tickets": ["T-1"],
        "created": "2025-11-01",
    }


def test_get_account_unknown_user_is_a_business_failure() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="get_account",
        arguments={"user_id": "u-99"},
        state=V2_STATE,
    )

    assert new_state == V2_STATE
    assert isinstance(outcome, ToolFailure)
    assert "u-99" in outcome.error


LIST_STATE = {
    "docs": {},
    "tickets": {
        "T-1": {
            "title": "A",
            "priority": "high",
            "status": "open",
            "assignee": "u-1",
            "created": "2026-01-10",
        },
        "T-2": {
            "title": "B",
            "priority": "high",
            "status": "open",
            "assignee": "u-1",
            "created": "2025-12-01",
        },
        "T-3": {
            "title": "C",
            "priority": "low",
            "status": "closed",
            "assignee": "u-2",
            "created": "2026-02-01",
        },
    },
    "accounts": {},
    "emails": {},
}


def test_list_tickets_no_filter_returns_all_with_fields_and_no_mutation() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS, name="list_tickets", arguments={}, state=LIST_STATE
    )

    assert new_state == LIST_STATE
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["ticket_ids"] == ["T-1", "T-2", "T-3"]
    assert outcome.result["tickets"]["T-2"]["created"] == "2025-12-01"


def test_list_tickets_filters_by_status_and_priority() -> None:
    _, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="list_tickets",
        arguments={"status": "open", "priority": "high"},
        state=LIST_STATE,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["ticket_ids"] == ["T-1", "T-2"]


def test_list_tickets_filters_by_assignee() -> None:
    _, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="list_tickets",
        arguments={"assignee": "u-2"},
        state=LIST_STATE,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["ticket_ids"] == ["T-3"]


def test_list_tickets_unknown_filter_value_is_empty_not_error() -> None:
    _, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="list_tickets",
        arguments={"status": "archived"},
        state=LIST_STATE,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["ticket_ids"] == []


def test_send_email_appends_sent_email_with_next_id_no_mutation() -> None:
    before = {"docs": {}, "tickets": {}, "accounts": {}, "emails": {}}
    snapshot = {"docs": {}, "tickets": {}, "accounts": {}, "emails": {}}

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="send_email",
        arguments={"to": "ada@example.com", "subject": "Hi", "body": "Welcome."},
        state=before,
    )

    assert before == snapshot
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"email_id": "e-1"}
    assert new_state["emails"]["e-1"] == {
        "to": "ada@example.com",
        "subject": "Hi",
        "body": "Welcome.",
        "state": "sent",
    }


def test_send_email_mints_next_id_above_existing() -> None:
    state = {
        "docs": {},
        "tickets": {},
        "accounts": {},
        "emails": {"e-1": {"to": "x", "subject": "y", "body": "z", "state": "sent"}},
    }

    _, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="send_email",
        arguments={"to": "b@example.com", "subject": "S", "body": "B"},
        state=state,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"email_id": "e-2"}


def test_archive_ticket_sets_archived_status_distinct_from_closed() -> None:
    state = {
        "docs": {},
        "accounts": {},
        "emails": {},
        "tickets": {"T-1": {"title": "A", "priority": "low", "status": "open"}},
    }

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="archive_ticket",
        arguments={"ticket_id": "T-1"},
        state=state,
    )

    assert isinstance(outcome, ToolSuccess)
    assert new_state["tickets"]["T-1"]["status"] == "archived"
    assert state["tickets"]["T-1"]["status"] == "open"


def test_archive_unknown_ticket_is_a_business_failure() -> None:
    state = {"docs": {}, "accounts": {}, "emails": {}, "tickets": {}}

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="archive_ticket",
        arguments={"ticket_id": "T-99"},
        state=state,
    )

    assert new_state == state
    assert isinstance(outcome, ToolFailure)
    assert "T-99" in outcome.error


def test_find_account_returns_candidate_user_ids_no_mutation() -> None:
    state = {
        "docs": {},
        "tickets": {},
        "emails": {},
        "accounts": {
            "u-1": {
                "name": "Ada",
                "email": "ada@example.com",
                "plan": "pro",
                "tickets": [],
                "created": "2025-11-01",
            },
            "u-2": {
                "name": "Grace",
                "email": "ada@example.com",
                "plan": "free",
                "tickets": [],
                "created": "2025-10-01",
            },
        },
    }

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="find_account",
        arguments={"email": "ada@example.com"},
        state=state,
    )

    assert new_state == state
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"candidates": ["u-1", "u-2"]}


def test_find_account_no_match_returns_empty_candidates() -> None:
    state = {"docs": {}, "tickets": {}, "emails": {}, "accounts": {}}

    _, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="find_account",
        arguments={"email": "nobody@example.com"},
        state=state,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"candidates": []}


def test_draft_email_appends_draft_state_not_sent() -> None:
    state = {"docs": {}, "tickets": {}, "accounts": {}, "emails": {}}

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="draft_email",
        arguments={"to": "ada@example.com", "subject": "Hi", "body": "Draft."},
        state=state,
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"email_id": "e-1"}
    assert new_state["emails"]["e-1"]["state"] == "draft"
    assert state["emails"] == {}
