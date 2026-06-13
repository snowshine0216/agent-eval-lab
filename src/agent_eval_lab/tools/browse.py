"""browse-world: the single `bash` tool (§18.10) for the D/B-set agent.

The candidate gets exactly one tool — `bash` — and drives playwright-cli (and,
for the B/F sets, repo operations) through it. `apply_browse` is pure: it
validates the command argument against the schema and returns a BashRequest
effect-request (ADR-0008) that the loop fulfils at the bash edge. The pure layer
never runs a subprocess; all I/O lives in runners/bash_edge.py.
"""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.bash import BashRequest
from agent_eval_lab.records.turns import ToolFailure, ToolOutcome
from agent_eval_lab.tools.validation import validate_args
from agent_eval_lab.tools.workspace import ToolDef

BROWSE_TOOLS: Mapping[str, ToolDef] = {
    "bash": ToolDef(
        name="bash",
        description=(
            "Run a single shell command and return its stdout, stderr, and exit "
            "code. Use this to drive playwright-cli (a headless browser) — e.g. "
            "`playwright-cli -s=<session> open <url>`, then "
            "`playwright-cli -s=<session> eval \"() => document.body.innerText\"`. "
            "Reuse the same -s=<session> id across commands to keep one browser "
            "session. Each command has a time limit; output is truncated if large."
        ),
        parameters={
            "type": "object",
            "properties": {"command": {"type": "string", "minLength": 1}},
            "required": ["command"],
            "additionalProperties": False,
        },
    ),
}


def apply_browse(
    *,
    registry: Mapping[str, ToolDef],
    name: str,
    arguments: Mapping[str, Any],
    state: Mapping[str, Any],
) -> tuple[Mapping[str, Any], "BashRequest | ToolOutcome"]:
    """Pure tool application: validate args, return a BashRequest effect-request.

    State is threaded through unchanged (the effect happens at the edge).
    """
    tool = registry.get(name)
    if tool is None:
        return state, ToolFailure(error=f"unknown tool: {name}")
    error = validate_args(tool.parameters, arguments)
    if error is not None:
        return state, ToolFailure(error=f"schema violation: {error}")
    if name == "bash":
        return state, BashRequest(command=arguments["command"])
    raise RuntimeError(
        f"harness misconfiguration: tool {name!r} is registered but has no impl"
    )
