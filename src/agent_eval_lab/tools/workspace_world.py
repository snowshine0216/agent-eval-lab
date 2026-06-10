"""Synthetic workspace-world: 3 schema-validated tools over {tickets, docs}.

Each tool is a JSON schema (fed to the model as available_tools) and a pure
branch of apply(tool, args, state) -> (state', outcome). Schema validation runs
at this boundary (design §5): a violation returns ToolFailure exactly as a real
API returns 400, and state is never silently repaired.
"""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.tasks.turns import ToolFailure, ToolOutcome, ToolSuccess
from agent_eval_lab.tools.jsonschema_mini import validate

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_docs": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    },
    "create_ticket": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["title", "priority"],
        "additionalProperties": False,
    },
    "update_ticket": {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string"},
            "status": {"type": "string", "enum": ["open", "closed"]},
        },
        "required": ["ticket_id", "status"],
        "additionalProperties": False,
    },
}

_DOCS = {
    "install": "Run `uv sync` then `uv run pytest`.",
    "deploy": "Push to main; CI ships the artifact.",
}


def initial_state() -> dict[str, Any]:
    """A fresh, empty world state."""
    return {"tickets": {}, "docs": dict(_DOCS)}


def _next_ticket_id(tickets: Mapping[str, Any]) -> str:
    return f"T-{len(tickets) + 1}"


def _search_docs(
    args: Mapping[str, Any], state: Mapping[str, Any]
) -> tuple[dict, ToolOutcome]:
    query = args["query"].lower()
    hits = [k for k, v in state["docs"].items() if query in k or query in v.lower()]
    return dict(state), ToolSuccess(result={"matches": hits})


def _create_ticket(
    args: Mapping[str, Any], state: Mapping[str, Any]
) -> tuple[dict, ToolOutcome]:
    tickets = dict(state["tickets"])
    ticket_id = _next_ticket_id(tickets)
    tickets[ticket_id] = {
        "title": args["title"],
        "priority": args["priority"],
        "status": "open",
    }
    return {**state, "tickets": tickets}, ToolSuccess(result={"ticket_id": ticket_id})


def _update_ticket(
    args: Mapping[str, Any], state: Mapping[str, Any]
) -> tuple[dict, ToolOutcome]:
    ticket_id = args["ticket_id"]
    if ticket_id not in state["tickets"]:
        return dict(state), ToolFailure(error=f"unknown ticket {ticket_id}")
    tickets = dict(state["tickets"])
    tickets[ticket_id] = {**tickets[ticket_id], "status": args["status"]}
    return {**state, "tickets": tickets}, ToolSuccess(result={"ticket_id": ticket_id})


_HANDLERS = {
    "search_docs": _search_docs,
    "create_ticket": _create_ticket,
    "update_ticket": _update_ticket,
}


def apply(
    tool: str, args: Mapping[str, Any], state: Mapping[str, Any]
) -> tuple[dict[str, Any], ToolOutcome]:
    """Pure tool application. Validates args at the boundary; never mutates inputs."""
    if tool not in TOOL_SCHEMAS:
        return dict(state), ToolFailure(error=f"unknown tool {tool}")
    errors = validate(dict(args), TOOL_SCHEMAS[tool])
    if errors:
        return dict(state), ToolFailure(error="; ".join(errors))
    return _HANDLERS[tool](args, state)
