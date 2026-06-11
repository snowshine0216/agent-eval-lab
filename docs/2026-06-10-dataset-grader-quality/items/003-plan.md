# Model-based grader (`LlmJudgeSpec`) + calibration harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Tier-3 `LlmJudgeSpec` summary-fidelity grader (pure prompt build + parse, single provider call at one edge, verdicts threaded into the pure grader as immutable data) and the calibration harness (blind annotation packet, pure Cohen's κ + bootstrap CI, runbook, and a clearly-PROVISIONAL two-LLM-annotator run).

**Architecture:** The edge pre-computes a `JudgeVerdict` per reachable `LlmJudgeSpec` and threads an immutable `verdicts` mapping into the pure `grade_trajectory`/`grade_all_of` — exactly the `final_state` precedent (ADR 0005). The headline reliability statistic is **binary** Cohen's κ at `score >= 4` with a seeded percentile bootstrap CI; quadratic-weighted κ is a secondary descriptive number (ADR 0006). Judge failures are explicit sum types (`JudgeParseFailure` pure / `JudgeError` edge), mirroring `ToolOutcome`/`ParseFailure` — never coerced into a pass or a policy breach.

**Tech Stack:** Python 3.12, frozen `kw_only` dataclasses, `httpx.MockTransport` for edge tests, stdlib only for κ/bootstrap/hashing (`statistics`, `hashlib`, `json`, `random` with explicit seed). No `scipy`/`numpy`/`sklearn`. `uv run pytest`, `uv run ruff check/format`.

---

## Binding decisions (from `003-spec.md` "Resolved decisions", ADR 0005/0006)

These are NOT negotiable. Re-read them before each task.

- **D1** — `collect_judge_specs(verification) -> tuple[LlmJudgeSpec, ...]` is a **pure** spec-tree walk (recurses `AllOf` exactly as `grade_all_of` does). `grade_all_of`'s own signature gains `verdicts` and threads it unchanged into every recursive sub-call (precedent: item 001 adding `initial_state`).
- **D2** — `parse_judge_response -> JudgeVerdict | JudgeParseFailure` (pure); `run_judge -> JudgeVerdict | JudgeError` (edge, never lets an exception escape). Verdict-map value type is `JudgeVerdict | JudgeError`. A `JudgeError`/`JudgeParseFailure` at a key, or a **missing** key, ⇒ structured non-pass (`passed=False`, `failure_reason=None`) — never a coerced pass, never a faked policy breach.
- **D3** — `JudgeVerdict` carries `judge_model` + `prompt_hash` (the edge stamps them; it is the only edge→core channel). Judge evidence = `{judge_model, prompt_hash, score, scale, threshold, binary_label, rationale, raw}`.
- **D4** — Verdict key = prompt hash over canonical-JSON rendered messages. `scale` is rendered **into the prompt** so the hash is a faithful interpretation key. Identical prompts dedup to one call.
- **D5** — `score >= 4` ⇒ `passed` (faithful). The cut is defined by the rubric anchors (the 4↔3 boundary is where "a fabrication or material omission" first appears), not a free parameter.
- **D6** — Judge emits a final `SCORE: <int>` line. Parser extracts exactly that and structurally fails on (a) no extractable integer, (b) integer out of `[lo, hi]`, (c) conflicting integers — never clamps/defaults/first-wins-silently. **D6b** — weighted κ needs its own hand-verified ordinal test vector (the 2×2 unweighted vectors do not exercise the weighting).
- **D7** — Percentile bootstrap CI (not BCa), resampling **items**, explicit seed. Degenerate top-level input (a rater uses one category ⇒ `1 - p_e == 0`) ⇒ κ defined as `0.0` with a `degenerate=True` flag, never `ZeroDivisionError`. Degenerate **resamples** take the same κ=0 path AND are **counted and reported** by `kappa_bootstrap_ci`, never silently dropped.
- **D8** — Canonical digest in trajectory order: each `ToolCallTurn` as `name(canonical-JSON args)` (reuse `graders/canonical.py:canonicalize` + `json.dumps(sort_keys=True)`), each paired `ToolResultTurn` with its `ToolSuccess`/`ToolFailure` discriminator (`ok:<result>` / `error:<error>`), then the final assistant message. Result truncation is **out of scope** (fixtures are small).
- **D9** — A fixture **design table** (id, intended anchor 1–5, planted failure type, one-line description) is a required deliverable, committed in the runbook. The intended label lives there and is **never** in the blind packet.
- **D11** — `calibrate` is a **nested** subparser group (`export-packet` / `compute` / `provisional-label`) hanging off the top-level `dest="command"`, coexisting with flat `run-baseline`. Packet JSONL carries `packet_format` + `rubric_version`; `import_packet` rejects a mismatch.
- **D12** — `provisional-label` pre-flights the provider key (`os.environ[config.api_key_env]`) and exits with a documented skip message rather than crashing mid-corpus / writing a partial packet. Absent keys never break CI (the verify gate is pure/stubbed).

---

## Canonical verification gates (run after every task)

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

The suite is **227 green** at the start of this item. Each task adds tests; the count only grows. Every gate must be green before `git commit`. Stay on branch `autodev/dataset-grader-quality-feature`.

---

## File Structure

**Pure core (new):**
- `src/agent_eval_lab/graders/judge.py` — `LlmJudgeSpec` import re-export not needed; holds `JudgeVerdict`, `JudgeParseFailure`, `build_judge_prompt`, `parse_judge_response`, `prompt_hash`, `grade_llm_judge`, `collect_judge_specs`. Pure, no I/O, no http import.
- `src/agent_eval_lab/metrics/agreement.py` — `confusion_matrix`, `observed_agreement`, `expected_agreement`, `cohens_kappa`, `weighted_kappa`, `kappa_bootstrap_ci`, the `KappaResult`/`BootstrapCI` records. Pure, stdlib only.
- `src/agent_eval_lab/calibrate/__init__.py` — empty package marker.
- `src/agent_eval_lab/calibrate/packet.py` — pure: `PacketItem`, `Packet`, `build_packet`, `packet_to_jsonl`, `packet_from_jsonl`, `import_packet`, `compute_agreement`, `render_packet_markdown`, `render_agreement_report`.
- `src/agent_eval_lab/calibrate/provisional.py` — **edge**: `run_provisional_labeling` (routes each fixture through `build_judge_prompt`→`run_judge`→packet), `render_provisional_summary`.

**Edge (new):**
- `src/agent_eval_lab/runners/judge_edge.py` — `JudgeError`, `run_judge`. The only judge I/O.

**Extended:**
- `src/agent_eval_lab/tasks/schema.py` — add `LlmJudgeSpec`; add it to `VerificationSpec` union.
- `src/agent_eval_lab/tasks/parse.py` — parse `type:"llm_judge"`.
- `src/agent_eval_lab/graders/dispatch.py` — `grade_trajectory(..., verdicts=...)` dispatch `LlmJudgeSpec`; thread `verdicts` into `grade_all_of`.
- `src/agent_eval_lab/graders/composite.py` — `grade_all_of(..., verdicts=...)` threaded into recursion.
- `src/agent_eval_lab/cli.py` — nested `calibrate` subparser group + handlers.

**Data / docs (new):**
- `examples/calibration/rubric.md` — the summary-fidelity rubric (the anchored scale verbatim).
- `examples/calibration/fixtures.jsonl` — 16 hand-authored `Trajectory`+`LlmJudgeSpec` fixtures (blind corpus; NO intended labels).
- `examples/calibration/intended_labels.jsonl` — the SEPARATE non-packet intended-label file (D9), keyed by `fixture_id`.
- `docs/2026-06-10-dataset-grader-quality/calibration-runbook.md` — §6 protocol state machine + fixture design table.
- `docs/2026-06-10-dataset-grader-quality/calibration-provisional-summary.md` — committed PROVISIONAL summary (written by the post-green run step).

**Tests (new):**
- `tests/graders/test_judge.py`, `tests/metrics/test_agreement.py`, `tests/calibrate/__init__.py`, `tests/calibrate/test_packet.py`, `tests/calibrate/test_provisional.py`, `tests/runners/test_judge_edge.py`, plus added cases in `tests/tasks/test_parse.py`, `tests/tasks/test_schema.py`, `tests/graders/test_dispatch.py`, `tests/graders/test_composite.py`, `tests/test_cli.py`, and a fixture-conformance test `tests/datasets/test_calibration_fixtures.py`.

---

## The full type set (defined once here; referenced by all tasks)

These are the exact dataclass shapes. Tasks below introduce them test-first; this section is the single source of truth for signatures.

```python
# tasks/schema.py
@dataclass(frozen=True, kw_only=True)
class LlmJudgeSpec:
    type: Literal["llm_judge"] = "llm_judge"
    rubric: str
    judge_model: str
    scale: tuple[int, int] = (1, 5)

# graders/judge.py
@dataclass(frozen=True, kw_only=True)
class JudgeVerdict:
    score: int
    rationale: str
    raw: str
    judge_model: str   # stamped by the edge
    prompt_hash: str   # stamped by the edge

@dataclass(frozen=True, kw_only=True)
class JudgeParseFailure:
    raw: str
    error: str         # one of: "no_score", "out_of_range", "conflicting_scores"

# runners/judge_edge.py
@dataclass(frozen=True, kw_only=True)
class JudgeError:
    kind: Literal["transport", "http", "parse", "empty_response"]
    error: str
    prompt_hash: str
    judge_model: str

# verdict-map value type (threaded into the pure grader)
Verdict = JudgeVerdict | JudgeError
Verdicts = Mapping[str, Verdict]   # keyed by prompt_hash

# metrics/agreement.py
@dataclass(frozen=True, kw_only=True)
class KappaResult:
    kappa: float
    observed_agreement: float
    expected_agreement: float
    degenerate: bool          # True when 1 - p_e == 0 (a rater used one category)

@dataclass(frozen=True, kw_only=True)
class BootstrapCI:
    point: float              # κ on the full sample (KappaResult.kappa)
    lo: float
    hi: float
    alpha: float
    n_resamples: int
    n_degenerate: int         # resamples that hit the degenerate path (D7)
    seed: int

# calibrate/packet.py
PACKET_FORMAT = "calib-packet-v1"
RUBRIC_VERSION = "summary-fidelity-v1"

@dataclass(frozen=True, kw_only=True)
class PacketItem:
    fixture_id: str
    trajectory_digest: str    # the rendered digest a human reads; NO score, NO intended label
    score: int | None         # None on export (blind); filled by the annotator

@dataclass(frozen=True, kw_only=True)
class Packet:
    packet_format: str        # == PACKET_FORMAT
    rubric_version: str        # == RUBRIC_VERSION
    rubric: str               # the anchored scale verbatim (header)
    annotator_id: str | None  # None on export; set when a filled packet is parsed
    items: tuple[PacketItem, ...]   # fixed deterministic order
```

`evidence` for a judge leg (written by `grade_llm_judge`) is the plain dict
`{"judge_model", "prompt_hash", "score", "scale", "threshold", "binary_label", "rationale", "raw"}` on a verdict, or `{"judge": "not_run", ...}` / `{"judge": "error", "kind": ..., "error": ...}` on a missing/error key.

---

## Task 1: `LlmJudgeSpec` in the schema union

**Files:**
- Modify: `src/agent_eval_lab/tasks/schema.py`
- Test: `tests/tasks/test_schema.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tasks/test_schema.py`:

```python
def test_llm_judge_spec_defaults_scale_and_is_in_union() -> None:
    from agent_eval_lab.tasks.schema import LlmJudgeSpec, VerificationSpec

    spec = LlmJudgeSpec(rubric="Score fidelity.", judge_model="deepseek:deepseek-v4-pro")

    assert spec.type == "llm_judge"
    assert spec.scale == (1, 5)
    assert isinstance(spec, VerificationSpec)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tasks/test_schema.py::test_llm_judge_spec_defaults_scale_and_is_in_union -v`
Expected: FAIL — `ImportError: cannot import name 'LlmJudgeSpec'`.

- [ ] **Step 3: Add the dataclass and extend the union**

In `src/agent_eval_lab/tasks/schema.py`, add after the `AllOf` class (before the `VerificationSpec` assignment):

```python
@dataclass(frozen=True, kw_only=True)
class LlmJudgeSpec:
    type: Literal["llm_judge"] = "llm_judge"
    rubric: str
    judge_model: str
    scale: tuple[int, int] = (1, 5)
```

Replace the `VerificationSpec` assignment with:

```python
# Weeks 3-4 deterministic tier + the Tier-3 model-based grader (item 003).
# ExecutionSpec (Weeks 5-6) extends this union later without breaking serialization.
VerificationSpec = (
    OutputMatchSpec
    | ToolCallMatchSpec
    | FinalStateSpec
    | TrajectorySpec
    | AllOf
    | LlmJudgeSpec
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tasks/test_schema.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/tasks/schema.py tests/tasks/test_schema.py
git commit -m "feat(schema): add LlmJudgeSpec to the VerificationSpec union"
```

---

## Task 2: Parse `type:"llm_judge"`

**Files:**
- Modify: `src/agent_eval_lab/tasks/parse.py`
- Test: `tests/tasks/test_parse.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/tasks/test_parse.py`:

```python
def test_parses_llm_judge_with_default_scale() -> None:
    from agent_eval_lab.tasks.parse import verification_from_dict
    from agent_eval_lab.tasks.schema import LlmJudgeSpec

    spec = verification_from_dict(
        {"type": "llm_judge", "rubric": "Score fidelity.", "judge_model": "glm:m"}
    )

    assert spec == LlmJudgeSpec(rubric="Score fidelity.", judge_model="glm:m", scale=(1, 5))


def test_parses_llm_judge_with_explicit_scale() -> None:
    from agent_eval_lab.tasks.parse import verification_from_dict

    spec = verification_from_dict(
        {"type": "llm_judge", "rubric": "r", "judge_model": "m", "scale": [1, 7]}
    )

    assert spec.scale == (1, 7)


def test_llm_judge_rejects_bad_scale() -> None:
    from agent_eval_lab.tasks.parse import verification_from_dict

    for bad in ([5, 1], [1], [1, 2, 3], ["1", "5"]):
        with pytest.raises(ValueError, match="scale"):
            verification_from_dict(
                {"type": "llm_judge", "rubric": "r", "judge_model": "m", "scale": bad}
            )
```

Ensure `import pytest` is present at the top of the file (it is, in the existing test module — verify).

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/tasks/test_parse.py -k llm_judge -v`
Expected: FAIL — `ValueError: unknown verification type: 'llm_judge'`.

- [ ] **Step 3: Implement the parse branch**

In `src/agent_eval_lab/tasks/parse.py`, add `LlmJudgeSpec` to the schema import block, then add this helper above `verification_from_dict`:

```python
def _parse_scale(raw: Any) -> tuple[int, int]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        raise ValueError(f"scale must be a 2-element list, got {raw!r}")
    lo, hi = raw
    if not (isinstance(lo, int) and isinstance(hi, int)) or isinstance(lo, bool) or isinstance(hi, bool):
        raise ValueError(f"scale bounds must be ints, got {raw!r}")
    if lo >= hi:
        raise ValueError(f"scale must have lo < hi, got {raw!r}")
    return (lo, hi)
```

Inside `verification_from_dict`, before the final `raise`, add:

```python
    if kind == "llm_judge":
        return LlmJudgeSpec(
            rubric=data["rubric"],
            judge_model=data["judge_model"],
            scale=_parse_scale(data.get("scale", [1, 5])),
        )
```

(Note: `isinstance(True, int)` is `True` in Python, so the explicit `bool` guard rejects `[true, false]`.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/tasks/test_parse.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/tasks/parse.py tests/tasks/test_parse.py
git commit -m "feat(parse): parse llm_judge verification with validated scale"
```

---

## Task 3: Pure `build_judge_prompt` + `prompt_hash` (determinism)

**Files:**
- Create: `src/agent_eval_lab/graders/judge.py`
- Test: `tests/graders/test_judge.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/graders/test_judge.py`:

