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
    "get_account": ToolDef(
        name="get_account",
        description="Look up an account by its exact user_id; returns the account.",
        parameters={
            "type": "object",
            "properties": {"user_id": {"type": "string", "minLength": 1}},
            "required": ["user_id"],
            "additionalProperties": False,
        },
    ),
    "list_tickets": ToolDef(
        name="list_tickets",
        description=(
            "List tickets, optionally filtered by status, assignee, or priority; "
            "returns matching ticket ids and their fields."
        ),
        parameters={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["open", "closed", "archived"]},
                "assignee": {"type": "string", "minLength": 1},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": [],
            "additionalProperties": False,
        },
    ),
    "send_email": ToolDef(
        name="send_email",
        description="Send an email; appends a sent email and returns its id.",
        parameters={
            "type": "object",
            "properties": {
                "to": {"type": "string", "minLength": 1},
                "subject": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            },
            "required": ["to", "subject", "body"],
            "additionalProperties": False,
        },
    ),
    "archive_ticket": ToolDef(
        name="archive_ticket",
        description="Archive a ticket (sets status to archived).",
        parameters={
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
            "additionalProperties": False,
        },
    ),
    "find_account": ToolDef(
        name="find_account",
        description="Search accounts by email; returns candidate user_ids.",
        parameters={
            "type": "object",
            "properties": {"email": {"type": "string", "minLength": 1}},
            "required": ["email"],
            "additionalProperties": False,
        },
    ),
    "draft_email": ToolDef(
        name="draft_email",
        description="Stage a draft email (does NOT send); appends a draft.",
        parameters={
            "type": "object",
            "properties": {
                "to": {"type": "string", "minLength": 1},
                "subject": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            },
            "required": ["to", "subject", "body"],
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


def _next_email_id(emails: Mapping[str, Any]) -> str:
    numbers = [
        int(email_id.split("-")[1])
        for email_id in emails
        if email_id.startswith("e-") and email_id.split("-")[1].isdigit()
    ]
    return f"e-{max(numbers, default=0) + 1}"


def _get_account(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    accounts = state.get("accounts", {})
    user_id = args["user_id"]
    account = accounts.get(user_id)
    if account is None:
        return state, ToolFailure(error=f"unknown user_id: {user_id}")
    return state, ToolSuccess(result={"user_id": user_id, **account})


def _list_tickets(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    tickets = state.get("tickets", {})
    status = args.get("status")
    assignee = args.get("assignee")
    priority = args.get("priority")
    matched = {
        ticket_id: ticket
        for ticket_id, ticket in tickets.items()
        if (status is None or ticket.get("status") == status)
        and (assignee is None or ticket.get("assignee") == assignee)
        and (priority is None or ticket.get("priority") == priority)
    }
    return state, ToolSuccess(
        result={"ticket_ids": sorted(matched), "tickets": matched}
    )


def _send_email(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    emails = state.get("emails", {})
    email_id = _next_email_id(emails)
    email = {
        "to": args["to"],
        "subject": args["subject"],
        "body": args["body"],
        "state": "sent",
    }
    new_state = {**state, "emails": {**emails, email_id: email}}
    return new_state, ToolSuccess(result={"email_id": email_id})


def _archive_ticket(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    tickets = state.get("tickets", {})
    ticket_id = args["ticket_id"]
    if ticket_id not in tickets:
        return state, ToolFailure(error=f"unknown ticket_id: {ticket_id}")
    updated = {**tickets[ticket_id], "status": "archived"}
    new_state = {**state, "tickets": {**tickets, ticket_id: updated}}
    return new_state, ToolSuccess(result={"ticket_id": ticket_id, "status": "archived"})


def _find_account(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    accounts = state.get("accounts", {})
    email = args["email"]
    candidates = sorted(
        user_id
        for user_id, account in accounts.items()
        if account.get("email") == email
    )
    return state, ToolSuccess(result={"candidates": candidates})


def _draft_email(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    emails = state.get("emails", {})
    email_id = _next_email_id(emails)
    email = {
        "to": args["to"],
        "subject": args["subject"],
        "body": args["body"],
        "state": "draft",
    }
    new_state = {**state, "emails": {**emails, email_id: email}}
    return new_state, ToolSuccess(result={"email_id": email_id})


_IMPLS: Mapping[
    str, Callable[[Mapping[str, Any], State], tuple[State, ToolOutcome]]
] = {
    "search_docs": _search_docs,
    "create_ticket": _create_ticket,
    "update_ticket": _update_ticket,
    "get_account": _get_account,
    "list_tickets": _list_tickets,
    "send_email": _send_email,
    "archive_ticket": _archive_ticket,
    "find_account": _find_account,
    "draft_email": _draft_email,
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
    impl = _IMPLS.get(name)
    if impl is None:
        raise RuntimeError(
            f"harness misconfiguration: tool {name!r} is registered but has no "
            "implementation"
        )
    return impl(arguments, state)
