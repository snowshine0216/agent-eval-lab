"""workspace-world: deterministic tools over explicit in-memory state.

Each tool is two things: a JSON schema (fed to the model) and a pure
implementation. `apply` validates arguments against the schema and returns a
ToolFailure on violation — exactly as a real API returns 400.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.records.turns import ToolFailure, ToolOutcome, ToolSuccess
from agent_eval_lab.tools.validation import validate_args

State = Mapping[str, Any]


@dataclass(frozen=True, kw_only=True)
class ToolDef:
    name: str
    description: str
    parameters: Mapping[str, Any]


WORKSPACE_TOOLS: Mapping[str, ToolDef] = {
    "search_docs": ToolDef(
        name="search_docs",
        description="Search the documentation; returns matching doc ids.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 1}},
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    "create_ticket": ToolDef(
        name="create_ticket",
        description="Create a support ticket; returns the new ticket id.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["title", "priority"],
            "additionalProperties": False,
        },
    ),
    "update_ticket": ToolDef(
        name="update_ticket",
        description="Set the status of an existing ticket.",
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "status": {"type": "string", "enum": ["open", "closed"]},
            },
            "required": ["ticket_id", "status"],
            "additionalProperties": False,
        },
    ),
}


def _search_docs(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    query = args["query"].lower()
    docs = state.get("docs", {})
    hits = sorted(
        doc_id
        for doc_id, doc in docs.items()
        if query in doc["title"].lower() or query in doc["body"].lower()
    )
    return state, ToolSuccess(result={"doc_ids": hits})


def _next_ticket_id(tickets: Mapping[str, Any]) -> str:
    numbers = [
        int(ticket_id.split("-")[1])
        for ticket_id in tickets
        if ticket_id.startswith("T-") and ticket_id.split("-")[1].isdigit()
    ]
    return f"T-{max(numbers, default=0) + 1}"


def _create_ticket(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    tickets = state.get("tickets", {})
    ticket_id = _next_ticket_id(tickets)
    ticket = {"title": args["title"], "priority": args["priority"], "status": "open"}
    new_state = {**state, "tickets": {**tickets, ticket_id: ticket}}
    return new_state, ToolSuccess(result={"ticket_id": ticket_id})


def _update_ticket(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    tickets = state.get("tickets", {})
    ticket_id = args["ticket_id"]
    if ticket_id not in tickets:
        return state, ToolFailure(error=f"unknown ticket_id: {ticket_id}")
    updated = {**tickets[ticket_id], "status": args["status"]}
    new_state = {**state, "tickets": {**tickets, ticket_id: updated}}
    return new_state, ToolSuccess(
        result={"ticket_id": ticket_id, "status": args["status"]}
    )


_IMPLS: Mapping[
    str, Callable[[Mapping[str, Any], State], tuple[State, ToolOutcome]]
] = {
    "search_docs": _search_docs,
    "create_ticket": _create_ticket,
    "update_ticket": _update_ticket,
}


def apply(
    *,
    registry: Mapping[str, ToolDef],
    name: str,
    arguments: Mapping[str, Any],
    state: State,
) -> tuple[State, ToolOutcome]:
    """Pure tool application: validates args, threads state explicitly."""
    tool = registry.get(name)
    if tool is None:
        return state, ToolFailure(error=f"unknown tool: {name}")
    error = validate_args(tool.parameters, arguments)
    if error is not None:
        return state, ToolFailure(error=f"schema violation: {error}")
    return _IMPLS[name](arguments, state)