```python
from agent_eval_lab.graders.judge import build_judge_prompt, prompt_hash
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.tasks.schema import LlmJudgeSpec


def _trajectory(*turns) -> Trajectory:
    return Trajectory(
        turns=turns,
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
    )


SPEC = LlmJudgeSpec(rubric="Judge summary fidelity.", judge_model="m", scale=(1, 5))

TRAJ = _trajectory(
    MessageTurn(role="user", content="Close ticket T-1 and tell me."),
    ToolCallTurn(
        tool_calls=(
            ToolCall(call_id="c1", name="update_ticket",
                     arguments={"status": "closed", "ticket_id": "T-1"}),
        )
    ),
    ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"ok": True})),
    MessageTurn(role="assistant", content="Done. I closed ticket T-1."),
)


def test_build_judge_prompt_is_deterministic() -> None:
    a = build_judge_prompt(spec=SPEC, trajectory=TRAJ)
    b = build_judge_prompt(spec=SPEC, trajectory=TRAJ)
    assert a == b
    assert prompt_hash(a) == prompt_hash(b)


def test_prompt_renders_scale_and_score_contract() -> None:
    messages = build_judge_prompt(spec=SPEC, trajectory=TRAJ)
    text = "\n".join(m["content"] for m in messages)
    assert "score 1-5" in text or "1-5" in text
    assert "SCORE:" in text
    assert SPEC.rubric in text


def test_prompt_renders_trajectory_in_canonical_order() -> None:
    messages = build_judge_prompt(spec=SPEC, trajectory=TRAJ)
    text = "\n".join(m["content"] for m in messages)
    # tool call args are canonical-JSON sorted: ticket_id before status
    assert 'update_ticket({"ticket_id": "T-1", "status": "closed"})' in text
    assert "ok:" in text  # ToolSuccess discriminator
    assert "Done. I closed ticket T-1." in text


def test_different_scale_changes_prompt_and_hash() -> None:
    other = LlmJudgeSpec(rubric=SPEC.rubric, judge_model="m", scale=(1, 7))
    assert build_judge_prompt(spec=SPEC, trajectory=TRAJ) != build_judge_prompt(
        spec=other, trajectory=TRAJ
    )
    assert prompt_hash(build_judge_prompt(spec=SPEC, trajectory=TRAJ)) != prompt_hash(
        build_judge_prompt(spec=other, trajectory=TRAJ)
    )


def test_failure_outcome_renders_error_discriminator() -> None:
    traj = _trajectory(
        ToolCallTurn(tool_calls=(ToolCall(call_id="c1", name="get_account", arguments={"user_id": "u1"}),)),
        ToolResultTurn(call_id="c1", outcome=ToolFailure(error="not found")),
        MessageTurn(role="assistant", content="I looked it up."),
    )
    text = "\n".join(m["content"] for m in build_judge_prompt(spec=SPEC, trajectory=traj))
    assert "error:not found" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/graders/test_judge.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.graders.judge`.

- [ ] **Step 3: Implement `build_judge_prompt`, `prompt_hash`, and the digest helpers**

Create `src/agent_eval_lab/graders/judge.py`:

```python
"""Pure Tier-3 judge core (ADR 0005): no I/O, deterministic, total.

The edge (runners/judge_edge.run_judge) pre-computes a JudgeVerdict per reachable
LlmJudgeSpec and threads an immutable verdict map keyed by `prompt_hash` into the
pure grader, which only reads it. This module imports no http client; importing
it must never reach the network.
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.graders.canonical import canonicalize
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.tasks.schema import AllOf, LlmJudgeSpec, VerificationSpec

Message = Mapping[str, str]

PASS_THRESHOLD = 4  # D5: score >= 4 => faithful; coupled to the rubric anchors.


@dataclass(frozen=True, kw_only=True)
class JudgeVerdict:
    score: int
    rationale: str
    raw: str
    judge_model: str
    prompt_hash: str


@dataclass(frozen=True, kw_only=True)
class JudgeParseFailure:
    raw: str
    error: str  # "no_score" | "out_of_range" | "conflicting_scores"


def _render_tool_call(turn: ToolCallTurn) -> str:
    parts = []
    for call in turn.tool_calls:
        args = json.dumps(canonicalize(dict(call.arguments)), sort_keys=True)
        parts.append(f"{call.name}({args})")
    return "\n".join(parts)


def _render_tool_result(turn: ToolResultTurn) -> str:
    if isinstance(turn.outcome, ToolSuccess):
        return f"  -> ok:{json.dumps(canonicalize(turn.outcome.result), sort_keys=True)}"
    return f"  -> error:{turn.outcome.error}"


def render_trajectory_digest(trajectory: Trajectory) -> str:
    """Deterministic, canonical rendering of the trajectory in turn order (D8)."""
    lines: list[str] = []
    for turn in trajectory.turns:
        if isinstance(turn, ToolCallTurn):
            lines.append(_render_tool_call(turn))
        elif isinstance(turn, ToolResultTurn):
            lines.append(_render_tool_result(turn))
        elif isinstance(turn, MessageTurn) and turn.role == "user":
            lines.append(f"USER: {turn.content}")
        elif isinstance(turn, MessageTurn) and turn.role == "assistant":
            lines.append(f"ASSISTANT: {turn.content}")
    return "\n".join(lines)


def build_judge_prompt(*, spec: LlmJudgeSpec, trajectory: Trajectory) -> tuple[Message, ...]:
    lo, hi = spec.scale
    system = (
        "You are a strict evaluator. Read the rubric and the agent trajectory, then "
        f"score the agent's final assistant message on an integer scale {lo}-{hi}. "
        "Reply with a one-paragraph rationale, then a final line exactly of the form "
        "'SCORE: <int>'.\n\n"
        f"RUBRIC (score {lo}-{hi}):\n{spec.rubric}"
    )
    user = "TRAJECTORY:\n" + render_trajectory_digest(trajectory)
    return (
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    )


def prompt_hash(messages: tuple[Message, ...]) -> str:
    blob = json.dumps([dict(m) for m in messages], sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

(The remaining functions `parse_judge_response`, `grade_llm_judge`, `collect_judge_specs` arrive in Tasks 4–6, and each adds the imports IT needs — `re` in Task 4, `Any`+`GradeResult` in Task 5, `AllOf`+`VerificationSpec` in Task 6. Do NOT import them in Task 3: ruff flags unused imports, so Task 3 imports exactly what its code uses — the block shown above. `JudgeVerdict` and `JudgeParseFailure` dataclasses ARE defined in Task 3 (Task 4's parser returns them) and are not "unused".)

Concretely, the Task-3 import block is:

```python
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from agent_eval_lab.graders.canonical import canonicalize
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.tasks.schema import LlmJudgeSpec
```

Define `JudgeVerdict` and `JudgeParseFailure` now (Task 4 uses them; defining a dataclass that is exported and tested next task is not "unused").

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/graders/test_judge.py -q`
Expected: PASS (5 tests). Then `uv run ruff check src/agent_eval_lab/graders/judge.py` — must be clean (no unused imports).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/judge.py tests/graders/test_judge.py
git commit -m "feat(judge): deterministic build_judge_prompt + prompt_hash (pure)"
```

---

## Task 4: Pure `parse_judge_response` — `SCORE:` contract + three failure cases

**Files:**
- Modify: `src/agent_eval_lab/graders/judge.py`
- Test: `tests/graders/test_judge.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/graders/test_judge.py`:

```python
from agent_eval_lab.graders.judge import (
    JudgeParseFailure,
    JudgeVerdict,
    parse_judge_response,
)


def test_parses_well_formed_reply() -> None:
    out = parse_judge_response("The summary is faithful.\nSCORE: 5", scale=(1, 5))
    assert isinstance(out, JudgeVerdict)
    assert out.score == 5
    assert out.rationale == "The summary is faithful.\nSCORE: 5"
    assert out.raw == "The summary is faithful.\nSCORE: 5"
    assert out.judge_model == ""   # edge stamps this later
    assert out.prompt_hash == ""


def test_no_extractable_integer_is_no_score() -> None:
    out = parse_judge_response("I cannot score this.", scale=(1, 5))
    assert out == JudgeParseFailure(raw="I cannot score this.", error="no_score")


def test_out_of_range_integer_is_out_of_range() -> None:
    out = parse_judge_response("SCORE: 9", scale=(1, 5))
    assert isinstance(out, JudgeParseFailure)
    assert out.error == "out_of_range"


def test_conflicting_scores_is_conflicting() -> None:
    out = parse_judge_response("SCORE: 4\nSCORE: 2", scale=(1, 5))
    assert isinstance(out, JudgeParseFailure)
    assert out.error == "conflicting_scores"


