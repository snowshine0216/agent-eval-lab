"""Pure: bound the tool-result text fed back to the provider (context-length safety).

The browse agent (D/B set) accumulates large page-text dumps as ToolResultTurns; over
many rounds the cumulative tool-result content can exceed a model's context window —
observed as a SiliconFlow HTTP 400 on GLM-5.1 mid-D-run, which aborted the whole run.

trim_tool_result_history trims what is SENT to the provider: the newest tool result is
always kept (the model needs the latest browse output to act this round); older tool
results are kept while their cumulative size stays within a character budget, then
replaced with a short elision marker. Non-tool turns are never touched.

This affects ONLY what the model sees, never what is recorded or graded — the D-set
fact-key grader reads the final assistant message and the evaluator-frozen snapshot,
not the browse dumps (graders/fact_key.py). Pure, deterministic (newest-first greedy)
and idempotent.
"""

from collections.abc import Sequence

from agent_eval_lab.records.turns import ToolResultTurn, ToolSuccess, Turn
from agent_eval_lab.runners.wire import turn_to_message

DEFAULT_TOOL_RESULT_CHAR_BUDGET = 24000
ELISION_MARKER = "[earlier tool output elided to bound context]"
_ELIDED_RESULT = {"elided": ELISION_MARKER}


def _result_size(turn: ToolResultTurn) -> int:
    """Size of the rendered wire content for this tool result (what the model sees)."""
    return len(turn_to_message(turn)["content"])


def _elide(turn: ToolResultTurn) -> ToolResultTurn:
    return ToolResultTurn(
        call_id=turn.call_id, outcome=ToolSuccess(result=_ELIDED_RESULT)
    )


def trim_tool_result_history(
    turns: Sequence[Turn], *, char_budget: int = DEFAULT_TOOL_RESULT_CHAR_BUDGET
) -> tuple[Turn, ...]:
    """Return turns with older ToolResultTurn contents elided to bound total context.

    Walks newest-first: the newest tool result is always kept in full; each older tool
    result is kept while the running total of kept tool-result sizes stays within
    char_budget, otherwise its content is replaced with a short elision marker. Already
    elided turns stay elided (idempotent). Non-tool turns pass through unchanged.
    """
    out = list(turns)
    seen = 0
    cumulative = 0
    for i in range(len(out) - 1, -1, -1):
        turn = out[i]
        if not isinstance(turn, ToolResultTurn):
            continue
        seen += 1
        size = _result_size(turn)
        if seen == 1:  # newest tool result is always kept, and counts toward the budget
            cumulative = size
            continue
        if cumulative + size <= char_budget:
            cumulative += size
        else:
            out[i] = _elide(turn)
    return tuple(out)
