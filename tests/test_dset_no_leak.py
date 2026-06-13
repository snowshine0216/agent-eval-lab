"""D19 no-leak gate: evaluator-only answer-specific values are absent from the
candidate-visible prompt and tool surface.

The no-leak invariant: the grading oracle must not give the candidate
the answer. The key distinction:
  - Questions legitimately NAME the components they ask about (the question
    "tell me about Management Console" obviously contains "Management Console").
    These are not leaks.
  - Answer-specific VALUES (version numbers, namespace assignments not in the
    question) must not be in the candidate's context.

Check: for each task, fact-keys that do NOT appear in that task's user-turn
question text (the "answer-specific" ones) must not appear in the system
prompt (the shared candidate context). Version numbers like "1.34" and
"Managed Redis 7" are the primary targets.
"""

import json
from pathlib import Path

import pytest

from agent_eval_lab.datasets.cmc_dset import build_cmc_tasks
from agent_eval_lab.tools.browse import BROWSE_TOOLS

_STORE = Path("evaluator-only")
_QUESTIONS = Path("examples/datasets/cmc-docs-questions.txt")

requires_store = pytest.mark.skipif(
    not (_STORE / "cmc-docs-factkeys.json").exists(),
    reason="evaluator-only store absent (candidate checkout / offline)",
)


@requires_store
def test_answer_values_absent_from_system_prompt():
    """Answer-specific tokens that do NOT appear in the question text must
    not appear in the shared system prompt. D19: the system prompt is what
    leaks oracle information since it is shared across all task runs.

    Keys that appear in the question's OWN user turn are legitimately
    there (the question names what it's asking about); we skip those.
    Keys that are absent from the user turn are purely answer-specific
    and must not be in the system prompt.
    """
    from agent_eval_lab.records.turns import MessageTurn

    data = json.loads((_STORE / "cmc-docs-factkeys.json").read_text())
    tasks = build_cmc_tasks(evaluator_store=_STORE, questions_path=_QUESTIONS)

    # The system prompt is shared; get it from the first task
    system_content = next(
        m.content for m in tasks[0].input.messages
        if isinstance(m, MessageTurn) and m.role == "system"
    ).lower()

    leaks = []
    for task, q in zip(tasks, data["questions"]):
        # Get this task's user-turn (the actual question text)
        user_content = next(
            m.content for m in task.input.messages
            if isinstance(m, MessageTurn) and m.role == "user"
        ).lower()
        # Check keys that are NOT in the question text (these are answer-specific)
        for key in (*q["required"], *q["forbidden"]):
            if key.lower() in user_content:
                # This key is named in the question — not a leak, skip
                continue
            # Answer-specific key: must not appear in the system prompt
            if key.lower() in system_content:
                leaks.append(f"{q['id']}: answer-specific key {key!r} in system prompt")

    assert not leaks, "\n".join(leaks)


@requires_store
def test_critical_answer_values_not_in_any_task_system_prompt():
    """Specific high-value answer tokens — version numbers and specific
    technical values — must not appear in the system prompt. D19 smoke check."""
    from agent_eval_lab.records.turns import MessageTurn

    tasks = build_cmc_tasks(evaluator_store=_STORE, questions_path=_QUESTIONS)
    system_content = next(
        m.content for m in tasks[0].input.messages
        if isinstance(m, MessageTurn) and m.role == "system"
    ).lower()
    # These are answer-specific values that MUST NOT be in the system prompt
    assert "managed redis 7" not in system_content, "managed redis 7 in system prompt"
    assert "calico 3.29" not in system_content, "calico 3.29 in system prompt"
    assert "1.34" not in system_content, "1.34 in system prompt"


def test_bash_tool_surface_exposes_no_answer():
    # the only tool is bash; its description must not name a snapshot/answer path
    desc = BROWSE_TOOLS["bash"].description.lower()
    assert "evaluator-only" not in desc
    assert "factkey" not in desc
    assert "answer" not in desc


def test_evaluator_store_is_gitignored():
    # D33: the store is gitignored (commit guard); permission-isolation is an
    # ops concern, but the commit guard is testable here.
    import subprocess
    out = subprocess.run(
        ["git", "check-ignore", "evaluator-only/cmc-docs-factkeys.json"],
        capture_output=True, text=True,
    )
    assert out.returncode == 0  # the path IS ignored