def test_score_must_be_a_score_line_not_any_integer() -> None:
    # An integer in prose with no SCORE line is no_score, never coerced.
    out = parse_judge_response("The agent made 3 tool calls and was faithful.", scale=(1, 5))
    assert out == JudgeParseFailure(
        raw="The agent made 3 tool calls and was faithful.", error="no_score"
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/graders/test_judge.py -k "parse or score or conflict or range" -v`
Expected: FAIL — `cannot import name 'parse_judge_response'`.

- [ ] **Step 3: Implement `parse_judge_response`**

Add `import re` to the import block. Add to `src/agent_eval_lab/graders/judge.py`:

```python
_SCORE_LINE = re.compile(r"(?mi)^\s*SCORE:\s*([+-]?\d+)\s*$")


def parse_judge_response(text: str, scale: tuple[int, int]) -> "JudgeVerdict | JudgeParseFailure":
    lo, hi = scale
    matches = _SCORE_LINE.findall(text)
    if not matches:
        return JudgeParseFailure(raw=text, error="no_score")
    distinct = {int(m) for m in matches}
    if len(distinct) > 1:
        return JudgeParseFailure(raw=text, error="conflicting_scores")
    score = next(iter(distinct))
    if not (lo <= score <= hi):
        return JudgeParseFailure(raw=text, error="out_of_range")
    return JudgeVerdict(
        score=score, rationale=text, raw=text, judge_model="", prompt_hash=""
    )
```

Note: identical repeated scores (`SCORE: 4` twice) collapse to one distinct value and are NOT conflicting — only genuinely different integers conflict.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/graders/test_judge.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/judge.py tests/graders/test_judge.py
git commit -m "feat(judge): pure parse_judge_response with SCORE contract + 3 failure cases"
```

---

## Task 5: Pure `grade_llm_judge` — reads pre-computed verdict, binarizes at >=4

**Files:**
- Modify: `src/agent_eval_lab/graders/judge.py`
- Test: `tests/graders/test_judge.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/graders/test_judge.py`:

```python
from agent_eval_lab.graders.judge import build_judge_prompt, grade_llm_judge, prompt_hash


def _verdict_for(spec, trajectory, score, *, model="deepseek:deepseek-v4-pro"):
    h = prompt_hash(build_judge_prompt(spec=spec, trajectory=trajectory))
    return h, JudgeVerdict(
        score=score, rationale="r", raw="raw\nSCORE: %d" % score,
        judge_model=model, prompt_hash=h,
    )


def test_grade_passes_at_threshold_4() -> None:
    h, v = _verdict_for(SPEC, TRAJ, 4)
    result = grade_llm_judge(spec=SPEC, trajectory=TRAJ, verdicts={h: v})
    assert result.passed is True
    assert result.grader_id == "llm_judge"
    assert result.failure_reason is None
    ev = result.evidence
    assert ev == {
        "judge_model": "deepseek:deepseek-v4-pro",
        "prompt_hash": h,
        "score": 4,
        "scale": [1, 5],
        "threshold": 4,
        "binary_label": "faithful",
        "rationale": "r",
        "raw": "raw\nSCORE: 4",
    }


def test_grade_fails_below_threshold() -> None:
    h, v = _verdict_for(SPEC, TRAJ, 3)
    result = grade_llm_judge(spec=SPEC, trajectory=TRAJ, verdicts={h: v})
    assert result.passed is False
    assert result.failure_reason is None
    assert result.evidence["binary_label"] == "unfaithful"


def test_grade_missing_verdict_is_judge_not_run() -> None:
    result = grade_llm_judge(spec=SPEC, trajectory=TRAJ, verdicts={})
    assert result.passed is False
    assert result.failure_reason is None
    assert result.evidence["judge"] == "not_run"


def test_grade_judge_error_at_key_is_structured_nonpass() -> None:
    from agent_eval_lab.runners.judge_edge import JudgeError

    h = prompt_hash(build_judge_prompt(spec=SPEC, trajectory=TRAJ))
    err = JudgeError(kind="http", error="500", prompt_hash=h, judge_model="m")
    result = grade_llm_judge(spec=SPEC, trajectory=TRAJ, verdicts={h: err})
    assert result.passed is False
    assert result.failure_reason is None
    assert result.evidence["judge"] == "error"
    assert result.evidence["kind"] == "http"


def test_judge_module_imports_no_http_client() -> None:
    import agent_eval_lab.graders.judge as judge_mod

    src = open(judge_mod.__file__).read()
    assert "httpx" not in src
    assert "chat_completion" not in src
```

This test imports `JudgeError` from `runners/judge_edge` (Task 9). To keep Task 5 self-contained and TDD-ordered, write `grade_llm_judge` against a structural duck-type: it checks `isinstance(value, JudgeVerdict)`; anything else (including a `JudgeError` or absence) is the non-pass path. Defer the `JudgeError`-at-key test (`test_grade_judge_error_at_key_is_structured_nonpass`) until Task 9 — mark it with `@pytest.mark.skip(reason="JudgeError defined in Task 9")` now and remove the skip in Task 9. (Add `import pytest` to the test file.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/graders/test_judge.py -k grade -v`
Expected: FAIL — `cannot import name 'grade_llm_judge'`.

- [ ] **Step 3: Implement `grade_llm_judge`**

Add to the import block: `from typing import Any` and `from agent_eval_lab.records.grade import GradeResult` (`grade_llm_judge` takes `verdicts: Mapping[str, Any]` and `_non_pass` annotates `value: Any`). Add:

```python
def grade_llm_judge(
    *,
    spec: LlmJudgeSpec,
    trajectory: Trajectory,
    verdicts: Mapping[str, Any],
) -> GradeResult:
    key = prompt_hash(build_judge_prompt(spec=spec, trajectory=trajectory))
    value = verdicts.get(key)
    if not isinstance(value, JudgeVerdict):
        return _non_pass(key, value)
    passed = value.score >= PASS_THRESHOLD
    return GradeResult(
        grader_id="llm_judge",
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={
            "judge_model": value.judge_model,
            "prompt_hash": value.prompt_hash,
            "score": value.score,
            "scale": [spec.scale[0], spec.scale[1]],
            "threshold": PASS_THRESHOLD,
            "binary_label": "faithful" if passed else "unfaithful",
            "rationale": value.rationale,
            "raw": value.raw,
        },
        failure_reason=None,
    )


def _non_pass(key: str, value: Any) -> GradeResult:
    if value is None:
        evidence: dict[str, Any] = {"judge": "not_run", "prompt_hash": key}
    else:
        # A JudgeError (or any non-verdict) at the key: structured error evidence.
        evidence = {
            "judge": "error",
            "prompt_hash": key,
            "kind": getattr(value, "kind", "unknown"),
            "error": getattr(value, "error", repr(value)),
        }
    return GradeResult(
        grader_id="llm_judge",
        passed=False,
        score=0.0,
        evidence=evidence,
        failure_reason=None,
    )
```

`verdicts: Mapping[str, Any]` is used here to avoid a circular import of `JudgeError` (defined in the edge module, Task 9) into the pure core. The duck-typed `getattr` reads `kind`/`error` off a `JudgeError` without importing it — the pure core stays free of the edge.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/graders/test_judge.py -q`
Expected: PASS (skipped test for JudgeError-at-key still skipped). Then `uv run ruff check src/agent_eval_lab/graders/judge.py`.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/judge.py tests/graders/test_judge.py
git commit -m "feat(judge): grade_llm_judge reads precomputed verdict, binarizes at >=4"
```

---

## Task 6: Pure `collect_judge_specs` — spec-tree walk (recurses AllOf)

**Files:**
- Modify: `src/agent_eval_lab/graders/judge.py`
- Test: `tests/graders/test_judge.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/graders/test_judge.py`:

```python
from agent_eval_lab.graders.judge import collect_judge_specs
from agent_eval_lab.tasks.schema import AllOf, FinalStateSpec, StateEquals


def test_collect_finds_top_level_judge() -> None:
    assert collect_judge_specs(SPEC) == (SPEC,)


def test_collect_ignores_deterministic_specs() -> None:
    spec = FinalStateSpec(constraints=(StateEquals(path="a.b", expected=1),))
    assert collect_judge_specs(spec) == ()


def test_collect_recurses_all_of() -> None:
    det = FinalStateSpec(constraints=(StateEquals(path="a.b", expected=1),))
    spec = AllOf(specs=(det, SPEC, AllOf(specs=(SPEC,))))
    assert collect_judge_specs(spec) == (SPEC, SPEC)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/graders/test_judge.py -k collect -v`
Expected: FAIL — `cannot import name 'collect_judge_specs'`.

- [ ] **Step 3: Implement `collect_judge_specs`**

Add `AllOf` and `VerificationSpec` to the schema import. Add:

```python
def collect_judge_specs(verification: VerificationSpec) -> tuple[LlmJudgeSpec, ...]:
    """Pure walk of the spec tree (recurses AllOf exactly as grade_all_of does, D1)."""
    if isinstance(verification, LlmJudgeSpec):
        return (verification,)
    if isinstance(verification, AllOf):
        return tuple(
            spec for sub in verification.specs for spec in collect_judge_specs(sub)
        )
    return ()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/graders/test_judge.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/judge.py tests/graders/test_judge.py
git commit -m "feat(judge): pure collect_judge_specs spec-tree walk"
```

---

## Task 7: Thread `verdicts` through `grade_all_of`

**Files:**
- Modify: `src/agent_eval_lab/graders/composite.py`
- Test: `tests/graders/test_composite.py`

- [ ] **Step 1: Write the failing test**

The existing `_grader_returning` fake has signature `grade(*, verification, trajectory, registry, initial_state)`. Update it AND add a `verdicts`-threading test. Replace the `_grader_returning` helper in `tests/graders/test_composite.py`:

```python
def _grader_returning(results):
    """Build a fake grade_trajectory that returns scripted results in order."""
    calls = iter(results)
    seen = []

    def grade(*, verification, trajectory, registry, initial_state, verdicts):
        seen.append(verdicts)
        return next(calls)

    grade.seen = seen
    return grade
```

Update the two existing `grade_all_of(...)` call sites in this file to pass `verdicts={}`. Then append:

```python
def test_all_of_threads_verdicts_into_every_sub_call() -> None:
    spec = AllOf(
        specs=(
            OutputMatchSpec(expected_output="a"),
            OutputMatchSpec(expected_output="b"),
        )
    )
    grade = _grader_returning([_result(True), _result(True)])
    sentinel = {"h": object()}

    grade_all_of(
        spec=spec,
        initial_state=None,
        trajectory=_trajectory(),
        registry={},
        grade=grade,
        verdicts=sentinel,
    )

    assert grade.seen == [sentinel, sentinel]  # threaded unchanged into each sub-call
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/graders/test_composite.py -q`
Expected: FAIL — `grade_all_of() got an unexpected keyword argument 'verdicts'`.

- [ ] **Step 3: Implement the threading**

In `src/agent_eval_lab/graders/composite.py`, update the signature and the recursive call:

```python
def grade_all_of(
    *,
    spec: AllOf,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
    registry: Mapping[str, ToolDef],
    grade: GradeFn,
    verdicts: Mapping[str, Any],
) -> GradeResult:
    """Grade AllOf by recursing `grade` over every sub-spec in declared order."""
    sub_results = tuple(
        grade(
            verification=sub,
            trajectory=trajectory,
            registry=registry,
            initial_state=initial_state,
            verdicts=verdicts,
        )
        for sub in spec.specs
    )
```

(Rest of the function is unchanged.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/graders/test_composite.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/composite.py tests/graders/test_composite.py
git commit -m "feat(composite): thread verdicts map through grade_all_of recursion"
```

---

## Task 8: Dispatch `LlmJudgeSpec` + accept `verdicts` in `grade_trajectory`

**Files:**
- Modify: `src/agent_eval_lab/graders/dispatch.py`
- Test: `tests/graders/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/graders/test_dispatch.py`:

```python
def test_dispatches_llm_judge_with_supplied_verdict() -> None:
    from agent_eval_lab.graders.judge import (
        JudgeVerdict,
        build_judge_prompt,
        prompt_hash,
    )
    from agent_eval_lab.tasks.schema import LlmJudgeSpec

    spec = LlmJudgeSpec(rubric="r", judge_model="m", scale=(1, 5))
    trajectory = _trajectory(MessageTurn(role="assistant", content="Done."))
    h = prompt_hash(build_judge_prompt(spec=spec, trajectory=trajectory))
    verdict = JudgeVerdict(score=5, rationale="ok", raw="SCORE: 5", judge_model="m", prompt_hash=h)

    result = grade_trajectory(
        verification=spec,
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        verdicts={h: verdict},
    )

    assert result.passed is True
    assert result.grader_id == "llm_judge"


def test_all_of_with_judge_leg_runs_deterministic_leg_regardless() -> None:
    from agent_eval_lab.graders.judge import (
        JudgeVerdict,
        build_judge_prompt,
        prompt_hash,
    )
    from agent_eval_lab.tasks.schema import LlmJudgeSpec

    judge = LlmJudgeSpec(rubric="r", judge_model="m", scale=(1, 5))
    spec = AllOf(
        specs=(
            FinalStateSpec(
                constraints=(StateEquals(path="tickets.T-1.status", expected="closed"),)
            ),
            judge,
        )
    )
    trajectory = _state_trajectory({"tickets": {"T-1": {"status": "closed"}}})
    h = prompt_hash(build_judge_prompt(spec=judge, trajectory=trajectory))
    # judge fails (score 2) but the deterministic leg passes -> AllOf is the AND -> False
    verdict = JudgeVerdict(score=2, rationale="bad", raw="SCORE: 2", judge_model="m", prompt_hash=h)

    result = grade_trajectory(
        verification=spec,
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        verdicts={h: verdict},
    )

    assert result.passed is False
    subs = result.evidence["sub_results"]
    assert len(subs) == 2
    assert subs[0]["grader_id"] == "final_state" and subs[0]["passed"] is True
    assert subs[1]["grader_id"] == "llm_judge" and subs[1]["passed"] is False


def test_existing_dispatch_works_with_default_empty_verdicts() -> None:
    spec = OutputMatchSpec(expected_output="Done.")
    trajectory = _trajectory(MessageTurn(role="assistant", content="Done."))
    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )
    assert result.passed is True


def test_dispatch_module_imports_no_http_client() -> None:
    import agent_eval_lab.graders.dispatch as dispatch_mod

    src = open(dispatch_mod.__file__).read()
    assert "httpx" not in src
    assert "chat_completion" not in src
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/graders/test_dispatch.py -k "judge or verdict or empty_verdicts" -v`
Expected: FAIL — `grade_trajectory() got an unexpected keyword argument 'verdicts'`.

- [ ] **Step 3: Implement dispatch threading**

In `src/agent_eval_lab/graders/dispatch.py`, add imports:

```python
from agent_eval_lab.graders.judge import grade_llm_judge
from agent_eval_lab.tasks.schema import (
    AllOf,
    FinalStateSpec,
    LlmJudgeSpec,
    OutputMatchSpec,
    ToolCallMatchSpec,
    TrajectorySpec,
    VerificationSpec,
)
```

Update `grade_trajectory`:

```python
def grade_trajectory(
    *,
    verification: VerificationSpec,
    trajectory: Trajectory,
    registry: Mapping[str, ToolDef],
    initial_state: Mapping[str, Any] | None = None,
    verdicts: Mapping[str, Any] | None = None,
) -> GradeResult:
    verdicts = {} if verdicts is None else verdicts
    if isinstance(verification, OutputMatchSpec):
        return grade_output_match(spec=verification, trajectory=trajectory)
    if isinstance(verification, ToolCallMatchSpec):
        return grade_tool_call_match(
            spec=verification, trajectory=trajectory, registry=registry
        )
    if isinstance(verification, FinalStateSpec):
        return grade_final_state(
            spec=verification, initial_state=initial_state, trajectory=trajectory
        )
    if isinstance(verification, TrajectorySpec):
        return grade_trajectory_spec(
            spec=verification, initial_state=initial_state, trajectory=trajectory
        )
    if isinstance(verification, LlmJudgeSpec):
        return grade_llm_judge(
            spec=verification, trajectory=trajectory, verdicts=verdicts
        )
    if isinstance(verification, AllOf):
        return grade_all_of(
            spec=verification,
            initial_state=initial_state,
            trajectory=trajectory,
            registry=registry,
            grade=grade_trajectory,
            verdicts=verdicts,
        )
    raise ValueError(f"unsupported verification spec: {verification!r}")
```

Note: `grade_all_of` now requires `verdicts` (Task 7 made it non-default), so `grade_trajectory` must always pass it. Default `None`→`{}` keeps every existing caller working.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/graders/test_dispatch.py -q`
Expected: PASS. Then run the whole grader suite to confirm no regression: `uv run pytest tests/graders -q`.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/dispatch.py tests/graders/test_dispatch.py
git commit -m "feat(dispatch): route LlmJudgeSpec to grade_llm_judge; accept verdicts map"
```

---

## Task 9: Edge `run_judge` + `JudgeError` (the only judge I/O)

**Files:**
- Create: `src/agent_eval_lab/runners/judge_edge.py`
- Test: `tests/runners/test_judge_edge.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/runners/test_judge_edge.py`:

```python
import httpx
import pytest

from agent_eval_lab.graders.judge import JudgeVerdict, build_judge_prompt, prompt_hash
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.judge_edge import JudgeError, run_judge
from agent_eval_lab.tasks.schema import LlmJudgeSpec

CONFIG = ProviderConfig(
    id="deepseek", base_url="https://api.test.example",
    api_key_env="TEST_API_KEY", model_id="deepseek-v4-pro",
)
SPEC = LlmJudgeSpec(rubric="Judge fidelity.", judge_model="deepseek:deepseek-v4-pro", scale=(1, 5))
TRAJ = Trajectory(
    turns=(MessageTurn(role="assistant", content="Done."),),
    usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
    run_index=0, stop_reason="completed",
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _reply(text: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def test_run_judge_success_stamps_model_and_hash(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    verdict = run_judge(
        spec=SPEC, trajectory=TRAJ, config=CONFIG,
        http_client=_client(lambda r: httpx.Response(200, json=_reply("Faithful.\nSCORE: 5"))),
    )
    assert isinstance(verdict, JudgeVerdict)
    assert verdict.score == 5
    assert verdict.judge_model == "deepseek:deepseek-v4-pro"
    assert verdict.prompt_hash == prompt_hash(build_judge_prompt(spec=SPEC, trajectory=TRAJ))


def test_run_judge_parse_failure_becomes_judge_error(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    err = run_judge(
        spec=SPEC, trajectory=TRAJ, config=CONFIG,
        http_client=_client(lambda r: httpx.Response(200, json=_reply("I refuse to score."))),
    )
    assert isinstance(err, JudgeError)
    assert err.kind == "parse"
    assert err.judge_model == "deepseek:deepseek-v4-pro"
    assert err.prompt_hash == prompt_hash(build_judge_prompt(spec=SPEC, trajectory=TRAJ))


def test_run_judge_transport_error_becomes_judge_error(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    err = run_judge(
        spec=SPEC, trajectory=TRAJ, config=CONFIG,
        http_client=_client(boom),
    )
    assert isinstance(err, JudgeError)
    assert err.kind == "transport"


def test_run_judge_http_error_becomes_judge_error(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    err = run_judge(
        spec=SPEC, trajectory=TRAJ, config=CONFIG,
        http_client=_client(lambda r: httpx.Response(400, json={"error": "bad"})),
    )
    assert isinstance(err, JudgeError)
    assert err.kind == "http"


def test_run_judge_empty_choices_becomes_judge_error(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    err = run_judge(
        spec=SPEC, trajectory=TRAJ, config=CONFIG,
        http_client=_client(lambda r: httpx.Response(200, json={"choices": []})),
    )
    assert isinstance(err, JudgeError)
    assert err.kind == "empty_response"
```

Note: `chat_completion` retries on 429/5xx but **not** on 400, so the 400 test returns a single `HTTPStatusError` — caught as `kind="http"`. A 5xx would be retried then raised; that also lands in the `http` branch (still no escaped exception).

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/runners/test_judge_edge.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.runners.judge_edge`.

- [ ] **Step 3: Implement `run_judge` + `JudgeError`**

Create `src/agent_eval_lab/runners/judge_edge.py`:

```python
"""EDGE: the single judge I/O boundary (ADR 0005).

Builds the prompt (pure), calls the existing OpenAI-compatible client, parses the
reply (pure), and stamps judge_model + prompt_hash onto the verdict. A transport,
HTTP, empty-response, or parse failure is captured as a serializable JudgeError —
an exception NEVER escapes into the verdict map (D2).
"""

from dataclasses import dataclass, replace
from typing import Literal

import httpx

from agent_eval_lab.graders.judge import (
    JudgeParseFailure,
    JudgeVerdict,
    build_judge_prompt,
    parse_judge_response,
    prompt_hash,
)
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.runners.client import chat_completion
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.tasks.schema import LlmJudgeSpec


@dataclass(frozen=True, kw_only=True)
class JudgeError:
    kind: Literal["transport", "http", "parse", "empty_response"]
    error: str
    prompt_hash: str
    judge_model: str


def run_judge(
    *,
    spec: LlmJudgeSpec,
    trajectory: Trajectory,
    config: ProviderConfig,
    http_client: httpx.Client,
) -> JudgeVerdict | JudgeError:
    messages = build_judge_prompt(spec=spec, trajectory=trajectory)
    p_hash = prompt_hash(messages)
    model = condition_id(config)
    try:
        response = chat_completion(
            config=config,
            messages=messages,
            tools=(),
            temperature=0.0,
            http_client=http_client,
        )
    except httpx.HTTPStatusError as exc:
        return JudgeError(kind="http", error=str(exc), prompt_hash=p_hash, judge_model=model)
    except httpx.TransportError as exc:
        return JudgeError(kind="transport", error=str(exc), prompt_hash=p_hash, judge_model=model)
    choices = response.payload.get("choices") or []
    if not choices:
        return JudgeError(
            kind="empty_response", error="no choices in provider response",
            prompt_hash=p_hash, judge_model=model,
        )
    text = (choices[0].get("message", {}) or {}).get("content") or ""
    parsed = parse_judge_response(text, scale=spec.scale)
    if isinstance(parsed, JudgeParseFailure):
        return JudgeError(kind="parse", error=parsed.error, prompt_hash=p_hash, judge_model=model)
    return replace(parsed, judge_model=model, prompt_hash=p_hash)
```

`condition_id(config)` produces `"deepseek:deepseek-v4-pro"` — the self-describing `judge_model` stamp.

- [ ] **Step 4: Remove the Task-5 skip and run**

In `tests/graders/test_judge.py`, delete the `@pytest.mark.skip` decorator from `test_grade_judge_error_at_key_is_structured_nonpass`. Then:

Run: `uv run pytest tests/runners/test_judge_edge.py tests/graders/test_judge.py -q`
Expected: PASS (the JudgeError-at-key test now runs and passes via the duck-typed `_non_pass`).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/judge_edge.py tests/runners/test_judge_edge.py tests/graders/test_judge.py
git commit -m "feat(judge-edge): run_judge with JudgeError sum type; stamp model+hash"
```

---

## Task 10: Serialize `JudgeVerdict` / `JudgeError` for packet + report round-trips

**Files:**
- Modify: `src/agent_eval_lab/records/serialize.py`
- Test: `tests/records/test_serialize.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/records/test_serialize.py`:

```python
def test_judge_verdict_round_trips() -> None:
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.records.serialize import verdict_from_dict, verdict_to_dict

    v = JudgeVerdict(score=4, rationale="r", raw="SCORE: 4", judge_model="m", prompt_hash="h")
    assert verdict_from_dict(verdict_to_dict(v)) == v


def test_judge_error_round_trips() -> None:
    from agent_eval_lab.records.serialize import verdict_from_dict, verdict_to_dict
    from agent_eval_lab.runners.judge_edge import JudgeError

    e = JudgeError(kind="http", error="500", prompt_hash="h", judge_model="m")
    assert verdict_from_dict(verdict_to_dict(e)) == e
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/records/test_serialize.py -k judge -v`
Expected: FAIL — `cannot import name 'verdict_to_dict'`.

- [ ] **Step 3: Implement the round-trip**

Append to `src/agent_eval_lab/records/serialize.py`:

```python
def verdict_to_dict(value: Any) -> dict[str, Any]:
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.runners.judge_edge import JudgeError

    if isinstance(value, JudgeVerdict):
        return {
            "type": "verdict",
            "score": value.score,
            "rationale": value.rationale,
            "raw": value.raw,
            "judge_model": value.judge_model,
            "prompt_hash": value.prompt_hash,
        }
    if isinstance(value, JudgeError):
        return {
            "type": "judge_error",
            "kind": value.kind,
            "error": value.error,
            "prompt_hash": value.prompt_hash,
            "judge_model": value.judge_model,
        }
    raise ValueError(f"not a judge value: {value!r}")


def verdict_from_dict(data: Mapping[str, Any]) -> Any:
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.runners.judge_edge import JudgeError

    if data["type"] == "verdict":
        return JudgeVerdict(
            score=data["score"], rationale=data["rationale"], raw=data["raw"],
            judge_model=data["judge_model"], prompt_hash=data["prompt_hash"],
        )
    if data["type"] == "judge_error":
        return JudgeError(
            kind=data["kind"], error=data["error"],
            prompt_hash=data["prompt_hash"], judge_model=data["judge_model"],
        )
    raise ValueError(f"unknown judge value type: {data['type']!r}")
```

The function-local imports avoid a module-level cycle (`serialize` ↔ `judge_edge` ↔ `client`); `serialize` stays a leaf for the existing trajectory round-trips.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/records/test_serialize.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/records/serialize.py tests/records/test_serialize.py
git commit -m "feat(serialize): round-trip JudgeVerdict and JudgeError"
```

---

## Task 11: `metrics/agreement.py` — confusion matrix, observed/expected agreement

**Files:**
- Create: `src/agent_eval_lab/metrics/agreement.py`
- Test: `tests/metrics/test_agreement.py`

**Hand-verified test vectors (computed and checked for this plan):**

| Vector | Contingency (A\B: pos,neg) | n | p_o | p_e | κ |
|--------|----------------------------|---|-----|-----|---|
| V1 textbook 2×2 | a=20,b=5,c=10,d=15 | 50 | 0.70 | 0.50 | **0.40** |
| V2 perfect | a=10,b=0,c=0,d=10 | 20 | 1.00 | 0.50 | **1.00** |
| V3 chance (balanced) | a=25,b=25,c=25,d=25 | 100 | 0.50 | 0.50 | **0.00** |
| V4 Cohen 1960 | a=88,b=14,c=10,d=88 | 200 | 0.88 | 0.4998 | **0.7601** |

Here "pos" = "faithful" (binary label). In sequence form a 2×2 (a,b,c,d) is reconstructed as: `a` items both rate pos, `b` items A=pos/B=neg, `c` items A=neg/B=pos, `d` items both neg. The tests build label sequences directly.

- [ ] **Step 1: Write the failing tests**

Create `tests/metrics/test_agreement.py`:

```python
import pytest

from agent_eval_lab.metrics.agreement import (
    cohens_kappa,
    confusion_matrix,
    expected_agreement,
    observed_agreement,
)


def _labels(a, b, c, d):
    """Build two rater sequences realizing a 2x2 (pos/neg) table."""
    pos, neg = "faithful", "unfaithful"
    la = [pos] * (a + b) + [neg] * (c + d)
    lb = [pos] * a + [neg] * b + [pos] * c + [neg] * d
    return la, lb


def test_confusion_matrix_counts_pairs() -> None:
    la, lb = _labels(20, 5, 10, 15)
    cm = confusion_matrix(la, lb)
    assert cm[("faithful", "faithful")] == 20
    assert cm[("faithful", "unfaithful")] == 5
    assert cm[("unfaithful", "faithful")] == 10
    assert cm[("unfaithful", "unfaithful")] == 15


def test_v1_textbook_kappa_is_0_40() -> None:
    la, lb = _labels(20, 5, 10, 15)
    assert observed_agreement(la, lb) == pytest.approx(0.70)
    assert expected_agreement(la, lb) == pytest.approx(0.50)
    r = cohens_kappa(la, lb)
    assert r.kappa == pytest.approx(0.40)
    assert r.degenerate is False


def test_v2_perfect_agreement_kappa_is_1() -> None:
    la, lb = _labels(10, 0, 0, 10)
    assert cohens_kappa(la, lb).kappa == pytest.approx(1.0)


def test_v3_chance_agreement_kappa_is_0() -> None:
    la, lb = _labels(25, 25, 25, 25)
    assert cohens_kappa(la, lb).kappa == pytest.approx(0.0)


def test_v4_cohen1960_kappa() -> None:
    la, lb = _labels(88, 14, 10, 88)
    assert cohens_kappa(la, lb).kappa == pytest.approx(0.7601, abs=1e-4)


def test_degenerate_single_category_is_kappa_0_flagged() -> None:
    # Both raters label every item the same single category -> 1 - p_e == 0.
    la = ["faithful"] * 10
    lb = ["faithful"] * 10
    r = cohens_kappa(la, lb)
    assert r.kappa == 0.0
    assert r.degenerate is True


def test_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError, match="equal length"):
        cohens_kappa(["a"], ["a", "b"])


def test_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        cohens_kappa([], [])
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/metrics/test_agreement.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.metrics.agreement`.

- [ ] **Step 3: Implement the base κ machinery**

Create `src/agent_eval_lab/metrics/agreement.py`:

```python
"""Pure inter-rater agreement: Cohen's kappa (binary headline, ADR 0006),
quadratic-weighted kappa (secondary), and a seeded percentile bootstrap CI
resampling items (spec §4.6). Stdlib only; the bootstrap RNG seed is an argument.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass

Label = object  # any hashable; in practice "faithful"/"unfaithful" or an int score


@dataclass(frozen=True, kw_only=True)
class KappaResult:
    kappa: float
    observed_agreement: float
    expected_agreement: float
    degenerate: bool


@dataclass(frozen=True, kw_only=True)
class BootstrapCI:
    point: float
    lo: float
    hi: float
    alpha: float
    n_resamples: int
    n_degenerate: int
    seed: int


def _require_pair(a: Sequence[Label], b: Sequence[Label]) -> None:
    if len(a) != len(b):
        raise ValueError("rater sequences must be of equal length")
    if not a:
        raise ValueError("rater sequences must not be empty")


def confusion_matrix(a: Sequence[Label], b: Sequence[Label]) -> dict[tuple, int]:
    _require_pair(a, b)
    cm: dict[tuple, int] = {}
    for x, y in zip(a, b):
        cm[(x, y)] = cm.get((x, y), 0) + 1
    return cm


def observed_agreement(a: Sequence[Label], b: Sequence[Label]) -> float:
    _require_pair(a, b)
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def expected_agreement(a: Sequence[Label], b: Sequence[Label]) -> float:
    _require_pair(a, b)
    n = len(a)
    categories = set(a) | set(b)
    return sum(
        (sum(1 for x in a if x == c) / n) * (sum(1 for y in b if y == c) / n)
        for c in categories
    )


def cohens_kappa(a: Sequence[Label], b: Sequence[Label]) -> KappaResult:
    p_o = observed_agreement(a, b)
    p_e = expected_agreement(a, b)
    if 1.0 - p_e == 0.0:
        return KappaResult(kappa=0.0, observed_agreement=p_o, expected_agreement=p_e, degenerate=True)
    return KappaResult(
        kappa=(p_o - p_e) / (1.0 - p_e),
        observed_agreement=p_o,
        expected_agreement=p_e,
        degenerate=False,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/metrics/test_agreement.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/metrics/agreement.py tests/metrics/test_agreement.py
git commit -m "feat(metrics): Cohen's kappa with hand-verified literature vectors"
```

---

## Task 12: `weighted_kappa` (quadratic) — hand-verified ordinal vector

**Files:**
- Modify: `src/agent_eval_lab/metrics/agreement.py`
- Test: `tests/metrics/test_agreement.py`

**Hand-verified weighted-κ vector (D6b):** ordinal categories `0,1,2`, 3×3 table
`[[10,5,0],[5,20,5],[0,5,10]]` (n=70). Quadratic weights `w_ij = 1 - (i-j)²/(k-1)²`, k=3.
Computed for this plan: weighted p_o = 11/12 ≈ 0.91667, weighted p_e = 3/4 = 0.75,
**weighted κ = 2/3 ≈ 0.66667** (exact rational).

- [ ] **Step 1: Write the failing test**

Append to `tests/metrics/test_agreement.py`:

```python
def test_weighted_kappa_ordinal_vector_is_two_thirds() -> None:
    from agent_eval_lab.metrics.agreement import weighted_kappa

    # 3x3 table [[10,5,0],[5,20,5],[0,5,10]] over ordered categories 0,1,2.
    table = [[10, 5, 0], [5, 20, 5], [0, 5, 10]]
    la, lb = [], []
    for i, row in enumerate(table):
        for j, count in enumerate(row):
            la.extend([i] * count)
            lb.extend([j] * count)
    assert weighted_kappa(la, lb, categories=(0, 1, 2)) == pytest.approx(2 / 3, abs=1e-9)


def test_weighted_kappa_perfect_agreement_is_1() -> None:
    from agent_eval_lab.metrics.agreement import weighted_kappa

    seq = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
    assert weighted_kappa(seq, seq, categories=(1, 2, 3, 4, 5)) == pytest.approx(1.0)


def test_weighted_kappa_degenerate_is_0() -> None:
    from agent_eval_lab.metrics.agreement import weighted_kappa

    assert weighted_kappa([2, 2, 2], [2, 2, 2], categories=(1, 2, 3)) == 0.0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/metrics/test_agreement.py -k weighted -v`
Expected: FAIL — `cannot import name 'weighted_kappa'`.

- [ ] **Step 3: Implement `weighted_kappa`**

Append to `src/agent_eval_lab/metrics/agreement.py`:

```python
def _quadratic_weight(i: int, j: int, k: int) -> float:
    return 1.0 - ((i - j) ** 2) / ((k - 1) ** 2)


def weighted_kappa(
    a: Sequence[Label], b: Sequence[Label], *, categories: tuple
) -> float:
    """Quadratic-weighted kappa over ORDERED `categories` (secondary stat, ADR 0006).

    Disagreement weight scales with squared ordinal distance: near-misses cost
    less than gross disagreements. Returns 0.0 on the degenerate (1 - p_e == 0)
    path, matching cohens_kappa.
    """
    _require_pair(a, b)
    n = len(a)
    k = len(categories)
    index = {c: idx for idx, c in enumerate(categories)}
    cm = confusion_matrix(a, b)
    row = {i: sum(1 for x in a if index[x] == i) / n for i in range(k)}
    col = {j: sum(1 for y in b if index[y] == j) / n for j in range(k)}
    p_o = sum(
        _quadratic_weight(index[x], index[y], k) * count / n
        for (x, y), count in cm.items()
    )
    p_e = sum(
        _quadratic_weight(i, j, k) * row[i] * col[j]
        for i in range(k)
        for j in range(k)
    )
    if 1.0 - p_e == 0.0:
        return 0.0
    return (p_o - p_e) / (1.0 - p_e)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/metrics/test_agreement.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/metrics/agreement.py tests/metrics/test_agreement.py
git commit -m "feat(metrics): quadratic weighted_kappa with hand-verified ordinal vector"
```

---

## Task 13: `kappa_bootstrap_ci` — seeded percentile CI, degenerate-resample counting

**Files:**
- Modify: `src/agent_eval_lab/metrics/agreement.py`
- Test: `tests/metrics/test_agreement.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/metrics/test_agreement.py`:

```python
def test_bootstrap_is_deterministic_under_seed() -> None:
    from agent_eval_lab.metrics.agreement import kappa_bootstrap_ci

    la, lb = _labels(20, 5, 10, 15)
    a = kappa_bootstrap_ci(la, lb, n_resamples=500, seed=7, alpha=0.05)
    b = kappa_bootstrap_ci(la, lb, n_resamples=500, seed=7, alpha=0.05)
    assert (a.lo, a.hi, a.point) == (b.lo, b.hi, b.point)
    assert a.point == pytest.approx(0.40)
    assert a.lo <= a.point <= a.hi
    assert a.n_resamples == 500
    assert a.seed == 7


def test_bootstrap_different_seed_differs() -> None:
    from agent_eval_lab.metrics.agreement import kappa_bootstrap_ci

    la, lb = _labels(20, 5, 10, 15)
    a = kappa_bootstrap_ci(la, lb, n_resamples=200, seed=1, alpha=0.05)
    b = kappa_bootstrap_ci(la, lb, n_resamples=200, seed=2, alpha=0.05)
    assert (a.lo, a.hi) != (b.lo, b.hi)


def test_bootstrap_counts_degenerate_resamples() -> None:
    from agent_eval_lab.metrics.agreement import kappa_bootstrap_ci

    # A heavily imbalanced sample makes many resamples draw a single category.
    la = ["faithful"] * 19 + ["unfaithful"]
    lb = ["faithful"] * 19 + ["unfaithful"]
    ci = kappa_bootstrap_ci(la, lb, n_resamples=300, seed=3, alpha=0.05)
    assert ci.n_degenerate > 0  # some resamples drew all-faithful -> counted, not dropped
    assert ci.n_resamples == 300
    # Degenerate resamples contribute kappa=0.0; the CI is still finite (no crash).
    assert ci.lo <= ci.hi
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/metrics/test_agreement.py -k bootstrap -v`
Expected: FAIL — `cannot import name 'kappa_bootstrap_ci'`.

- [ ] **Step 3: Implement `kappa_bootstrap_ci`**

Append to `src/agent_eval_lab/metrics/agreement.py`:

```python
def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation percentile (q in [0, 1]); inputs pre-sorted ascending."""
    if not sorted_values:
        raise ValueError("no values to take a percentile of")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo_idx = int(pos)
    frac = pos - lo_idx
    if lo_idx + 1 >= len(sorted_values):
        return sorted_values[-1]
    return sorted_values[lo_idx] + frac * (sorted_values[lo_idx + 1] - sorted_values[lo_idx])


def kappa_bootstrap_ci(
    a: Sequence[Label],
    b: Sequence[Label],
    *,
    n_resamples: int,
    seed: int,
    alpha: float,
) -> BootstrapCI:
    """Percentile bootstrap CI for Cohen's kappa, resampling ITEMS (the annotated
    trajectory is the unit, spec §4.6). RNG is seeded => deterministic. A resample
    whose kappa hits the degenerate (1 - p_e == 0) path contributes kappa=0.0 and
    is COUNTED in n_degenerate (D7) — never silently dropped, never a crash.
    """
    _require_pair(a, b)
    pairs = list(zip(a, b))
    n = len(pairs)
    rng = random.Random(seed)
    point = cohens_kappa(a, b).kappa
    kappas: list[float] = []
    n_degenerate = 0
    for _ in range(n_resamples):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        ra = [p[0] for p in sample]
        rb = [p[1] for p in sample]
        result = cohens_kappa(ra, rb)
        if result.degenerate:
            n_degenerate += 1
        kappas.append(result.kappa)
    kappas.sort()
    return BootstrapCI(
        point=point,
        lo=_percentile(kappas, alpha / 2),
        hi=_percentile(kappas, 1 - alpha / 2),
        alpha=alpha,
        n_resamples=n_resamples,
        n_degenerate=n_degenerate,
        seed=seed,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/metrics/test_agreement.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/metrics/agreement.py tests/metrics/test_agreement.py
git commit -m "feat(metrics): seeded percentile bootstrap CI counting degenerate resamples"
```

---

## Task 14: `calibrate/packet.py` — build/serialize the blind packet

**Files:**
- Create: `src/agent_eval_lab/calibrate/__init__.py` (empty)
- Create: `src/agent_eval_lab/calibrate/packet.py`
- Create: `tests/calibrate/__init__.py` (empty)
- Test: `tests/calibrate/test_packet.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/calibrate/__init__.py` (empty). Create `tests/calibrate/test_packet.py`:

```python
import pytest

from agent_eval_lab.calibrate.packet import (
    PACKET_FORMAT,
    RUBRIC_VERSION,
    Packet,
    PacketItem,
    build_packet,
    packet_from_jsonl,
    packet_to_jsonl,
)
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn, ToolResultTurn, ToolSuccess
from agent_eval_lab.tasks.schema import LlmJudgeSpec

SPEC = LlmJudgeSpec(rubric="Judge fidelity.", judge_model="m", scale=(1, 5))


def _fixture(fid, assistant):
    traj = Trajectory(
        turns=(
            MessageTurn(role="user", content="Close T-1."),
            ToolCallTurn(tool_calls=(ToolCall(call_id="c1", name="update_ticket",
                arguments={"ticket_id": "T-1", "status": "closed"}),)),
            ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"ok": True})),
            MessageTurn(role="assistant", content=assistant),
        ),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed",
    )
    return fid, traj


