"""Assemble the 15 D-set Tasks (§4.2): each candidate-visible CMC question paired
with its evaluator-only fact-key oracle.

Mirrors datasets/f3_oracle.py: the candidate-visible QUESTION text is read from
the committed examples/datasets/cmc-docs-questions.txt; the ORACLE (fact-keys +
page snapshot) is read from the permission-isolated evaluator store (D19/D33).
Nothing here writes a fact-key into a candidate-visible location.

L1-L3 (questions 1-9) -> a FactKeySpec (deterministic headline).
L4-L5 (questions 10-15) -> an AllOf(FactKeySpec floor, LlmJudgeSpec STUB) — the
fact-key floor is deterministic; the judge stub is reported, never the headline
(DEC-6 / §4.2 / §6). The stub is clearly marked judge_model="(stub-uncalibrated)".
"""

import json
import os
import re
from pathlib import Path

from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import (
    AllOf,
    FactKeySpec,
    LlmJudgeSpec,
    Task,
    TaskInput,
    TaskMetadata,
)

# The internal docs host is NOT hardcoded in tracked source (it would leak to a
# public repo). The real URL is supplied at runtime via the CMC_DOCS_URL env var
# (loaded from the gitignored .env / evaluator config); the placeholder default
# keeps the eval inert until configured.
CMC_SOURCE_URL = os.environ.get(
    "CMC_DOCS_URL", "http://<CMC_DOCS_HOST>/docs/24.12/Introduction.html"
)
_FACTKEYS_REL = "cmc-docs-factkeys.json"

_SYSTEM = (
    "You are answering documentation questions about Strategy Customer Managed "
    "Cloud (CMC). You have a single tool: `bash`. Use it to drive a headless "
    "browser via playwright-cli. Start a session and open the docs, e.g.:\n"
    f"  playwright-cli -s=$SESSION open {CMC_SOURCE_URL}\n"
    "  playwright-cli -s=$SESSION eval \"() => document.body.innerText\"\n"
    "Reuse the same -s=$SESSION id across commands. Read the page, then answer "
    "the question using ONLY information found in the documentation. Give your "
    "final answer as a plain-text message (no tool call)."
)


def load_questions(path: Path) -> tuple[str, ...]:
    """Parse the 15 numbered questions from the candidate-visible questions file.

    Questions are top-level numbered items `N. ...`; sub-bullets and level
    headers are folded into the preceding question's text.
    """
    text = path.read_text(encoding="utf-8")
    # Split on lines that start a top-level numbered question: "1. ", "2. ", ...
    parts = re.split(r"(?m)^\s*(\d+)\.\s", text)
    # parts = [preamble, "1", q1, "2", q2, ...]
    questions: list[str] = []
    for i in range(1, len(parts), 2):
        body = parts[i + 1].strip()
        # stop the body at the next Level header if one bled in
        body = re.split(r"(?m)^\s*Level \d", body)[0].strip()
        questions.append(body)
    if len(questions) != 15:
        raise ValueError(f"expected 15 questions, parsed {len(questions)}")
    return tuple(questions)


def _factkey_spec(entry: dict, snapshot: str, sha: str) -> FactKeySpec:
    return FactKeySpec(
        required=tuple(entry["required"]),
        forbidden=tuple(entry["forbidden"]),
        page_snapshot=snapshot,
        page_snapshot_sha256=sha,
        level=entry["level"],
    )


def _judge_stub(level: int) -> LlmJudgeSpec:
    return LlmJudgeSpec(
        rubric=(
            "Score 1-5 the quality of this CMC documentation answer: coverage of "
            "the relevant page sections, internal consistency, and whether claims "
            "are grounded in the docs. (UNCALIBRATED STUB — reported only.)"
        ),
        judge_model="(stub-uncalibrated)",
        scale=(1, 5),
    )


def build_cmc_tasks(*, evaluator_store: Path, questions_path: Path) -> tuple[Task, ...]:
    questions = load_questions(questions_path)
    data = json.loads((evaluator_store / _FACTKEYS_REL).read_text(encoding="utf-8"))
    snapshot = (evaluator_store / data["snapshot_file"]).read_text(encoding="utf-8")
    sha = data["snapshot_sha256"]
    entries = data["questions"]
    if len(entries) != 15:
        raise ValueError(f"expected 15 fact-key entries, got {len(entries)}")

    tasks: list[Task] = []
    for n, (question, entry) in enumerate(zip(questions, entries), start=1):
        floor = _factkey_spec(entry, snapshot, sha)
        verification = (
            floor if n <= 9 else AllOf(specs=(floor, _judge_stub(entry["level"])))
        )
        tasks.append(
            Task(
                id=f"cmc-q{n:02d}",
                capability="docs_qa",
                input=TaskInput(
                    messages=(
                        MessageTurn(role="system", content=_SYSTEM),
                        MessageTurn(role="user", content=question),
                    ),
                    available_tools=("bash",),
                ),
                verification=verification,
                metadata=TaskMetadata(
                    split="held_out",
                    version="cmc-dset-v1",
                    provenance="examples/datasets/cmc-docs-questions.txt",
                    difficulty_knob=f"L{entry['level']}",
                ),
            )
        )
    return tuple(tasks)
