from agent_eval_lab.tasks.turns import ToolFailure, ToolSuccess
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS, apply, initial_state


def test_tool_schemas_cover_the_three_tools():
    assert set(TOOL_SCHEMAS) == {"search_docs", "create_ticket", "update_ticket"}


def test_create_ticket_valid_returns_success_and_new_state():
    state = initial_state()
    new_state, outcome = apply(
        "create_ticket", {"title": "Bug", "priority": "high"}, state
    )
    assert isinstance(outcome, ToolSuccess)
    ticket_id = outcome.result["ticket_id"]
    assert new_state["tickets"][ticket_id] == {
        "title": "Bug",
        "priority": "high",
        "status": "open",
    }
    # original state is untouched (pure, copy-on-write)
    assert state["tickets"] == {}


def test_create_ticket_schema_invalid_returns_failure_no_mutation():
    state = initial_state()
    new_state, outcome = apply(
        "create_ticket", {"title": "Bug", "priority": "urgent"}, state
    )
    assert isinstance(outcome, ToolFailure)
    assert new_state == state  # unchanged
    assert state["tickets"] == {}


def test_create_ticket_type_coercion_is_failure():
    state = initial_state()
    _, outcome = apply("create_ticket", {"title": 1, "priority": "low"}, state)
    assert isinstance(outcome, ToolFailure)


def test_update_ticket_valid_changes_status():
    state = initial_state()
    state, created = apply("create_ticket", {"title": "x", "priority": "low"}, state)
    tid = created.result["ticket_id"]
    new_state, outcome = apply(
        "update_ticket", {"ticket_id": tid, "status": "closed"}, state
    )
    assert isinstance(outcome, ToolSuccess)
    assert new_state["tickets"][tid]["status"] == "closed"


def test_update_ticket_unknown_id_returns_failure():
    state = initial_state()
    new_state, outcome = apply(
        "update_ticket", {"ticket_id": "T-404", "status": "closed"}, state
    )
    assert isinstance(outcome, ToolFailure)
    assert new_state == state


def test_search_docs_returns_matches_without_mutation():
    state = initial_state()
    new_state, outcome = apply("search_docs", {"query": "install"}, state)
    assert isinstance(outcome, ToolSuccess)
    assert new_state == state


def test_unknown_tool_returns_failure():
    state = initial_state()
    _, outcome = apply("delete_everything", {}, state)
    assert isinstance(outcome, ToolFailure)


def test_apply_does_not_mutate_argument_dict():
    state = initial_state()
    args = {"title": "x", "priority": "low"}
    apply("create_ticket", args, state)
    assert args == {"title": "x", "priority": "low"}
