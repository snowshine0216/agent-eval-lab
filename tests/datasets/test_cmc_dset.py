import hashlib
import json
import re
from pathlib import Path

import pytest

from agent_eval_lab.datasets.cmc_dset import (
    CMC_SOURCE_URL,
    build_cmc_tasks,
    load_questions,
)
from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import AllOf, FactKeySpec

_QUESTIONS = Path("examples/datasets/cmc-docs-questions.txt")
_STORE = Path("evaluator-only")

requires_store = pytest.mark.skipif(
    not (_STORE / "cmc-docs-factkeys.json").exists(),
    reason="evaluator-only fact-key store not present (offline / candidate checkout)",
)


def test_load_questions_returns_15_nonempty():
    qs = load_questions(_QUESTIONS)
    assert len(qs) == 15
    assert all(q.strip() for q in qs)


@requires_store
def test_build_cmc_tasks_makes_15_domain_D_tasks():
    tasks = build_cmc_tasks(evaluator_store=_STORE, questions_path=_QUESTIONS)
    assert len(tasks) == 15
    for t in tasks:
        assert t.capability == "docs_qa"
        assert t.input.available_tools == ("bash",)
        # the question text is in the user turn; the URL is in the system turn
        assert any(
            CMC_SOURCE_URL in m.content
            for m in t.input.messages if isinstance(m, MessageTurn)
        )


@requires_store
def test_l1_l3_tasks_are_factkey_l4_l5_are_allof_with_judge_stub():
    tasks = build_cmc_tasks(evaluator_store=_STORE, questions_path=_QUESTIONS)
    for t in tasks:
        # task ids: cmc-q01..cmc-q15; questions 1-9 are L1-L3
        n = int(t.id.split("-q")[1])  # cmc-q07 -> 7
        if n <= 9:  # L1-L3 (questions 1-9)
            assert isinstance(t.verification, FactKeySpec), \
                f"{t.id} expected FactKeySpec, got {type(t.verification)}"
        else:       # L4-L5 (questions 10-15)
            assert isinstance(t.verification, AllOf), \
                f"{t.id} expected AllOf, got {type(t.verification)}"


@requires_store
def test_every_factkey_required_is_on_the_snapshot():
    # The authoring faithfulness invariant: no required key is off-page, and no
    # forbidden key is on-page (a mis-authored contradiction).
    data = json.loads((_STORE / "cmc-docs-factkeys.json").read_text())
    snap = (_STORE / data["snapshot_file"]).read_text()
    assert hashlib.sha256(snap.encode()).hexdigest() == data["snapshot_sha256"]
    low = " ".join(snap.lower().split())
    for q in data["questions"]:
        for k in q["required"]:
            assert " ".join(k.lower().split()) in low, (
                f"{q['id']} required off-page: {k}"
            )
        for k in q["forbidden"]:
            assert " ".join(k.lower().split()) not in low, (
                f"{q['id']} forbidden on-page: {k}"
            )


@requires_store
def test_golden_answers_pass_their_own_factkey_oracle():
    # Round-trip: the owner answer-key text grades PASS against its fact-keys
    # (so the oracle is not impossibly strict). Answers come from the eval store.
    answers = _load_answer_key(_STORE / "cmc-docs-answers.txt")
    tasks = build_cmc_tasks(evaluator_store=_STORE, questions_path=_QUESTIONS)
    for t in tasks:
        if not isinstance(t.verification, FactKeySpec):
            continue
        ans = answers[t.id]
        traj = Trajectory(
            turns=(MessageTurn(role="assistant", content=ans),),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0, stop_reason="completed_natural",
        )
        g = grade_trajectory(verification=t.verification, trajectory=traj, registry={})
        assert g.passed, f"{t.id} golden answer failed its own oracle: {g.evidence}"


def _load_answer_key(path: Path) -> dict[str, str]:
    """Parse evaluator-only/cmc-docs-answers.txt into {cmc-qNN: answer_text}."""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^\s*(\d+)\.", text)
    result: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1].strip()
        result[f"cmc-q{num:02d}"] = body
    return result