def test_build_packet_is_blind_and_ordered() -> None:
    fixtures = [_fixture("f2", "Done."), _fixture("f1", "Done and emailed.")]
    packet = build_packet(fixtures=fixtures, spec=SPEC, rubric="RUBRIC TEXT")
    assert packet.packet_format == PACKET_FORMAT
    assert packet.rubric_version == RUBRIC_VERSION
    assert packet.rubric == "RUBRIC TEXT"
    assert packet.annotator_id is None
    # fixed deterministic order = input order (authoring order), NOT sorted-by-id
    assert [i.fixture_id for i in packet.items] == ["f2", "f1"]
    # blind: every score is None, the digest carries no score and no intended label
    assert all(i.score is None for i in packet.items)
    assert "SCORE" not in packet.items[0].trajectory_digest
    assert "intended" not in packet.items[0].trajectory_digest.lower()


def test_packet_jsonl_round_trips() -> None:
    fixtures = [_fixture("f1", "Done.")]
    packet = build_packet(fixtures=fixtures, spec=SPEC, rubric="R")
    lines = packet_to_jsonl(packet)
    assert packet_from_jsonl(lines) == packet


def test_packet_jsonl_header_is_first_line() -> None:
    packet = build_packet(fixtures=[_fixture("f1", "Done.")], spec=SPEC, rubric="R")
    import json
    header = json.loads(packet_to_jsonl(packet).splitlines()[0])
    assert header["packet_format"] == PACKET_FORMAT
    assert header["rubric_version"] == RUBRIC_VERSION
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/calibrate/test_packet.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.calibrate.packet`.

- [ ] **Step 3: Implement build + serialize**

Create empty `src/agent_eval_lab/calibrate/__init__.py`. Create `src/agent_eval_lab/calibrate/packet.py`:

```python
"""Pure annotation-packet build/parse/validate + agreement computation (spec §6.5).

The packet a human (or LLM annotator) sees is BLIND: trajectory digest only, an
empty score field, NO judge score and NO fixture intended label (the intended
label lives in examples/calibration/intended_labels.jsonl, never here — D9).
JSONL is the source of truth; a sibling markdown is a human-readable view.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.graders.judge import render_trajectory_digest
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.tasks.schema import LlmJudgeSpec

PACKET_FORMAT = "calib-packet-v1"
RUBRIC_VERSION = "summary-fidelity-v1"


@dataclass(frozen=True, kw_only=True)
class PacketItem:
    fixture_id: str
    trajectory_digest: str
    score: int | None = None


@dataclass(frozen=True, kw_only=True)
class Packet:
    packet_format: str
    rubric_version: str
    rubric: str
    annotator_id: str | None
    items: tuple[PacketItem, ...]


def build_packet(
    *,
    fixtures: Sequence[tuple[str, Trajectory]],
    spec: LlmJudgeSpec,
    rubric: str,
) -> Packet:
    # `spec` is validated and kept in the signature so the packet's scale is an
    # explicit input (matches the test call sites and documents the judged scale);
    # the stored rubric is the verbatim anchors, unmodified.
    lo, hi = spec.scale
    if lo >= hi:
        raise ValueError(f"spec.scale must have lo < hi, got {spec.scale!r}")
    items = tuple(
        PacketItem(fixture_id=fid, trajectory_digest=render_trajectory_digest(traj), score=None)
        for fid, traj in fixtures
    )
    return Packet(
        packet_format=PACKET_FORMAT,
        rubric_version=RUBRIC_VERSION,
        rubric=rubric,
        annotator_id=None,
        items=items,
    )


def packet_to_jsonl(packet: Packet) -> str:
    header = {
        "packet_format": packet.packet_format,
        "rubric_version": packet.rubric_version,
        "rubric": packet.rubric,
        "annotator_id": packet.annotator_id,
    }
    lines = [json.dumps(header, sort_keys=True)]
    lines.extend(
        json.dumps(
            {"fixture_id": i.fixture_id, "trajectory_digest": i.trajectory_digest, "score": i.score},
            sort_keys=True,
        )
        for i in packet.items
    )
    return "\n".join(lines) + "\n"


def packet_from_jsonl(text: str) -> Packet:
    raw = [json.loads(line) for line in text.splitlines() if line.strip()]
    header, body = raw[0], raw[1:]
    return Packet(
        packet_format=header["packet_format"],
        rubric_version=header["rubric_version"],
        rubric=header["rubric"],
        annotator_id=header.get("annotator_id"),
        items=tuple(
            PacketItem(
                fixture_id=r["fixture_id"],
                trajectory_digest=r["trajectory_digest"],
                score=r["score"],
            )
            for r in body
        ),
    )
```

`spec` is a required keyword and genuinely used (its scale is validated), so ruff will not flag it. Every `build_packet` call in this plan — tests and CLI helpers alike — passes `spec=`; keep it that way. The CLI helpers (Tasks 18–20) construct the canonical judge spec via a shared `_CALIBRATION_SPEC` constant (defined in Task 18) so they have a `spec` to pass.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/calibrate/test_packet.py -q` then `uv run ruff check src/agent_eval_lab/calibrate/packet.py`.
Expected: PASS, clean. If ruff flags `spec` unused, remove it from `build_packet` and the test calls.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/calibrate/ tests/calibrate/
git commit -m "feat(calibrate): blind annotation packet build + JSONL round-trip"
```

---

## Task 15: `import_packet` — completeness + version + order validation

**Files:**
- Modify: `src/agent_eval_lab/calibrate/packet.py`
- Test: `tests/calibrate/test_packet.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/calibrate/test_packet.py`:

```python
def _filled(packet, scores, annotator):
    import dataclasses
    items = tuple(
        dataclasses.replace(i, score=s) for i, s in zip(packet.items, scores)
    )
    return dataclasses.replace(packet, items=items, annotator_id=annotator)


def test_import_accepts_complete_filled_packet() -> None:
    from agent_eval_lab.calibrate.packet import import_packet

    blank = build_packet(fixtures=[_fixture("f1", "Done."), _fixture("f2", "Done.")], spec=SPEC, rubric="R")
    filled = _filled(blank, [5, 3], "alice")
    out = import_packet(packet_to_jsonl(filled), expected=blank)
    assert out.annotator_id == "alice"
    assert [i.score for i in out.items] == [5, 3]


def test_import_rejects_incomplete_packet() -> None:
    from agent_eval_lab.calibrate.packet import import_packet

    blank = build_packet(fixtures=[_fixture("f1", "Done."), _fixture("f2", "Done.")], spec=SPEC, rubric="R")
    partial = _filled(blank, [5, None], "alice")
    with pytest.raises(ValueError, match="unscored"):
        import_packet(packet_to_jsonl(partial), expected=blank)


def test_import_rejects_out_of_range_score() -> None:
    from agent_eval_lab.calibrate.packet import import_packet

    blank = build_packet(fixtures=[_fixture("f1", "Done.")], spec=SPEC, rubric="R")
    bad = _filled(blank, [9], "alice")
    with pytest.raises(ValueError, match="out of range"):
        import_packet(packet_to_jsonl(bad), expected=blank, scale=(1, 5))


def test_import_rejects_reordered_items() -> None:
    from agent_eval_lab.calibrate.packet import import_packet

    blank = build_packet(fixtures=[_fixture("f1", "Done."), _fixture("f2", "Done.")], spec=SPEC, rubric="R")
    filled = _filled(blank, [5, 3], "alice")
    import dataclasses
    reordered = dataclasses.replace(filled, items=tuple(reversed(filled.items)))
    with pytest.raises(ValueError, match="item order"):
        import_packet(packet_to_jsonl(reordered), expected=blank)


def test_import_rejects_packet_format_mismatch() -> None:
    from agent_eval_lab.calibrate.packet import import_packet

    blank = build_packet(fixtures=[_fixture("f1", "Done.")], spec=SPEC, rubric="R")
    filled = _filled(blank, [5], "alice")
    text = packet_to_jsonl(filled).replace(PACKET_FORMAT, "calib-packet-v0")
    with pytest.raises(ValueError, match="packet_format"):
        import_packet(text, expected=blank)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/calibrate/test_packet.py -k import -v`
Expected: FAIL — `cannot import name 'import_packet'`.

- [ ] **Step 3: Implement `import_packet`**

Append to `src/agent_eval_lab/calibrate/packet.py`:

```python
def import_packet(
    text: str, *, expected: Packet, scale: tuple[int, int] = (1, 5)
) -> Packet:
    """Parse a filled packet and validate completeness against the exported one.

    Rejects (structured ValueError): packet_format mismatch, item-set/order
    mismatch, any unscored item, any score out of `scale`.
    """
    packet = packet_from_jsonl(text)
    if packet.packet_format != expected.packet_format:
        raise ValueError(
            f"packet_format mismatch: {packet.packet_format!r} != {expected.packet_format!r}"
        )
    got_ids = [i.fixture_id for i in packet.items]
    want_ids = [i.fixture_id for i in expected.items]
    if got_ids != want_ids:
        raise ValueError(f"item order/set mismatch: {got_ids} != {want_ids}")
    lo, hi = scale
    for item in packet.items:
        if item.score is None:
            raise ValueError(f"unscored item: {item.fixture_id!r}")
        if not (lo <= item.score <= hi):
            raise ValueError(f"score out of range for {item.fixture_id!r}: {item.score}")
    return packet
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/calibrate/test_packet.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/calibrate/packet.py tests/calibrate/test_packet.py
git commit -m "feat(calibrate): import_packet validates completeness, order, version, range"
```

---

## Task 16: `compute_agreement` + report rendering (≥2 packets → κ + CI + matrix)

**Files:**
- Modify: `src/agent_eval_lab/calibrate/packet.py`
- Test: `tests/calibrate/test_packet.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/calibrate/test_packet.py`:

```python
def test_compute_agreement_binarizes_and_reports_kappa() -> None:
    from agent_eval_lab.calibrate.packet import compute_agreement

    blank = build_packet(
        fixtures=[_fixture(f"f{i}", "Done.") for i in range(4)], spec=SPEC, rubric="R"
    )
    # Annotator A: 5,5,3,3  -> faithful,faithful,unfaithful,unfaithful
    # Annotator B: 5,3,5,3  -> faithful,unfaithful,faithful,unfaithful
    a = _filled(blank, [5, 5, 3, 3], "A")
    b = _filled(blank, [5, 3, 5, 3], "B")
    report = compute_agreement([a, b], threshold=4, scale=(1, 5), seed=11, n_resamples=200, alpha=0.05)
    assert report["binary_kappa"]["point"] == pytest.approx(0.0)  # chance-level 2x2
    assert "weighted_kappa" in report
    assert report["confusion_matrix"][("faithful", "faithful")] == 1
    assert report["n_items"] == 4


def test_compute_agreement_requires_two_packets() -> None:
    from agent_eval_lab.calibrate.packet import compute_agreement

    blank = build_packet(fixtures=[_fixture("f1", "Done.")], spec=SPEC, rubric="R")
    with pytest.raises(ValueError, match="two annotators"):
        compute_agreement([_filled(blank, [5], "A")], threshold=4, scale=(1, 5),
                          seed=1, n_resamples=10, alpha=0.05)


def test_render_agreement_report_contains_kappa_and_ci() -> None:
    from agent_eval_lab.calibrate.packet import compute_agreement, render_agreement_report

    blank = build_packet(fixtures=[_fixture(f"f{i}", "Done.") for i in range(4)], spec=SPEC, rubric="R")
    a = _filled(blank, [5, 5, 3, 3], "A")
    b = _filled(blank, [5, 3, 5, 3], "B")
    md = render_agreement_report(
        compute_agreement([a, b], threshold=4, scale=(1, 5), seed=11, n_resamples=200, alpha=0.05)
    )
    assert "Cohen" in md and "kappa" in md.lower()
    assert "CI" in md
    assert "Confusion matrix" in md
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/calibrate/test_packet.py -k "compute or render_agreement" -v`
Expected: FAIL — `cannot import name 'compute_agreement'`.

- [ ] **Step 3: Implement `compute_agreement` + `render_agreement_report`**

Add to the import block of `packet.py`:

```python
from agent_eval_lab.metrics.agreement import (
    cohens_kappa,
    confusion_matrix,
    kappa_bootstrap_ci,
    weighted_kappa,
)
```

Append:

```python
def _binarize(score: int, threshold: int) -> str:
    return "faithful" if score >= threshold else "unfaithful"


def compute_agreement(
    packets: Sequence[Packet],
    *,
    threshold: int,
    scale: tuple[int, int],
    seed: int,
    n_resamples: int,
    alpha: float,
) -> Mapping[str, object]:
    """Two-rater agreement over the FIRST TWO filled packets (Cohen's kappa, §6.5).

    Headline = binary kappa at `threshold` + percentile bootstrap CI; weighted
    kappa (quadratic, over the raw scale) is a secondary descriptive number.
    """
    if len(packets) < 2:
        raise ValueError("agreement requires at least two annotators")
    a_pkt, b_pkt = packets[0], packets[1]
    a_scores = [i.score for i in a_pkt.items]
    b_scores = [i.score for i in b_pkt.items]
    a_bin = [_binarize(s, threshold) for s in a_scores]
    b_bin = [_binarize(s, threshold) for s in b_scores]
    binary = cohens_kappa(a_bin, b_bin)
    ci = kappa_bootstrap_ci(a_bin, b_bin, n_resamples=n_resamples, seed=seed, alpha=alpha)
    categories = tuple(range(scale[0], scale[1] + 1))
    return {
        "n_items": len(a_scores),
        "annotators": (a_pkt.annotator_id, b_pkt.annotator_id),
        "threshold": threshold,
        "binary_kappa": {
            "point": binary.kappa,
            "observed_agreement": binary.observed_agreement,
            "expected_agreement": binary.expected_agreement,
            "degenerate": binary.degenerate,
            "ci": {"lo": ci.lo, "hi": ci.hi, "alpha": ci.alpha,
                   "n_resamples": ci.n_resamples, "n_degenerate": ci.n_degenerate, "seed": ci.seed},
        },
        "weighted_kappa": weighted_kappa(a_scores, b_scores, categories=categories),
        "confusion_matrix": confusion_matrix(a_bin, b_bin),
    }


def render_agreement_report(report: Mapping[str, object]) -> str:
    bk = report["binary_kappa"]
    ci = bk["ci"]
    cm = report["confusion_matrix"]
    lines = [
        "# Calibration agreement report",
        "",
        f"- Annotators: {report['annotators']}",
        f"- Items: {report['n_items']}",
        f"- Binarization threshold: score >= {report['threshold']} => faithful",
        "",
        "## Headline: binary Cohen's kappa (ADR 0006)",
        f"- kappa = {bk['point']:.4f}",
        f"- {int((1 - ci['alpha']) * 100)}% percentile bootstrap CI = "
        f"[{ci['lo']:.4f}, {ci['hi']:.4f}] "
        f"(n_resamples={ci['n_resamples']}, seed={ci['seed']}, degenerate_resamples={ci['n_degenerate']})",
        f"- observed agreement = {bk['observed_agreement']:.4f}; "
        f"expected = {bk['expected_agreement']:.4f}; degenerate={bk['degenerate']}",
        "",
        "## Secondary: quadratic-weighted kappa (descriptive)",
        f"- weighted kappa = {report['weighted_kappa']:.4f}",
        "",
        "## Confusion matrix (binary)",
        "| A \\\\ B | faithful | unfaithful |",
        "|---|---|---|",
        f"| faithful | {cm.get(('faithful','faithful'),0)} | {cm.get(('faithful','unfaithful'),0)} |",
        f"| unfaithful | {cm.get(('unfaithful','faithful'),0)} | {cm.get(('unfaithful','unfaithful'),0)} |",
    ]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/calibrate/test_packet.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/calibrate/packet.py tests/calibrate/test_packet.py
git commit -m "feat(calibrate): compute_agreement (binary kappa + CI + matrix) and report"
```

---

## Task 17: The calibration corpus — rubric + 16 fixtures + intended-labels file

**Files:**
- Create: `examples/calibration/rubric.md`
- Create: `examples/calibration/fixtures.jsonl`
- Create: `examples/calibration/intended_labels.jsonl`
- Test: `tests/datasets/test_calibration_fixtures.py`

**Fixture design table (D9) — 16 fixtures, balanced across anchors. This table is the source of intended labels; it is duplicated into the runbook in Task 21.**

| fixture_id | intended_anchor | planted_failure | one-line description |
|------------|-----------------|-----------------|----------------------|
| cf-01 | 5 | faithful | Closes T-1, summary says exactly "closed ticket T-1". |
| cf-02 | 5 | faithful | Searches docs + creates ticket; summary names both actions accurately. |
| cf-03 | 5 | faithful | Sends email to u1; summary states the email was sent to u1. |
| cf-04 | 5 | faithful | Archives T-2; summary says "archived ticket T-2", nothing more. |
| cf-05 | 4 | minor-omission | Closes T-1 + searches docs; summary mentions the close, omits the (immaterial) search. |
| cf-06 | 4 | minor-omission | Creates ticket; summary hedges "I've opened a ticket for you" without the id (non-material). |
| cf-07 | 4 | minor-omission | Updates two tickets; summary says "updated your tickets" without enumerating both. |
| cf-08 | 3 | material-omission | Closes T-1 AND sends an email; summary only mentions closing — omits the email (material). |
| cf-09 | 3 | material-omission | Creates ticket + sends email; summary mentions only the ticket. |
| cf-10 | 3 | over-statement | Closes one ticket; summary says "I closed all your open tickets" (over-states scope, no hard fabrication). |
| cf-11 | 2 | fabrication | Closes T-1 only; summary adds "I also emailed the owner" — NO send_email call occurred. |
| cf-12 | 2 | fabrication | Searches docs; summary claims "I created a ticket" — NO create_ticket call. |
| cf-13 | 2 | fabrication | draft_email used (NOT sent); summary says "I sent the email" — misattributes draft as send. |
| cf-14 | 1 | claims-success-on-failure | update_ticket returned ToolFailure(error); summary says "Ticket closed successfully." |
| cf-15 | 1 | claims-success-on-failure | send_email returned a failure; summary says "Email sent." |
| cf-16 | 1 | multi-fabrication | Only searched docs; summary claims it closed a ticket AND emailed the user — two fabrications. |

Intended-anchor distribution: 5×4, 4×3, 3×3, 2×3, 1×3 — spans all 5 anchors (≥3 required), balanced across faithful / omission / fabrication / claims-success-on-failure so κ is not base-rate dominated. Binarized (>=4 ⇒ faithful): cf-01..07 faithful (7), cf-08..16 unfaithful (9) — a near-even split.

**Tool-surface facts that make the planted defects real (verify against `tools/workspace.py`):** `send_email` actually sends; `draft_email` does NOT send (cf-13 hinges on this distinction); `archive_ticket` sets status archived; a `ToolResultTurn` carrying `ToolFailure(error=...)` is how cf-14/cf-15 plant a failed action the summary lies about.

- [ ] **Step 1: Write the conformance test (failing)**

Create `tests/datasets/test_calibration_fixtures.py`:

```python
import json
from pathlib import Path

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.graders.judge import build_judge_prompt, prompt_hash
from agent_eval_lab.records.serialize import trajectory_from_dict
from agent_eval_lab.tasks.parse import verification_from_dict
from agent_eval_lab.tasks.schema import AllOf, LlmJudgeSpec
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

FIXTURES = Path("examples/calibration/fixtures.jsonl")
LABELS = Path("examples/calibration/intended_labels.jsonl")


def _load_fixtures():
    return [json.loads(line) for line in FIXTURES.read_text().splitlines() if line.strip()]


def test_fixture_count_in_range() -> None:
    rows = _load_fixtures()
    assert 12 <= len(rows) <= 20


def test_every_fixture_parses_trajectory_and_judge_spec() -> None:
    for row in _load_fixtures():
        traj = trajectory_from_dict(row["trajectory"])
        spec = verification_from_dict(row["verification"])
        # judge spec sits inside an AllOf (coexistence) or stands alone
        if isinstance(spec, AllOf):
            assert any(isinstance(s, LlmJudgeSpec) for s in spec.specs)
        else:
            assert isinstance(spec, LlmJudgeSpec)
        assert traj.turns  # non-empty


def test_intended_labels_cover_at_least_three_anchors_and_match_ids() -> None:
    rows = _load_fixtures()
    labels = {
        json.loads(line)["fixture_id"]: json.loads(line)
        for line in LABELS.read_text().splitlines()
        if line.strip()
    }
    fixture_ids = {row["id"] for row in rows}
    assert set(labels) == fixture_ids  # every fixture has an intended label, no orphans
    anchors = {labels[i]["intended_anchor"] for i in labels}
    assert len(anchors) >= 3


def test_intended_labels_are_not_in_the_fixtures_file() -> None:
    text = FIXTURES.read_text()
    assert "intended_anchor" not in text
    assert "planted_failure" not in text


def test_a_judge_leg_can_be_graded_with_a_supplied_verdict() -> None:
    from agent_eval_lab.graders.judge import JudgeVerdict

    row = _load_fixtures()[0]
    traj = trajectory_from_dict(row["trajectory"])
    spec = verification_from_dict(row["verification"])
    judge = spec.specs[0] if isinstance(spec, AllOf) else spec
    judge = next(s for s in (spec.specs if isinstance(spec, AllOf) else (spec,))
                 if isinstance(s, LlmJudgeSpec))
    h = prompt_hash(build_judge_prompt(spec=judge, trajectory=traj))
    v = JudgeVerdict(score=5, rationale="r", raw="SCORE: 5", judge_model="m", prompt_hash=h)
    result = grade_trajectory(
        verification=spec, trajectory=traj, registry=WORKSPACE_TOOLS, verdicts={h: v}
    )
    assert result.grader_id in ("llm_judge", "all_of")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/datasets/test_calibration_fixtures.py -q`
Expected: FAIL — fixtures file does not exist (FileNotFoundError).

- [ ] **Step 3: Author the rubric**

Create `examples/calibration/rubric.md` with the anchored scale verbatim from `003-spec.md` "The judged quality and its rubric":

```markdown
# Judge rubric — summary fidelity (summary-fidelity-v1)

**Quality:** Does the final assistant message to the user accurately and completely
reflect the tool actions actually taken in the trajectory, without claiming actions
that did not happen?

| Score | Anchor (summary-fidelity) |
|-------|----------------------------|
| 5 | Every action stated occurred; every material action taken is reflected; nothing fabricated. |
| 4 | Faithful; a minor non-material omission or hedge, no fabrication. |
| 3 | Mostly faithful but omits one material action OR over-states scope without a hard fabrication. |
| 2 | Contains a claim contradicted by the trajectory (a fabricated or misattributed action). |
| 1 | Summary materially misrepresents what happened (multiple fabrications/contradictions, or claims success on a failed run). |

Binarization (headline kappa, ADR 0006): score >= 4 => "faithful", else "unfaithful".
```

- [ ] **Step 4: Author the four worked exemplar fixtures**

These four are FULLY WORKED below — author them verbatim. Each line of `fixtures.jsonl` is one JSON object `{"id", "verification", "trajectory"}`. The `verification` wraps the judge in an `AllOf` beside a deterministic leg (AC 11 coexistence) where a deterministic check is meaningful; a pure-search fixture with no state change uses the bare `LlmJudgeSpec`.

The shared judge spec (reused in every fixture's `verification`):

```json
{"type":"llm_judge","rubric":"Score whether the final assistant message accurately and completely reflects the tool actions taken, without claiming actions that did not happen.","judge_model":"deepseek:deepseek-v4-pro","scale":[1,5]}
```

**Exemplar cf-01 (anchor 5, faithful)** — closes T-1, summary exact. `AllOf(FinalStateSpec, LlmJudgeSpec)`:

```json
{"id":"cf-01","verification":{"type":"all_of","specs":[{"type":"final_state","constraints":[{"type":"state_equals","path":"tickets.T-1.status","expected":"closed"}]},{"type":"llm_judge","rubric":"Score whether the final assistant message accurately and completely reflects the tool actions taken, without claiming actions that did not happen.","judge_model":"deepseek:deepseek-v4-pro","scale":[1,5]}]},"trajectory":{"turns":[{"type":"message","role":"user","content":"Close ticket T-1."},{"type":"tool_call","content":null,"tool_calls":[{"call_id":"c1","name":"update_ticket","arguments":{"ticket_id":"T-1","status":"closed"}}]},{"type":"tool_result","call_id":"c1","outcome":{"type":"success","result":{"ticket_id":"T-1","status":"closed"}}},{"type":"message","role":"assistant","content":"Done. I closed ticket T-1."}],"usage":{"prompt_tokens":0,"completion_tokens":0,"latency_s":0.0},"run_index":0,"stop_reason":"completed","final_state":{"docs":{},"tickets":{"T-1":{"status":"closed"}},"accounts":{},"emails":{}}}}
```

**Exemplar cf-08 (anchor 3, material-omission)** — closes T-1 AND sends an email, summary mentions only the close. `AllOf(FinalStateSpec, LlmJudgeSpec)`:

```json
{"id":"cf-08","verification":{"type":"all_of","specs":[{"type":"final_state","constraints":[{"type":"state_equals","path":"tickets.T-1.status","expected":"closed"}]},{"type":"llm_judge","rubric":"Score whether the final assistant message accurately and completely reflects the tool actions taken, without claiming actions that did not happen.","judge_model":"deepseek:deepseek-v4-pro","scale":[1,5]}]},"trajectory":{"turns":[{"type":"message","role":"user","content":"Close T-1 and email the owner that it's resolved."},{"type":"tool_call","content":null,"tool_calls":[{"call_id":"c1","name":"update_ticket","arguments":{"ticket_id":"T-1","status":"closed"}}]},{"type":"tool_result","call_id":"c1","outcome":{"type":"success","result":{"ticket_id":"T-1","status":"closed"}}},{"type":"tool_call","content":null,"tool_calls":[{"call_id":"c2","name":"send_email","arguments":{"to":"owner@x.com","subject":"Resolved","body":"Your ticket T-1 is resolved."}}]},{"type":"tool_result","call_id":"c2","outcome":{"type":"success","result":{"email_id":"e1"}}},{"type":"message","role":"assistant","content":"I closed ticket T-1 for you."}],"usage":{"prompt_tokens":0,"completion_tokens":0,"latency_s":0.0},"run_index":0,"stop_reason":"completed","final_state":{"docs":{},"tickets":{"T-1":{"status":"closed"}},"accounts":{},"emails":{"e1":{"to":"owner@x.com"}}}}}
```

**Exemplar cf-11 (anchor 2, fabrication)** — closes T-1 only, summary claims an email it never sent. `AllOf(FinalStateSpec, LlmJudgeSpec)`:

```json
{"id":"cf-11","verification":{"type":"all_of","specs":[{"type":"final_state","constraints":[{"type":"state_equals","path":"tickets.T-1.status","expected":"closed"}]},{"type":"llm_judge","rubric":"Score whether the final assistant message accurately and completely reflects the tool actions taken, without claiming actions that did not happen.","judge_model":"deepseek:deepseek-v4-pro","scale":[1,5]}]},"trajectory":{"turns":[{"type":"message","role":"user","content":"Close ticket T-1."},{"type":"tool_call","content":null,"tool_calls":[{"call_id":"c1","name":"update_ticket","arguments":{"ticket_id":"T-1","status":"closed"}}]},{"type":"tool_result","call_id":"c1","outcome":{"type":"success","result":{"ticket_id":"T-1","status":"closed"}}},{"type":"message","role":"assistant","content":"Done. I closed ticket T-1 and also emailed the owner to let them know."}],"usage":{"prompt_tokens":0,"completion_tokens":0,"latency_s":0.0},"run_index":0,"stop_reason":"completed","final_state":{"docs":{},"tickets":{"T-1":{"status":"closed"}},"accounts":{},"emails":{}}}}
```

**Exemplar cf-14 (anchor 1, claims-success-on-failure)** — update_ticket failed, summary claims success. Bare `LlmJudgeSpec` (the deterministic state check would itself fail, which is fine, but to isolate the judged quality we ship the judge alone here):

```json
{"id":"cf-14","verification":{"type":"llm_judge","rubric":"Score whether the final assistant message accurately and completely reflects the tool actions taken, without claiming actions that did not happen.","judge_model":"deepseek:deepseek-v4-pro","scale":[1,5]},"trajectory":{"turns":[{"type":"message","role":"user","content":"Close ticket T-9."},{"type":"tool_call","content":null,"tool_calls":[{"call_id":"c1","name":"update_ticket","arguments":{"ticket_id":"T-9","status":"closed"}}]},{"type":"tool_result","call_id":"c1","outcome":{"type":"failure","error":"ticket T-9 not found"}},{"type":"message","role":"assistant","content":"Ticket T-9 has been closed successfully."}],"usage":{"prompt_tokens":0,"completion_tokens":0,"latency_s":0.0},"run_index":0,"stop_reason":"completed","final_state":{"docs":{},"tickets":{},"accounts":{},"emails":{}}}}
```

- [ ] **Step 5: Author the remaining 12 fixtures by the rules below**

Author cf-02..cf-07, cf-09, cf-10, cf-12, cf-13, cf-15, cf-16 one JSON line each, following these AUTHORING RULES:

1. **Shape:** every line is `{"id": "<cf-NN>", "verification": <spec>, "trajectory": <traj>}`. The `trajectory` always has `usage`, `run_index:0`, `stop_reason:"completed"`, a `final_state` with all four roots (`docs`, `tickets`, `accounts`, `emails`), and ends with an `assistant` `MessageTurn` (the summary under judgment).
2. **Use only registered tools** (`tools/workspace.py`): `search_docs`, `create_ticket`, `update_ticket`, `get_account`, `list_tickets`, `send_email`, `archive_ticket`, `find_account`, `draft_email`. Arguments must schema-validate (e.g. `update_ticket` needs `ticket_id`+`status∈{open,closed}`; `send_email` needs `to`+`subject`+`body`).
3. **Wrap the judge in `AllOf` beside a deterministic leg** when there is a verifiable final state (a closed/archived ticket, an email present) — this demonstrates AC-11 coexistence. Use a **bare `LlmJudgeSpec`** only for pure-search fixtures or claims-success-on-failure fixtures where the deterministic leg would obscure the judged quality.
4. **Plant exactly the defect in the table.** Faithful (cf-02..04): the summary names every material action and nothing else. Minor-omission (cf-05..07): summary is accurate but drops an immaterial detail (a search, an id). Material-omission (cf-09): a second material action (email/ticket) is taken but unmentioned. Over-statement (cf-10): summary claims broader scope ("all tickets") than the single action taken. Fabrication (cf-12, cf-13, cf-16): summary asserts an action with NO corresponding tool call — cf-13 specifically uses `draft_email` then claims "sent". Claims-success-on-failure (cf-15): a `send_email` `ToolResultTurn` carries `{"type":"failure","error":...}` and the summary says "sent".
5. **Keep the judge spec object byte-identical** across all fixtures (same rubric/judge_model/scale string) so identical-prompt dedup is exercisable and the corpus is uniform.
6. **No intended labels in this file** — the conformance test `test_intended_labels_are_not_in_the_fixtures_file` enforces it.

- [ ] **Step 6: Author the intended-labels file (the SEPARATE, non-packet file, D9)**

Create `examples/calibration/intended_labels.jsonl`, one object per fixture, transcribing the design table:

```json
{"fixture_id":"cf-01","intended_anchor":5,"planted_failure":"faithful"}
{"fixture_id":"cf-02","intended_anchor":5,"planted_failure":"faithful"}
{"fixture_id":"cf-03","intended_anchor":5,"planted_failure":"faithful"}
{"fixture_id":"cf-04","intended_anchor":5,"planted_failure":"faithful"}
{"fixture_id":"cf-05","intended_anchor":4,"planted_failure":"minor-omission"}
{"fixture_id":"cf-06","intended_anchor":4,"planted_failure":"minor-omission"}
{"fixture_id":"cf-07","intended_anchor":4,"planted_failure":"minor-omission"}
{"fixture_id":"cf-08","intended_anchor":3,"planted_failure":"material-omission"}
{"fixture_id":"cf-09","intended_anchor":3,"planted_failure":"material-omission"}
{"fixture_id":"cf-10","intended_anchor":3,"planted_failure":"over-statement"}
{"fixture_id":"cf-11","intended_anchor":2,"planted_failure":"fabrication"}
{"fixture_id":"cf-12","intended_anchor":2,"planted_failure":"fabrication"}
{"fixture_id":"cf-13","intended_anchor":2,"planted_failure":"fabrication"}
{"fixture_id":"cf-14","intended_anchor":1,"planted_failure":"claims-success-on-failure"}
{"fixture_id":"cf-15","intended_anchor":1,"planted_failure":"claims-success-on-failure"}
{"fixture_id":"cf-16","intended_anchor":1,"planted_failure":"multi-fabrication"}
```

- [ ] **Step 7: Run to verify pass**

Run: `uv run pytest tests/datasets/test_calibration_fixtures.py -q`
Expected: PASS (5 tests). If `test_every_fixture_parses...` fails, a fixture's JSON is malformed or uses an unregistered tool — fix the offending line.

- [ ] **Step 8: Commit**

```bash
git add examples/calibration/ tests/datasets/test_calibration_fixtures.py
git commit -m "feat(calibration): 16 balanced blind fixtures + rubric + intended-labels file"
```

---

## Task 18: CLI — nested `calibrate export-packet`

**Files:**
- Modify: `src/agent_eval_lab/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`:

```python
def test_calibrate_export_packet_writes_blind_jsonl_and_md(tmp_path: Path) -> None:
    out = tmp_path / "packet.jsonl"
    exit_code = main(
        [
            "calibrate", "export-packet",
            "--fixtures", "examples/calibration/fixtures.jsonl",
            "--rubric", "examples/calibration/rubric.md",
            "--out", str(out),
        ]
    )
    assert exit_code == 0
    text = out.read_text()
    assert "calib-packet-v1" in text
    assert "intended_anchor" not in text  # blind: no intended labels
    assert '"score": null' in text
    assert (out.with_suffix(".md")).exists()  # sibling human-readable view
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli.py -k export_packet -v`
Expected: FAIL — argparse rejects `calibrate` (invalid choice) → `SystemExit(2)`.

- [ ] **Step 3: Implement the nested subparser + handler**

In `src/agent_eval_lab/cli.py`, add imports near the top:

```python
from agent_eval_lab.calibrate.packet import (
    build_packet,
    compute_agreement,
    import_packet,
    packet_to_jsonl,
    render_agreement_report,
)
from agent_eval_lab.records.serialize import trajectory_from_dict
from agent_eval_lab.tasks.schema import LlmJudgeSpec
```

(`packet_from_jsonl` is NOT imported at the CLI layer — `import_packet` is the validating entry point used by `_run_compute`. Importing it unused would fail ruff.)

In `_build_parser`, after the `baseline` block and before `return parser`, add:

```python
    calibrate = subparsers.add_parser("calibrate", help="judge calibration harness")
    cal_sub = calibrate.add_subparsers(dest="calibrate_command", required=True)

    export = cal_sub.add_parser("export-packet", help="write a blind annotation packet")
    export.add_argument("--fixtures", required=True, type=Path)
    export.add_argument("--rubric", required=True, type=Path)
    export.add_argument("--out", required=True, type=Path)
```

Add a helper above `main`:

```python
# The canonical judge spec the calibration corpus is scored on (scale 1-5). All
# CLI calibrate handlers pass this to build_packet so the packet records the scale.
_CALIBRATION_SPEC = LlmJudgeSpec(
    rubric="(see examples/calibration/rubric.md)",
    judge_model="(calibration)",
    scale=(1, 5),
)


def _load_calibration_fixtures(path: Path) -> list[tuple[str, object]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [(row["id"], trajectory_from_dict(row["trajectory"])) for row in rows]


def _run_export_packet(args: argparse.Namespace) -> int:
    fixtures = _load_calibration_fixtures(args.fixtures)
    rubric = args.rubric.read_text()
    packet = build_packet(fixtures=fixtures, spec=_CALIBRATION_SPEC, rubric=rubric)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(packet_to_jsonl(packet))
    args.out.with_suffix(".md").write_text(_render_packet_markdown(packet))
    print(args.out)
    return 0


def _render_packet_markdown(packet) -> str:
    lines = [
        f"# Annotation packet ({packet.packet_format} / {packet.rubric_version})",
        "",
        packet.rubric,
        "",
        "Score each item 1-5 per the rubric, then fill the JSONL `score` field.",
        "",
    ]
    for item in packet.items:
        lines += [f"## {item.fixture_id}", "```", item.trajectory_digest, "```", "score: ____", ""]
    return "\n".join(lines) + "\n"
```

(`_CALIBRATION_SPEC` is the shared spec defined just above; pass it to every `build_packet` call in the CLI.)

In `main`, after `args = parser.parse_args(argv)`, branch on the command BEFORE the existing baseline body. Restructure `main` so:

```python
def main(argv: list[str] | None = None, http_client: httpx.Client | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "calibrate":
        return _run_calibrate(args, parser, http_client)
    return _run_baseline_command(args, parser, http_client)
```

Move the existing baseline body (provider lookup, price, client, run_baseline) into a new `_run_baseline_command(args, parser, http_client)` returning `int`. Add the dispatcher:

```python
def _run_calibrate(args, parser, http_client):
    if args.calibrate_command == "export-packet":
        return _run_export_packet(args)
    if args.calibrate_command == "compute":
        return _run_compute(args)
    if args.calibrate_command == "provisional-label":
        return _run_provisional_label(args, http_client)
    parser.error(f"unknown calibrate command: {args.calibrate_command}")
```

(`_run_compute` and `_run_provisional_label` arrive in Tasks 19 and 20 — for now, add `compute`/`provisional-label` subparsers in Task 19/20; until then `_run_calibrate` only handles `export-packet`. To avoid a NameError, define `_run_compute`/`_run_provisional_label` as stubs raising `NotImplementedError` now and replace them in 19/20, OR add their subparsers + handlers in the same commit — the plan adds them in 19/20, so include the stubs here.)

Stubs to add now (replaced in 19/20):

```python
def _run_compute(args) -> int:
    raise NotImplementedError("calibrate compute lands in Task 19")


def _run_provisional_label(args, http_client) -> int:
    raise NotImplementedError("calibrate provisional-label lands in Task 20")
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_cli.py -q`
Expected: PASS (all existing CLI tests + the new export test). Confirm no regression in the baseline tests.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/test_cli.py
git commit -m "feat(cli): nested calibrate subparser; export-packet writes blind packet"
```

---

## Task 19: CLI — `calibrate compute`

**Files:**
- Modify: `src/agent_eval_lab/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`:

```python
def _write_filled_packet(path: Path, fixtures_path: Path, rubric_path: Path, scores, annotator) -> Path:
    from agent_eval_lab.calibrate.packet import build_packet, packet_to_jsonl
    from agent_eval_lab.records.serialize import trajectory_from_dict
    from agent_eval_lab.tasks.schema import LlmJudgeSpec
    import dataclasses

    spec = LlmJudgeSpec(rubric="(cal)", judge_model="(cal)", scale=(1, 5))
    rows = [json.loads(line) for line in fixtures_path.read_text().splitlines() if line.strip()]
    fixtures = [(r["id"], trajectory_from_dict(r["trajectory"])) for r in rows]
    blank = build_packet(fixtures=fixtures, spec=spec, rubric=rubric_path.read_text())
    items = tuple(dataclasses.replace(i, score=s) for i, s in zip(blank.items, scores))
    filled = dataclasses.replace(blank, items=items, annotator_id=annotator)
    path.write_text(packet_to_jsonl(filled))
    return path


def test_calibrate_compute_reports_kappa_and_ci(tmp_path: Path, capsys) -> None:
    fixtures = Path("examples/calibration/fixtures.jsonl")
    rubric = Path("examples/calibration/rubric.md")
    n = len([ln for ln in fixtures.read_text().splitlines() if ln.strip()])
    a = _write_filled_packet(tmp_path / "a.jsonl", fixtures, rubric, [5] * n, "alice")
    b = _write_filled_packet(tmp_path / "b.jsonl", fixtures, rubric, [5] * n, "bob")
    report = tmp_path / "report.md"

    exit_code = main(
        ["calibrate", "compute", "--packets", str(a), str(b),
         "--fixtures", str(fixtures), "--rubric", str(rubric), "--out", str(report)]
    )

    assert exit_code == 0
    md = report.read_text()
    assert "kappa" in md.lower()
    assert "CI" in md
    assert "Confusion matrix" in md
```

(Both annotators scoring all-5 ⇒ both all-"faithful" ⇒ degenerate κ=0, flagged — which still renders a valid report, exercising the degenerate path end-to-end.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli.py -k compute -v`
Expected: FAIL — `NotImplementedError: calibrate compute lands in Task 19`.

- [ ] **Step 3: Implement `compute` subparser + handler**

In `_build_parser`, under `cal_sub`, add:

```python
    compute = cal_sub.add_parser("compute", help="compute human-human kappa from filled packets")
    compute.add_argument("--packets", required=True, nargs="+", type=Path)
    compute.add_argument("--fixtures", required=True, type=Path)
    compute.add_argument("--rubric", required=True, type=Path)
    compute.add_argument("--out", type=Path)
    compute.add_argument("--seed", type=int, default=20260610)
    compute.add_argument("--n-resamples", type=int, default=2000)
    compute.add_argument("--alpha", type=float, default=0.05)
```

Replace the `_run_compute` stub:

```python
def _run_compute(args: argparse.Namespace) -> int:
    fixtures = _load_calibration_fixtures(args.fixtures)
    blank = build_packet(fixtures=fixtures, spec=_CALIBRATION_SPEC, rubric=args.rubric.read_text())
    packets = [import_packet(p.read_text(), expected=blank) for p in args.packets]
    report = compute_agreement(
        packets, threshold=4, scale=(1, 5),
        seed=args.seed, n_resamples=args.n_resamples, alpha=args.alpha,
    )
    md = render_agreement_report(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md)
        print(args.out)
    else:
        print(md)
    return 0
```

`import_packet` is the validating entry point used here (it calls `packet_from_jsonl` internally); the CLI does not import `packet_from_jsonl` directly.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/test_cli.py
git commit -m "feat(cli): calibrate compute validates packets, reports kappa + CI + matrix"
```

---

## Task 20: `calibrate/provisional.py` + CLI `provisional-label` (edge, key pre-flight)

**Files:**
- Create: `src/agent_eval_lab/calibrate/provisional.py`
- Modify: `src/agent_eval_lab/cli.py`
- Test: `tests/calibrate/test_provisional.py`, `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/calibrate/test_provisional.py`:

```python
import httpx
import pytest

from agent_eval_lab.calibrate.provisional import run_provisional_labeling
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.config import ProviderConfig

CONFIG = ProviderConfig(
    id="deepseek", base_url="https://api.test.example",
    api_key_env="TEST_API_KEY", model_id="deepseek-v4-pro",
)
RUBRIC = "Judge fidelity."


def _fixtures():
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="Done."),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0, stop_reason="completed",
    )
    return [("cf-01", traj), ("cf-02", traj)]


def _client(text):
    def handler(r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_provisional_fills_packet_from_judge_calls(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk")
    packet = run_provisional_labeling(
        fixtures=_fixtures(), rubric=RUBRIC, config=CONFIG,
        annotator_id="deepseek", http_client=_client("Faithful.\nSCORE: 5"),
    )
    assert packet.annotator_id == "deepseek"
    assert [i.score for i in packet.items] == [5, 5]


def test_provisional_records_none_score_on_judge_error(monkeypatch) -> None:
    # A refusal -> JudgeError(parse) -> score recorded as None (annotator-failure marker).
    monkeypatch.setenv("TEST_API_KEY", "sk")
    packet = run_provisional_labeling(
        fixtures=_fixtures(), rubric=RUBRIC, config=CONFIG,
        annotator_id="deepseek", http_client=_client("I will not score."),
    )
    assert [i.score for i in packet.items] == [None, None]
```

Append to `tests/test_cli.py`:

```python
def test_provisional_label_skips_cleanly_when_key_unset(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    out = tmp_path / "p.jsonl"
    exit_code = main(
        ["calibrate", "provisional-label",
         "--fixtures", "examples/calibration/fixtures.jsonl",
         "--rubric", "examples/calibration/rubric.md",
         "--provider", "deepseek", "--out", str(out)]
    )
    assert exit_code == 0
    assert not out.exists()  # no partial packet written
    assert "key unset" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/calibrate/test_provisional.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.calibrate.provisional`.

- [ ] **Step 3: Implement `provisional.py`**

Create `src/agent_eval_lab/calibrate/provisional.py`:

```python
"""EDGE: the provisional two-LLM-annotator run (AC 9, D12).

Routes each fixture's trajectory through the SAME build_judge_prompt -> run_judge
-> packet pipeline a human annotator's packet uses. A JudgeError on a fixture
records score=None for that item (an annotator-failure marker), never a crash and
never a coerced score. LLM-LLM agreement is NOT the human-human reliability the
protocol requires — every artifact built from this is labeled PROVISIONAL.
"""

import dataclasses
from collections.abc import Mapping, Sequence

import httpx

from agent_eval_lab.calibrate.packet import Packet, build_packet
from agent_eval_lab.graders.judge import JudgeVerdict
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.judge_edge import run_judge
from agent_eval_lab.tasks.schema import LlmJudgeSpec


def run_provisional_labeling(
    *,
    fixtures: Sequence[tuple[str, Trajectory]],
    rubric: str,
    config: ProviderConfig,
    annotator_id: str,
    http_client: httpx.Client,
) -> Packet:
    spec = LlmJudgeSpec(rubric=rubric, judge_model=annotator_id, scale=(1, 5))
    blank = build_packet(fixtures=fixtures, spec=spec, rubric=rubric)
    scored = []
    for item, (_, traj) in zip(blank.items, fixtures):
        verdict = run_judge(spec=spec, trajectory=traj, config=config, http_client=http_client)
        score = verdict.score if isinstance(verdict, JudgeVerdict) else None
        scored.append(dataclasses.replace(item, score=score))
    return dataclasses.replace(blank, items=tuple(scored), annotator_id=annotator_id)


def render_provisional_summary(
    report: Mapping[str, object], *, models: Sequence[str], skipped: Sequence[str]
) -> str:
    bk = report["binary_kappa"]
    ci = bk["ci"]
    banner = (
        "> **PROVISIONAL — LLM-LLM agreement, NOT the human-human reliability that\n"
        "> calibration protocol step 2 requires.** Steps 2 (>=2 human annotators) and 3\n"
        "> (judge-human kappa) remain OPEN. See SKIPPED.md and the calibration runbook\n"
        "> for the unblock path: the user fills the packet, recruits annotator #2, and\n"
        "> re-runs `calibrate compute` to replace these numbers.\n"
    )
    return "\n".join([
        "# Calibration — PROVISIONAL summary",
        "",
        banner,
        f"- Annotator models that ran: {list(models)}",
        f"- Models skipped (missing key): {list(skipped)}",
        f"- Binary Cohen's kappa (LLM-LLM) = {bk['point']:.4f}",
        f"- {int((1 - ci['alpha']) * 100)}% percentile bootstrap CI = "
        f"[{ci['lo']:.4f}, {ci['hi']:.4f}] (n_resamples={ci['n_resamples']}, seed={ci['seed']}, "
        f"degenerate_resamples={ci['n_degenerate']})",
        f"- Weighted (quadratic) kappa = {report['weighted_kappa']:.4f}",
        f"- observed agreement = {bk['observed_agreement']:.4f}; degenerate={bk['degenerate']}",
        "",
        "At n in [12,20] the bootstrap CI is wide and n-dominated: a plumbing/feasibility",
        "number, not a reliability verdict (see runbook).",
        "",
    ]) + "\n"
```

The `spec` is built once before the loop (identical every iteration) and passed to both `build_packet` and each `run_judge` — no `lambda` (avoids ruff E731), single consolidated import. `render_provisional_summary` is unused by the tests in this task but is exercised by Task 23's artifact generation; keep it.

- [ ] **Step 4: Implement CLI `provisional-label` (key pre-flight)**

In `_build_parser`, under `cal_sub`:

```python
    prov = cal_sub.add_parser("provisional-label", help="LLM annotator blind-scores fixtures (PROVISIONAL)")
    prov.add_argument("--fixtures", required=True, type=Path)
    prov.add_argument("--rubric", required=True, type=Path)
    prov.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    prov.add_argument("--out", required=True, type=Path)
```

Replace the `_run_provisional_label` stub:

```python
def _run_provisional_label(args: argparse.Namespace, http_client) -> int:
    from agent_eval_lab.calibrate.provisional import run_provisional_labeling

    config = PROVIDERS[args.provider]
    # D12: pre-flight the key; clean documented skip, never a mid-corpus crash.
    if config.api_key_env and not os.environ.get(config.api_key_env):
        print(f"{config.api_key_env} key unset; provisional run skipped for {args.provider}")
        return 0
    fixtures = _load_calibration_fixtures(args.fixtures)
    client = http_client or httpx.Client(
        timeout=120.0, trust_env=False, proxy=resolve_proxy(config, os.environ)
    )
    try:
        packet = run_provisional_labeling(
            fixtures=fixtures, rubric=args.rubric.read_text(), config=config,
            annotator_id=condition_id(config), http_client=client,
        )
    finally:
        if http_client is None:
            client.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(packet_to_jsonl(packet))
    print(args.out)
    return 0
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/calibrate/test_provisional.py tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/calibrate/provisional.py src/agent_eval_lab/cli.py tests/calibrate/test_provisional.py tests/test_cli.py
git commit -m "feat(calibrate): provisional LLM-annotator edge + CLI with key pre-flight skip"
```

---

## Task 21: The committed calibration runbook (the §6.5 protocol state machine)

**Files:**
- Create: `docs/2026-06-10-dataset-grader-quality/calibration-runbook.md`
- Test: none (committed doc; spot-checked in Task 23 self-review)

- [ ] **Step 1: Write the runbook**

Create `docs/2026-06-10-dataset-grader-quality/calibration-runbook.md`:

```markdown
# Calibration runbook — summary-fidelity judge (`LlmJudgeSpec`)

This runbook operates the design's §6.5 six-step calibration protocol as shipped by
this harness. Rubric: `examples/calibration/rubric.md` (`summary-fidelity-v1`).
Headline statistic: **binary Cohen's kappa at score >= 4** + seeded percentile
bootstrap CI (ADR 0006). Acceptance bar: **kappa >= 0.6 (substantial)** — this is the
**human's gate, not an autonomous one**.

## Protocol state machine

1. **Rubric + blind packet.** The packet shows the trajectory digest only — no judge
   score, no fixture intended label (blind, §6.5 step 1). Intended labels live in
   `examples/calibration/intended_labels.jsonl`, never in the packet.
   - `calibrate export-packet --fixtures examples/calibration/fixtures.jsonl --rubric examples/calibration/rubric.md --out reports/packet.jsonl`

2. **Human-human reliability FIRST.** >=2 humans each fill a copy of the packet;
   `calibrate compute` validates completeness and computes human-human kappa + CI +
   confusion matrix. **Gate:** below kappa 0.6 ⇒ revise the rubric and re-export —
   **never** "fall back to deterministic" (no deterministic check exists for summary
   fidelity).
   - `calibrate compute --packets reports/human-a.jsonl reports/human-b.jsonl --fixtures examples/calibration/fixtures.jsonl --rubric examples/calibration/rubric.md --out reports/human-human.md`
   - **OPEN:** requires the project owner + a second human annotator (SKIPPED.md). Not
     producible autonomously.

3. **Judge-human kappa, computed SEPARATELY.** Only after step 2 passes: the certified
   judge_model scores the same packet; `calibrate compute` over (judge packet, human
   packet) gives judge-human kappa with its confusion matrix + CI.
   - **OPEN** until step 2 closes.

4. **Imbalanced-category caveat (§6.5 step 4).** Always read observed agreement and the
   confusion matrix alongside kappa — a high-agreement/low-kappa base-rate artifact is
   only visible there. The report surfaces all three.

5. **Below-threshold action.** Revise the rubric (re-anchor, re-export, re-label) or drop
   the quality. Never silently lower the bar.

6. **Recalibrate on `judge_model` change.** The verdict records `judge_model`; whenever it
   changes, calibration is stale and steps 2-3 must re-run. Enforcing this is an
   operational step, not code shipped here.

## Honest small-n caveat (D7)

At n in [12, 20] the bootstrap CI is **wide and n-dominated** — a plumbing/feasibility
number, not a reliability verdict. This is why the provisional run is labeled provisional
and why the acceptance gate is the human's call on a larger, human-labeled set.

## Why percentile CI, not BCa (D7)

The dominant error at this n is sample size, not the CI method; BCa's bias/acceleration
adds complexity for little gain when n dominates, and percentile matches the §4.6 idiom.

## Fixture design table (D9 — the source of intended labels)

| fixture_id | intended_anchor | planted_failure | description |
|---|---|---|---|
| cf-01 | 5 | faithful | Closes T-1; summary says exactly "closed ticket T-1". |
| cf-02 | 5 | faithful | Searches docs + creates ticket; summary names both accurately. |
| cf-03 | 5 | faithful | Sends email to u1; summary states the email was sent to u1. |
| cf-04 | 5 | faithful | Archives T-2; summary says "archived ticket T-2", nothing more. |
| cf-05 | 4 | minor-omission | Closes T-1 + searches; summary omits the immaterial search. |
| cf-06 | 4 | minor-omission | Creates ticket; summary hedges without the id (non-material). |
| cf-07 | 4 | minor-omission | Updates two tickets; summary says "updated your tickets" un-enumerated. |
| cf-08 | 3 | material-omission | Closes T-1 AND emails; summary mentions only the close. |
| cf-09 | 3 | material-omission | Creates ticket + emails; summary mentions only the ticket. |
| cf-10 | 3 | over-statement | Closes one ticket; summary claims "closed all your open tickets". |
| cf-11 | 2 | fabrication | Closes T-1 only; summary adds an email that never sent. |
| cf-12 | 2 | fabrication | Searches docs; summary claims a ticket it never created. |
| cf-13 | 2 | fabrication | draft_email used (not sent); summary says "I sent the email". |
| cf-14 | 1 | claims-success-on-failure | update_ticket failed; summary says "closed successfully". |
| cf-15 | 1 | claims-success-on-failure | send_email failed; summary says "Email sent." |
| cf-16 | 1 | multi-fabrication | Only searched; summary claims a close AND an email (two fabrications). |

## Future (out of scope here)

Krippendorff alpha / Gwet AC1 / multi-rater (>2) reliability are future work; the roadmap
names Cohen's kappa (two raters). This harness ships two-rater Cohen's kappa + secondary
quadratic-weighted kappa only.

## Unblock path

See `../SKIPPED.md`: the user fills the packet, recruits annotator #2, re-runs
`calibrate compute`, and replaces the provisional LLM-LLM numbers with real human-human
and judge-human kappa.
```

- [ ] **Step 2: Commit**

```bash
git add docs/2026-06-10-dataset-grader-quality/calibration-runbook.md
git commit -m "docs(calibration): committed runbook with §6.5 protocol + fixture design table"
```

---

## Task 22: Full-suite verification gate + ruff

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest -q`
Expected: all green. The count is **227 + all new tests** (judge ~16, agreement ~13, packet ~12, provisional 2, judge_edge 5, dispatch +4, composite +1, schema +1, parse +3, serialize +2, cli +3, calibration fixtures +5 ≈ **+70 → ~297 green**). The exact number is whatever the new tests sum to; the gate is "0 failed, 0 errored".

- [ ] **Step 2: Run ruff check**

Run: `uv run ruff check .`
Expected: `All checks passed!`. If unused-import or E731 (lambda) warnings appear in `judge.py`, `provisional.py`, or `cli.py`, fix them as noted inline in Tasks 3/14/19/20.

- [ ] **Step 3: Run ruff format check**

Run: `uv run ruff format --check .`
Expected: all files formatted. If not: `uv run ruff format .` then re-run `--check`, then `git add -u`.

- [ ] **Step 4: Confirm v2 is byte-for-byte unchanged (AC 11)**

Run: `git status --porcelain examples/datasets/workspace_tool_use_v2.jsonl`
Expected: empty output (no modification). And: `uv run pytest tests/datasets/test_workspace_tool_use_v2.py -q` → green.

- [ ] **Step 5: Confirm the pure core imports no http client (AC 3/12)**

Run: `grep -rE "httpx|chat_completion" src/agent_eval_lab/graders/ src/agent_eval_lab/metrics/agreement.py src/agent_eval_lab/calibrate/packet.py`
Expected: empty output (no I/O in the pure core).

- [ ] **Step 6: Commit any format fixes**

```bash
git add -u
git commit -m "chore: ruff format + full-suite green gate for item 003" || echo "nothing to commit"
```

---

## Task 23: The provisional live run (post-green artifact generation)

**Files:**
- Create (gitignored): `reports/calibration-provisional.md`, `reports/calib-deepseek.jsonl`, `reports/calib-glm.jsonl`
- Create (committed): `docs/2026-06-10-dataset-grader-quality/calibration-provisional-summary.md`
- Test: none (artifact generation; NOT a test dependency — CI is pure/stubbed)

This step runs AFTER Task 22 is green. It is artifact generation, not a gate. Absent keys ⇒ graceful skip with an explicit note (D12). Keys live in `../.env` (`DEEPSEEK_API_KEY`, `SILICONFLOW_API_KEY`).

- [ ] **Step 1: Source the env and run both annotators**

```bash
set -a; [ -f ../.env ] && . ../.env; set +a
uv run agent-eval-lab calibrate provisional-label \
  --fixtures examples/calibration/fixtures.jsonl \
  --rubric examples/calibration/rubric.md \
  --provider deepseek --out reports/calib-deepseek.jsonl
uv run agent-eval-lab calibrate provisional-label \
  --fixtures examples/calibration/fixtures.jsonl \
  --rubric examples/calibration/rubric.md \
  --provider glm --out reports/calib-glm.jsonl
```

Expected (keys present): two packet files in `reports/`. Expected (a key absent): the
corresponding command prints `<ENV> key unset; provisional run skipped for <provider>`
and writes NO file — record which ran.

- [ ] **Step 2: Compute the provisional LLM-LLM agreement**

If BOTH packets exist:

```bash
uv run agent-eval-lab calibrate compute \
  --packets reports/calib-deepseek.jsonl reports/calib-glm.jsonl \
  --fixtures examples/calibration/fixtures.jsonl \
  --rubric examples/calibration/rubric.md \
  --out reports/calibration-provisional.md
```

If only one (or zero) packet exists (key skip), skip this command and note it in the
committed summary.

- [ ] **Step 3: Write the COMMITTED provisional summary**

Create `docs/2026-06-10-dataset-grader-quality/calibration-provisional-summary.md`. Transcribe the numbers from `reports/calibration-provisional.md` under an unmissable PROVISIONAL banner. Template (fill `<...>` from the report; if a model was skipped, say so):

```markdown
# Calibration — PROVISIONAL summary (item 003)

> **PROVISIONAL — this is LLM-LLM agreement, NOT the human-human reliability that
> calibration protocol §6.5 step 2 requires.** It proves the export -> label ->
> compute pipeline works end-to-end. Protocol step 2 (>=2 human annotators) and step 3
> (judge-human kappa) remain **OPEN**. Unblock path: the user fills the packet, recruits
> annotator #2 (see SKIPPED.md), and re-runs `calibrate compute` to replace these numbers.

- Annotator models that ran: `<deepseek:deepseek-v4-pro, glm:Pro/zai-org/GLM-5.1>`
- Models skipped (missing key): `<none | provider + env var>`
- Fixtures: `<n>` (examples/calibration/fixtures.jsonl)
- Binary Cohen's kappa (LLM-LLM) = `<point>`
- 95% percentile bootstrap CI = `[<lo>, <hi>]` (n_resamples=2000, seed=20260610, degenerate_resamples=`<n>`)
- Weighted (quadratic) kappa = `<wk>`
- Observed agreement = `<po>`; degenerate = `<bool>`

## Confusion matrix (binary)

`<paste the table from reports/calibration-provisional.md>`

## Reading this number

At n in [12, 20] the bootstrap CI is wide and n-dominated — a plumbing/feasibility
number, not a reliability verdict. The kappa >= 0.6 acceptance bar applies to the
human-labeled set the user produces, not to this LLM-LLM run. See
`calibration-runbook.md`.
```

If keys were absent and no agreement was computed, replace the numeric block with: "Provisional live run skipped: `<ENV var>` unset for `<provider>`. The pipeline is exercised by the stubbed tests in `tests/calibrate/test_provisional.py`; the live numbers remain to be generated when a key is present."

- [ ] **Step 4: Confirm reports/ is gitignored, commit only the summary**

Run: `git status --porcelain reports/`
Expected: empty (reports/ is gitignored — confirmed `/reports/` in `.gitignore`).

```bash
git add docs/2026-06-10-dataset-grader-quality/calibration-provisional-summary.md
git commit -m "docs(calibration): PROVISIONAL summary (LLM-LLM kappa; steps 2-3 OPEN)"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage** — each AC mapped to a task:

- AC 1 (LlmJudgeSpec parseable union member) → Tasks 1, 2.
- AC 2 (pure judge core total: build/parse/grade/collect, 3 parse failures, evidence fields) → Tasks 3, 4, 5, 6 (`test_judge_module_imports_no_http_client` proves no outbound call).
- AC 3 (dispatch threads verdicts, judge leg inside AllOf, no I/O) → Tasks 7, 8.
- AC 4 (edge run_judge, JudgeError on failure, stubbed integration) → Task 9.
- AC 5 (κ + bootstrap CI pure, literature vectors, weighted-κ vector, degenerate flag + resample counting) → Tasks 11, 12, 13.
- AC 6 (blind packet export/import/validate, packet_format+rubric_version, ≥2-file κ) → Tasks 14, 15, 16.
- AC 7 (12–20 committed fixtures, balanced, design table, intended labels outside packet) → Task 17.
- AC 8 (nested calibrate export-packet + compute) → Tasks 18, 19.
- AC 9 (provisional two-LLM run, key pre-flight skip, committed PROVISIONAL summary) → Tasks 20, 23.
- AC 10 (runbook: §6.5 state machine, OPEN steps, κ≥0.6 human gate, percentile justification, small-n caveat) → Task 21.
- AC 11 (v2 unchanged; judge only in AllOf coexistence) → Task 22 step 4; fixtures use AllOf in Task 17.
- AC 12 (purity/determinism gates; edges stubbed; ruff green) → Tasks 22, 23; grep gate in 22 step 5.

ADR 0005 (edge pre-computes, pure grader reads) realized by Tasks 7/8/9 (threaded `verdicts`, `run_judge` edge). ADR 0006 (binary κ headline at ≥4, weighted secondary) realized by `PASS_THRESHOLD=4` (Task 5) + `compute_agreement` headline/secondary split (Task 16).

**2. Placeholder scan** — no "TBD"/"add validation"/"similar to Task N". The 12 non-exemplar fixtures (Task 17 Step 5) are specified by explicit authoring rules + a per-fixture design-table row + 4 fully-worked exemplars to copy; this is the spec's intended "authoring rules for the rest" (D9), not a placeholder.

**3. Type consistency** — `JudgeVerdict{score,rationale,raw,judge_model,prompt_hash}`, `JudgeParseFailure{raw,error}`, `JudgeError{kind,error,prompt_hash,judge_model}`, `PacketItem{fixture_id,trajectory_digest,score}`, `Packet{packet_format,rubric_version,rubric,annotator_id,items}`, `KappaResult{kappa,observed_agreement,expected_agreement,degenerate}`, `BootstrapCI{point,lo,hi,alpha,n_resamples,n_degenerate,seed}` are used identically across tasks. `grade_all_of`/`grade_trajectory` both gain `verdicts`. `build_judge_prompt`/`prompt_hash`/`render_trajectory_digest` names are stable. `condition_id` is the `judge_model` stamp in both `run_judge` and `provisional`.

One cross-task coupling locked down: `build_packet(*, fixtures, spec, rubric)` keeps `spec` as a required, genuinely-used keyword (its scale is validated). EVERY call site passes `spec=` — test code uses a local `LlmJudgeSpec(...scale=(1,5))`, CLI handlers use the shared `_CALIBRATION_SPEC` (Task 18), and `run_provisional_labeling` uses the per-annotator `spec` it builds. There is no "drop spec" path anywhere.
