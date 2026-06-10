# Weeks 1–2 Tool-Use Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a minimum reproducible tool-use evaluation system — locked immutable data spine, deterministic synthetic `workspace-world`, schema-first AST tool-call grader with a failure taxonomy, OpenAI-compatible provider client, multi-run runner with cost/latency, golden conformance suite, and a baseline report — all functional-core / imperative-shell, TDD red-green-refactor.

**Architecture:** Pure cores in `tasks/`, `tools/`, `graders/`, `metrics/`, `reports/` (frozen kw-only dataclasses, behavior in functions, JSONL round-trippable with explicit `type` discriminators); effects only in `runners/` and the I/O edges of `reports/` + dataset loaders. A single **vendored stdlib JSON-Schema validator** (`tools/jsonschema_mini.py`) is applied identically at the tool-world boundary AND in the AST grader so they agree on "invalid". The provider client and runner are built **test-first against a fake transport and a deterministic fake model** — no live HTTP, no API keys, anywhere in the suite.

**Tech Stack:** Python 3.11+ via `uv` (CI interpreter; do NOT call bare `python`/`pytest`), stdlib only for runtime, `pytest` + `hypothesis` (new dev dep) for tests, `ruff` (select E,F,I,UP; line-length 88).

---

## Locked decisions (judgment calls this plan makes)

These resolve the "Left to the plan" items in `001-spec.md`. Cite these if anything downstream disagrees.

- **The 2–3 tools + state subset (spec §"Left to the plan"; design §5).** Three tools over a `{tickets, docs}` state subset:
  - `search_docs(query: str)` — read-only; selection signal vs the ticket tools.
  - `create_ticket(title: str, priority: "low"|"medium"|"high")` — argument extraction with a **string enum** (`priority`), the natural home for `schema_violation` (e.g. `"urgent"` not in enum, or `1` where a string is required).
  - `update_ticket(ticket_id: str, status: "open"|"closed")` — argument extraction with an id + **status enum**; supports `exact_sequence` (create then update) and `multiset` task shapes.

  This subset is the smallest that exercises tool selection (read vs two writes), enum + type coercion violations, and ordered/unordered multi-call grading. `get_account`/`send_email`/`list_tickets`/`ask_user` from design §5 are **out of scope this slice** (single-turn, no clarification — spec §"Out of scope").
- **Serialization mechanism (spec §"Left to the plan").** Hand-rolled pure `to_dict`/`from_dict` codec module (`tasks/codec.py`), dependency-light. Tagged unions dispatch on the `type` discriminator. No third-party codec.
- **JSON Schema validation approach (spec §"Left to the plan"; design §5/§6).** A **vendored minimal validator** (`tools/jsonschema_mini.py`, stdlib only) supporting `type` (object/string/integer/number/boolean/array), `properties`, `required`, `enum`, `additionalProperties:false`. Rationale: the subset needed is small; vendoring guarantees the world boundary and the grader call the **identical** function (spec hard constraint: "applied identically … so they agree on 'invalid'"); avoids the `jsonschema` → `referencing`/`rpds` (compiled) dependency chain, honoring "dependency-light". **No type coercion** — `"1"` where `integer` is required is a violation, never a pass (design §6/§7).
- **New dev dependency:** `hypothesis` only (property-based tests; spec A4/A6). Added to `[dependency-groups].dev`.
- **Fake-transport / cassette mechanism (spec §"Left to the plan").** The provider client takes an injected `transport` callable `(request: Mapping) -> Mapping`. Tests pass a `FakeTransport` built from a committed JSON cassette (`tests/runners/cassettes/*.json`); CI never opens a socket. The real `httpx`/`urllib` transport is a thin default constructed only when no transport is injected and is **never exercised in tests**.
- **Thin CLI (spec §"Left to the plan", task requirement).** `python -m agent_eval_lab.reports.baseline <runs.jsonl>` renders a baseline report from committed recorded `RunResult`s. This is the `/verify` smoke target.

---

## File structure (created/modified)

```
src/agent_eval_lab/
  tasks/
    __init__.py                 (create)
    tool_calls.py               (create) ExpectedToolCall, ToolCall
    turns.py                    (create) MessageTurn, ToolCallTurn, ToolResultTurn, ToolSuccess, ToolFailure
    verification.py             (create) OutputMatchSpec, ToolCallMatchSpec + dispatch guard
    task.py                     (create) TaskInput, TaskMetadata, Task
    grading.py                  (create) FailureCategory, GradeResult, RunResult, Trajectory
    codec.py                    (create) pure to_dict/from_dict for every record above
    loader.py                   (create, EDGE) read/write Task + RunResult JSONL files
  tools/
    __init__.py                 (create)
    jsonschema_mini.py          (create) vendored minimal validator (pure)
    workspace_world.py          (create) TOOL_SCHEMAS + pure apply()
  graders/
    __init__.py                 (modify) re-exports
    exact_match.py              (modify) migrate GradeResult; grade_exact_match -> OutputMatchSpec scorer
    canonicalize.py             (create) value-preserving idempotent canonicalization (pure)
    ast_tool_match.py           (create) schema-first AST tool-call grader (pure)
    grade.py                    (create) grade_task(verification, trajectory) dispatch (pure)
  runners/
    __init__.py                 (create)
    provider.py                 (create, EDGE) ProviderConfig, build_request, parse_response, ProviderClient
    fake_model.py               (create) deterministic fake model (pure decision fn) — test+CLI support
    runner.py                   (create, EDGE) model<->tool loop, limits, multi-run -> Trajectory/RunResult
  metrics/
    __init__.py                 (create)
    baseline.py                 (create) pure aggregation: pass-over-k, cost/latency, failure counts
  reports/
    __init__.py                 (create)
    baseline.py                 (create) pure report model + renderer + __main__ CLI (write at edge)

tests/                          (mirrors src, plus:)
  tasks/test_codec_roundtrip.py
  tools/test_jsonschema_mini.py
  tools/test_workspace_world.py
  graders/test_exact_match.py   (modify)
  graders/test_canonicalize.py
  graders/test_ast_tool_match.py
  graders/test_grade.py
  graders/test_canonicalize_properties.py
  graders/test_conformance.py
  graders/conformance/*.json    (golden fixtures)
  runners/test_provider.py
  runners/test_fake_model.py
  runners/test_runner.py
  runners/test_runner_determinism.py
  runners/cassettes/*.json    (illustrative — Task 15 test_cassette_replay uses tmp_path; no committed cassettes dir needed; A5 satisfied)
  metrics/test_baseline.py
  reports/test_baseline_report.py
  reports/test_baseline_cli.py

examples/datasets/
  tool_use.jsonl               (create) ~20 full Task JSONL records
  recorded_runs.jsonl          (create) committed RunResults for CLI/report smoke
  tool_selection.jsonl         (delete — replaced by tool_use.jsonl)

docs/
  ARCHITECTURE.md              (modify) reconcile drift
  ROADMAP.md                   (modify) Wk 1–2 -> landed
  superpowers/specs/2026-06-09-agent-eval-pipeline-design.md (modify) §13 delta toward done
  2026-06-10-tool-use-slice/items/dataset-note.md (create) new task format note

pyproject.toml                 (modify) add hypothesis dev dep
```

---

## Phase 1 — Locked record types + JSONL round-trip (Tasks 1–7)

**Verification point (end of phase):** `uv run pytest` passes (2 → ~10+ tests); `uv run ruff check .` and `uv run ruff format --check .` clean. Every record round-trips through JSONL losslessly including `type` discriminators.

### Task 1: Tool-call record types

**Files:**
- Create: `src/agent_eval_lab/tasks/__init__.py`
- Create: `src/agent_eval_lab/tasks/tool_calls.py`
- Test: `tests/tasks/test_codec_roundtrip.py` (created in Task 6; Task 1 has no test of its own — it is exercised by codec round-trip)

- [ ] **Step 1: Create the package marker**

`src/agent_eval_lab/tasks/__init__.py`:

```python
"""Pure task data model: records + codec; JSONL loader at the edge."""
```

- [ ] **Step 2: Create the tool-call record types**

`src/agent_eval_lab/tasks/tool_calls.py`:

```python
"""Spec-time vs run-time tool-call records (design §4.1)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, kw_only=True)
class ExpectedToolCall:
    """Spec-time expected call. No call_id (unknowable when authoring)."""

    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class ToolCall:
    """Run-time observed call. Carries the runtime-generated call_id."""

    call_id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
```

- [ ] **Step 3: Verify it imports**

Run: `uv run python -c "from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add src/agent_eval_lab/tasks/__init__.py src/agent_eval_lab/tasks/tool_calls.py
git commit -m "feat(tasks): add spec-time/run-time tool-call record types"
```

### Task 2: Turn + tool-outcome union types

**Files:**
- Create: `src/agent_eval_lab/tasks/turns.py`

- [ ] **Step 1: Create the turn + outcome records**

`src/agent_eval_lab/tasks/turns.py`:

```python
"""Turns + tool outcomes — tagged unions with explicit discriminators (design §4.2)."""

from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.tasks.tool_calls import ToolCall


@dataclass(frozen=True, kw_only=True)
class MessageTurn:
    role: Literal["system", "user", "assistant"]
    content: str
    type: Literal["message"] = "message"


@dataclass(frozen=True, kw_only=True)
class ToolCallTurn:
    tool_calls: tuple[ToolCall, ...]
    content: str | None = None
    type: Literal["tool_call"] = "tool_call"


@dataclass(frozen=True, kw_only=True)
class ToolSuccess:
    result: Any
    type: Literal["success"] = "success"


@dataclass(frozen=True, kw_only=True)
class ToolFailure:
    error: str
    type: Literal["failure"] = "failure"


ToolOutcome = ToolSuccess | ToolFailure


@dataclass(frozen=True, kw_only=True)
class ToolResultTurn:
    call_id: str
    outcome: ToolOutcome
    type: Literal["tool_result"] = "tool_result"


Turn = MessageTurn | ToolCallTurn | ToolResultTurn
```

- [ ] **Step 2: Verify it imports**

Run: `uv run python -c "from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn, ToolResultTurn, ToolSuccess, ToolFailure; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/agent_eval_lab/tasks/turns.py
git commit -m "feat(tasks): add Turn and ToolOutcome tagged-union records"
```

### Task 3: Verification spec union + dispatch guard

**Files:**
- Create: `src/agent_eval_lab/tasks/verification.py`

- [ ] **Step 1: Create the verification records + open-union guard**

`src/agent_eval_lab/tasks/verification.py`:

```python
"""Verification specs (tool-use subset) + open-union dispatch guard (design §4.3, §13)."""

from dataclasses import dataclass
from typing import Literal

from agent_eval_lab.tasks.tool_calls import ExpectedToolCall


@dataclass(frozen=True, kw_only=True)
class OutputMatchSpec:
    expected_output: str
    normalizer: str | None = None
    type: Literal["output_match"] = "output_match"


@dataclass(frozen=True, kw_only=True)
class ToolCallMatchSpec:
    expected_tool_calls: tuple[ExpectedToolCall, ...]
    match: Literal["exact_sequence", "multiset"] = "exact_sequence"
    type: Literal["tool_call_match"] = "tool_call_match"


VerificationSpec = OutputMatchSpec | ToolCallMatchSpec

_IMPLEMENTED = frozenset({"output_match", "tool_call_match"})


class UnsupportedVerificationError(ValueError):
    """Raised when a VerificationSpec variant is not implemented this slice."""


def ensure_supported(spec_type: str) -> None:
    """Reject unimplemented (final_state/trajectory/execution/judge/all_of) variants."""
    if spec_type not in _IMPLEMENTED:
        raise UnsupportedVerificationError(
            f"verification type {spec_type!r} is not implemented in this slice"
        )
```

- [ ] **Step 2: Verify it imports**

Run: `uv run python -c "from agent_eval_lab.tasks.verification import OutputMatchSpec, ToolCallMatchSpec, ensure_supported, UnsupportedVerificationError; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/agent_eval_lab/tasks/verification.py
git commit -m "feat(tasks): add tool-use VerificationSpec subset + dispatch guard"
```

### Task 4: Task + metadata records

**Files:**
- Create: `src/agent_eval_lab/tasks/task.py`

- [ ] **Step 1: Create the Task records**

`src/agent_eval_lab/tasks/task.py`:

```python
"""Task schema (design §4.4). Single-turn only this slice (no scripted_user)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from agent_eval_lab.tasks.turns import MessageTurn
from agent_eval_lab.tasks.verification import VerificationSpec


@dataclass(frozen=True, kw_only=True)
class TaskInput:
    messages: tuple[MessageTurn, ...]
    available_tools: tuple[Mapping[str, Any], ...]  # JSON schemas


@dataclass(frozen=True, kw_only=True)
class TaskMetadata:
    split: str
    version: str
    provenance: str
    world_template_id: str
    difficulty_knob: str


@dataclass(frozen=True, kw_only=True)
class Task:
    id: str
    capability: str
    input: TaskInput
    verification: VerificationSpec
    metadata: TaskMetadata
    initial_state: Mapping[str, Any] | None = field(default=None)
```

- [ ] **Step 2: Verify it imports**

Run: `uv run python -c "from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/agent_eval_lab/tasks/task.py
git commit -m "feat(tasks): add Task, TaskInput, TaskMetadata records"
```

### Task 5: Grading + run records

**Files:**
- Create: `src/agent_eval_lab/tasks/grading.py`

- [ ] **Step 1: Create the grading + run records**

`src/agent_eval_lab/tasks/grading.py`:

```python
"""Grading + run records (design §4.5). Tool-use subset of FailureCategory."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_eval_lab.tasks.turns import Turn

FailureCategory = Literal[
    "malformed_call",
    "schema_violation",
    "wrong_tool",
    "wrong_args",
    "missing_call",
    "extra_call",
    "order_mismatch",
    "step_limit_exceeded",
]


@dataclass(frozen=True, kw_only=True)
class GradeResult:
    grader_id: str
    passed: bool
    score: float
    evidence: Mapping[str, Any] = field(default_factory=dict)
    failure_reason: FailureCategory | None = None


@dataclass(frozen=True, kw_only=True)
class Trajectory:
    turns: tuple[Turn, ...]
    usage: Mapping[str, int]            # {prompt_tokens, completion_tokens, total_tokens}
    cost_usd: float
    latency_ms: int
    run_index: int
    termination_reason: Literal["stop", "max_turns", "max_tool_calls"]


@dataclass(frozen=True, kw_only=True)
class RunResult:
    task_id: str
    condition_id: str
    run_index: int
    trajectory: Trajectory
    grade: GradeResult
```

- [ ] **Step 2: Verify it imports**

Run: `uv run python -c "from agent_eval_lab.tasks.grading import GradeResult, Trajectory, RunResult; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/agent_eval_lab/tasks/grading.py
git commit -m "feat(tasks): add GradeResult, Trajectory, RunResult records"
```

### Task 6: Pure JSONL codec (round-trip)

**Files:**
- Create: `src/agent_eval_lab/tasks/codec.py`
- Test: `tests/tasks/test_codec_roundtrip.py`

- [ ] **Step 1: Write the failing round-trip test**

`tests/tasks/test_codec_roundtrip.py`:

```python
from agent_eval_lab.tasks.codec import from_dict, to_dict
from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.tasks.verification import OutputMatchSpec, ToolCallMatchSpec


def _roundtrip(record):
    return from_dict(type(record), to_dict(record))


def test_tool_call_roundtrip():
    rec = ToolCall(call_id="c1", name="create_ticket", arguments={"title": "x"})
    assert _roundtrip(rec) == rec


def test_message_turn_roundtrip():
    rec = MessageTurn(role="user", content="hi")
    out = to_dict(rec)
    assert out["type"] == "message"
    assert from_dict(MessageTurn, out) == rec


def test_tool_call_turn_roundtrip():
    rec = ToolCallTurn(tool_calls=(ToolCall(call_id="c1", name="t", arguments={}),))
    assert _roundtrip(rec) == rec


def test_tool_result_turn_success_roundtrip():
    rec = ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"ok": 1}))
    out = to_dict(rec)
    assert out["outcome"]["type"] == "success"
    assert from_dict(ToolResultTurn, out) == rec


def test_tool_result_turn_failure_roundtrip():
    rec = ToolResultTurn(call_id="c1", outcome=ToolFailure(error="bad"))
    out = to_dict(rec)
    assert out["outcome"]["type"] == "failure"
    assert from_dict(ToolResultTurn, out) == rec


def test_output_match_spec_roundtrip():
    rec = OutputMatchSpec(expected_output="42")
    assert _roundtrip(rec) == rec


def test_tool_call_match_spec_roundtrip():
    rec = ToolCallMatchSpec(
        expected_tool_calls=(ExpectedToolCall(name="t", arguments={"a": 1}),),
        match="multiset",
    )
    assert _roundtrip(rec) == rec


def test_task_roundtrip_with_tool_call_verification():
    rec = Task(
        id="t1",
        capability="tool_selection",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="hi"),),
            available_tools=({"name": "search_docs"},),
        ),
        verification=ToolCallMatchSpec(
            expected_tool_calls=(ExpectedToolCall(name="search_docs", arguments={"query": "x"}),),
        ),
        metadata=TaskMetadata(
            split="dev",
            version="1",
            provenance="handwritten",
            world_template_id="workspace",
            difficulty_knob="baseline",
        ),
        initial_state={"tickets": {}, "docs": {}},
    )
    assert _roundtrip(rec) == rec


def test_run_result_roundtrip():
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="done"),),
        usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        cost_usd=0.0001,
        latency_ms=42,
        run_index=0,
        termination_reason="stop",
    )
    grade = GradeResult(grader_id="ast_tool_match", passed=True, score=1.0)
    rec = RunResult(task_id="t1", condition_id="c", run_index=0, trajectory=traj, grade=grade)
    assert _roundtrip(rec) == rec
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tasks/test_codec_roundtrip.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.tasks.codec'`

- [ ] **Step 3: Write the codec implementation**

`src/agent_eval_lab/tasks/codec.py`:

```python
"""Pure to_dict/from_dict for every record. Tagged unions dispatch on `type`."""

from typing import Any

from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.tasks.verification import OutputMatchSpec, ToolCallMatchSpec

_TURN_BY_TAG = {"message": MessageTurn, "tool_call": ToolCallTurn, "tool_result": ToolResultTurn}
_OUTCOME_BY_TAG = {"success": ToolSuccess, "failure": ToolFailure}
_VERIFY_BY_TAG = {"output_match": OutputMatchSpec, "tool_call_match": ToolCallMatchSpec}


def _call_to_dict(c: ToolCall | ExpectedToolCall) -> dict[str, Any]:
    out = {"name": c.name, "arguments": dict(c.arguments)}
    if isinstance(c, ToolCall):
        out["call_id"] = c.call_id
    return out


def _turn_to_dict(t: Any) -> dict[str, Any]:
    if isinstance(t, MessageTurn):
        return {"type": "message", "role": t.role, "content": t.content}
    if isinstance(t, ToolCallTurn):
        return {
            "type": "tool_call",
            "content": t.content,
            "tool_calls": [_call_to_dict(c) for c in t.tool_calls],
        }
    outcome = t.outcome
    tag = "success" if isinstance(outcome, ToolSuccess) else "failure"
    body = {"result": outcome.result} if tag == "success" else {"error": outcome.error}
    return {"type": "tool_result", "call_id": t.call_id, "outcome": {"type": tag, **body}}


def _verify_to_dict(v: Any) -> dict[str, Any]:
    if isinstance(v, OutputMatchSpec):
        return {"type": "output_match", "expected_output": v.expected_output, "normalizer": v.normalizer}
    return {
        "type": "tool_call_match",
        "match": v.match,
        "expected_tool_calls": [_call_to_dict(c) for c in v.expected_tool_calls],
    }


def to_dict(record: Any) -> dict[str, Any]:
    """Serialize any locked record to a plain JSON-able dict."""
    if isinstance(record, (ToolCall, ExpectedToolCall)):
        return _call_to_dict(record)
    if isinstance(record, (MessageTurn, ToolCallTurn, ToolResultTurn)):
        return _turn_to_dict(record)
    if isinstance(record, (OutputMatchSpec, ToolCallMatchSpec)):
        return _verify_to_dict(record)
    if isinstance(record, TaskInput):
        return {
            "messages": [_turn_to_dict(m) for m in record.messages],
            "available_tools": [dict(s) for s in record.available_tools],
        }
    if isinstance(record, TaskMetadata):
        return {
            "split": record.split,
            "version": record.version,
            "provenance": record.provenance,
            "world_template_id": record.world_template_id,
            "difficulty_knob": record.difficulty_knob,
        }
    if isinstance(record, Task):
        return {
            "id": record.id,
            "capability": record.capability,
            "input": to_dict(record.input),
            "verification": _verify_to_dict(record.verification),
            "metadata": to_dict(record.metadata),
            "initial_state": dict(record.initial_state) if record.initial_state is not None else None,
        }
    if isinstance(record, GradeResult):
        return {
            "grader_id": record.grader_id,
            "passed": record.passed,
            "score": record.score,
            "evidence": dict(record.evidence),
            "failure_reason": record.failure_reason,
        }
    if isinstance(record, Trajectory):
        return {
            "turns": [_turn_to_dict(t) for t in record.turns],
            "usage": dict(record.usage),
            "cost_usd": record.cost_usd,
            "latency_ms": record.latency_ms,
            "run_index": record.run_index,
            "termination_reason": record.termination_reason,
        }
    if isinstance(record, RunResult):
        return {
            "task_id": record.task_id,
            "condition_id": record.condition_id,
            "run_index": record.run_index,
            "trajectory": to_dict(record.trajectory),
            "grade": to_dict(record.grade),
        }
    raise TypeError(f"cannot serialize {type(record).__name__}")


def _call_from_dict(cls: Any, d: dict[str, Any]) -> Any:
    if cls is ToolCall:
        return ToolCall(call_id=d["call_id"], name=d["name"], arguments=dict(d.get("arguments", {})))
    return ExpectedToolCall(name=d["name"], arguments=dict(d.get("arguments", {})))


def _turn_from_dict(d: dict[str, Any]) -> Any:
    cls = _TURN_BY_TAG[d["type"]]
    if cls is MessageTurn:
        return MessageTurn(role=d["role"], content=d["content"])
    if cls is ToolCallTurn:
        return ToolCallTurn(
            content=d.get("content"),
            tool_calls=tuple(_call_from_dict(ToolCall, c) for c in d["tool_calls"]),
        )
    o = d["outcome"]
    outcome = ToolSuccess(result=o["result"]) if o["type"] == "success" else ToolFailure(error=o["error"])
    return ToolResultTurn(call_id=d["call_id"], outcome=outcome)


def _verify_from_dict(d: dict[str, Any]) -> Any:
    cls = _VERIFY_BY_TAG[d["type"]]
    if cls is OutputMatchSpec:
        return OutputMatchSpec(expected_output=d["expected_output"], normalizer=d.get("normalizer"))
    return ToolCallMatchSpec(
        match=d.get("match", "exact_sequence"),
        expected_tool_calls=tuple(_call_from_dict(ExpectedToolCall, c) for c in d["expected_tool_calls"]),
    )


def from_dict(cls: Any, d: dict[str, Any]) -> Any:
    """Deserialize a plain dict back into the given record class."""
    if cls in (ToolCall, ExpectedToolCall):
        return _call_from_dict(cls, d)
    if cls in (MessageTurn, ToolCallTurn, ToolResultTurn):
        return _turn_from_dict(d)
    if cls in (OutputMatchSpec, ToolCallMatchSpec):
        return _verify_from_dict(d)
    if cls is TaskInput:
        return TaskInput(
            messages=tuple(_turn_from_dict(m) for m in d["messages"]),
            available_tools=tuple(dict(s) for s in d["available_tools"]),
        )
    if cls is TaskMetadata:
        return TaskMetadata(**d)
    if cls is Task:
        return Task(
            id=d["id"],
            capability=d["capability"],
            input=from_dict(TaskInput, d["input"]),
            verification=_verify_from_dict(d["verification"]),
            metadata=from_dict(TaskMetadata, d["metadata"]),
            initial_state=dict(d["initial_state"]) if d.get("initial_state") is not None else None,
        )
    if cls is GradeResult:
        return GradeResult(
            grader_id=d["grader_id"],
            passed=d["passed"],
            score=d["score"],
            evidence=dict(d.get("evidence", {})),
            failure_reason=d.get("failure_reason"),
        )
    if cls is Trajectory:
        return Trajectory(
            turns=tuple(_turn_from_dict(t) for t in d["turns"]),
            usage=dict(d["usage"]),
            cost_usd=d["cost_usd"],
            latency_ms=d["latency_ms"],
            run_index=d["run_index"],
            termination_reason=d["termination_reason"],
        )
    if cls is RunResult:
        return RunResult(
            task_id=d["task_id"],
            condition_id=d["condition_id"],
            run_index=d["run_index"],
            trajectory=from_dict(Trajectory, d["trajectory"]),
            grade=from_dict(GradeResult, d["grade"]),
        )
    raise TypeError(f"cannot deserialize {getattr(cls, '__name__', cls)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tasks/test_codec_roundtrip.py -q`
Expected: PASS — 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/tasks/codec.py tests/tasks/test_codec_roundtrip.py
git commit -m "feat(tasks): add pure JSONL codec with round-trip tests"
```

### Task 7: Dataset loader (edge)

**Files:**
- Create: `src/agent_eval_lab/tasks/loader.py`
- Test: `tests/tasks/test_loader.py`

- [ ] **Step 1: Write the failing test**

`tests/tasks/test_loader.py`:

```python
from agent_eval_lab.tasks.codec import to_dict
from agent_eval_lab.tasks.loader import load_tasks, write_run_results
from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall
from agent_eval_lab.tasks.turns import MessageTurn
from agent_eval_lab.tasks.verification import ToolCallMatchSpec


def _task(task_id):
    return Task(
        id=task_id,
        capability="tool_selection",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="hi"),),
            available_tools=({"name": "search_docs"},),
        ),
        verification=ToolCallMatchSpec(
            expected_tool_calls=(ExpectedToolCall(name="search_docs"),),
        ),
        metadata=TaskMetadata(
            split="dev", version="1", provenance="handwritten",
            world_template_id="workspace", difficulty_knob="baseline",
        ),
    )


def test_load_tasks_reads_jsonl(tmp_path):
    path = tmp_path / "tasks.jsonl"
    lines = [to_dict(_task("a")), to_dict(_task("b"))]
    import json
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    tasks = load_tasks(path)
    assert [t.id for t in tasks] == ["a", "b"]


def test_write_run_results_roundtrips(tmp_path):
    path = tmp_path / "runs.jsonl"
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage={"total_tokens": 1}, cost_usd=0.0, latency_ms=1,
        run_index=0, termination_reason="stop",
    )
    rr = RunResult(
        task_id="a", condition_id="c", run_index=0, trajectory=traj,
        grade=GradeResult(grader_id="g", passed=True, score=1.0),
    )
    write_run_results(path, [rr])
    from agent_eval_lab.tasks.loader import load_run_results
    loaded = load_run_results(path)
    assert loaded == [rr]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tasks/test_loader.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.tasks.loader'`

- [ ] **Step 3: Write the loader (edge)**

`src/agent_eval_lab/tasks/loader.py`:

```python
"""JSONL I/O edge for Task and RunResult. The only file access in tasks/."""

import json
from collections.abc import Iterable
from pathlib import Path

from agent_eval_lab.tasks.codec import from_dict, to_dict
from agent_eval_lab.tasks.grading import RunResult
from agent_eval_lab.tasks.task import Task


def _read_lines(path: Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def load_tasks(path: Path) -> list[Task]:
    return [from_dict(Task, d) for d in _read_lines(path)]


def load_run_results(path: Path) -> list[RunResult]:
    return [from_dict(RunResult, d) for d in _read_lines(path)]


def write_run_results(path: Path, results: Iterable[RunResult]) -> None:
    lines = [json.dumps(to_dict(r)) for r in results]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tasks/test_loader.py -q`
Expected: PASS — 2 passed.

- [ ] **Step 5: Run the full suite + lint**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: pytest all pass (~14); ruff check clean. `ruff format --check` may report files would be reformatted — if so run `uv run ruff format .` then re-run the checks until clean, and amend the commit.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/tasks/loader.py tests/tasks/test_loader.py
git commit -m "feat(tasks): add JSONL dataset loader edge"
```

---

## Phase 2 — workspace-world: schemas + JSON-schema-validated pure apply() (Tasks 8–9)

**Verification point:** `uv run pytest tests/tools -q` passes; schema-invalid calls return `ToolFailure` and never mutate state; valid calls mutate a copy. Ruff clean.

### Task 8: Vendored minimal JSON-Schema validator

**Files:**
- Create: `src/agent_eval_lab/tools/__init__.py`
- Create: `src/agent_eval_lab/tools/jsonschema_mini.py`
- Test: `tests/tools/test_jsonschema_mini.py`

- [ ] **Step 1: Create the package marker**

`src/agent_eval_lab/tools/__init__.py`:

```python
"""Synthetic workspace-world: JSON schemas + pure apply over explicit state."""
```

- [ ] **Step 2: Write the failing validator test**

`tests/tools/test_jsonschema_mini.py`:

```python
from agent_eval_lab.tools.jsonschema_mini import validate

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "count": {"type": "integer"},
    },
    "required": ["title", "priority"],
    "additionalProperties": False,
}


def test_valid_object_returns_no_errors():
    assert validate({"title": "x", "priority": "low"}, SCHEMA) == []


def test_missing_required_field_reported():
    errs = validate({"title": "x"}, SCHEMA)
    assert any("priority" in e for e in errs)


def test_wrong_type_reported_no_coercion():
    # "1" where integer required must FAIL — never coerced.
    errs = validate({"title": "x", "priority": "low", "count": "1"}, SCHEMA)
    assert any("count" in e for e in errs)


def test_bool_is_not_integer():
    errs = validate({"title": "x", "priority": "low", "count": True}, SCHEMA)
    assert any("count" in e for e in errs)


def test_enum_violation_reported():
    errs = validate({"title": "x", "priority": "urgent"}, SCHEMA)
    assert any("priority" in e for e in errs)


def test_additional_property_reported():
    errs = validate({"title": "x", "priority": "low", "extra": 1}, SCHEMA)
    assert any("extra" in e for e in errs)


def test_non_object_top_level_reported():
    errs = validate(["not", "an", "object"], SCHEMA)
    assert errs != []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_jsonschema_mini.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write the validator (pure)**

`src/agent_eval_lab/tools/jsonschema_mini.py`:

```python
"""Minimal, dependency-free JSON-Schema validator (subset).

Supports: type (object/string/integer/number/boolean/array), properties,
required, enum, additionalProperties:false. Returns a list of human-readable
error strings; [] means valid. NEVER coerces types ("1" != integer).
Applied identically at the tool-world boundary and the AST grader.
"""

from typing import Any

_PY_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list, tuple),
    "object": (dict,),
}


def _type_ok(value: Any, expected: str) -> bool:
    # bool is a subclass of int in Python; exclude it from numeric types.
    if expected in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _PY_TYPES[expected])


def validate(instance: Any, schema: dict[str, Any], path: str = "") -> list[str]:
    """Validate instance against schema. Returns error messages; [] if valid."""
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None and not _type_ok(instance, expected):
        errors.append(f"{path or '<root>'}: expected type {expected}")
        return errors
    if expected == "object":
        errors.extend(_validate_object(instance, schema, path))
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path or '<root>'}: {instance!r} not in enum {schema['enum']}")
    return errors


def _validate_object(instance: dict, schema: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    props: dict[str, Any] = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in instance:
            errors.append(f"{path}{name}: required property missing")
    if schema.get("additionalProperties") is False:
        for key in instance:
            if key not in props:
                errors.append(f"{path}{key}: additional property not allowed")
    for key, value in instance.items():
        if key in props:
            errors.extend(validate(value, props[key], f"{path}{key}."))
    return errors
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_jsonschema_mini.py -q`
Expected: PASS — 7 passed.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/tools/__init__.py src/agent_eval_lab/tools/jsonschema_mini.py tests/tools/test_jsonschema_mini.py
git commit -m "feat(tools): add vendored minimal JSON-Schema validator"
```

### Task 9: workspace-world schemas + pure apply()

**Files:**
- Create: `src/agent_eval_lab/tools/workspace_world.py`
- Test: `tests/tools/test_workspace_world.py`

- [ ] **Step 1: Write the failing world test**

`tests/tools/test_workspace_world.py`:

```python
from agent_eval_lab.tasks.turns import ToolFailure, ToolSuccess
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS, apply, initial_state


def test_tool_schemas_cover_the_three_tools():
    assert set(TOOL_SCHEMAS) == {"search_docs", "create_ticket", "update_ticket"}


def test_create_ticket_valid_returns_success_and_new_state():
    state = initial_state()
    new_state, outcome = apply("create_ticket", {"title": "Bug", "priority": "high"}, state)
    assert isinstance(outcome, ToolSuccess)
    ticket_id = outcome.result["ticket_id"]
    assert new_state["tickets"][ticket_id] == {"title": "Bug", "priority": "high", "status": "open"}
    # original state is untouched (pure, copy-on-write)
    assert state["tickets"] == {}


def test_create_ticket_schema_invalid_returns_failure_no_mutation():
    state = initial_state()
    new_state, outcome = apply("create_ticket", {"title": "Bug", "priority": "urgent"}, state)
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
    new_state, outcome = apply("update_ticket", {"ticket_id": tid, "status": "closed"}, state)
    assert isinstance(outcome, ToolSuccess)
    assert new_state["tickets"][tid]["status"] == "closed"


def test_update_ticket_unknown_id_returns_failure():
    state = initial_state()
    new_state, outcome = apply("update_ticket", {"ticket_id": "T-404", "status": "closed"}, state)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_workspace_world.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the world (pure)**

`src/agent_eval_lab/tools/workspace_world.py`:

```python
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


def _search_docs(args: Mapping[str, Any], state: Mapping[str, Any]) -> tuple[dict, ToolOutcome]:
    query = args["query"].lower()
    hits = [k for k, v in state["docs"].items() if query in k or query in v.lower()]
    return dict(state), ToolSuccess(result={"matches": hits})


def _create_ticket(args: Mapping[str, Any], state: Mapping[str, Any]) -> tuple[dict, ToolOutcome]:
    tickets = dict(state["tickets"])
    ticket_id = _next_ticket_id(tickets)
    tickets[ticket_id] = {"title": args["title"], "priority": args["priority"], "status": "open"}
    return {**state, "tickets": tickets}, ToolSuccess(result={"ticket_id": ticket_id})


def _update_ticket(args: Mapping[str, Any], state: Mapping[str, Any]) -> tuple[dict, ToolOutcome]:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_workspace_world.py -q`
Expected: PASS — 9 passed.

- [ ] **Step 5: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all pass (~30); ruff clean (reformat + amend if needed).

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/tools/workspace_world.py tests/tools/test_workspace_world.py
git commit -m "feat(tools): add workspace-world schemas + pure apply()"
```

---

## Phase 3 — schema-first AST grader + failure taxonomy + ~20-task dataset (Tasks 10–15)

**Verification point:** every `FailureCategory` in A3 is emitted by a unit test; the migrated `grade_exact_match` returns the new `GradeResult`; the ~20-task dataset round-trips. Ruff clean.

### Task 10: Migrate GradeResult + exact_match → OutputMatchSpec scorer

**Files:**
- Modify: `src/agent_eval_lab/graders/exact_match.py`
- Modify: `tests/graders/test_exact_match.py`
- Modify: `src/agent_eval_lab/graders/__init__.py`

- [ ] **Step 1: Rewrite the failing test to the new shape**

Replace the entire contents of `tests/graders/test_exact_match.py`:

```python
from agent_eval_lab.graders.exact_match import grade_exact_match


def test_exact_match_passes_identical_values():
    result = grade_exact_match(expected="get_weather", actual="get_weather")
    assert result.grader_id == "output_match"
    assert result.passed is True
    assert result.score == 1.0
    assert result.failure_reason is None
    assert result.evidence["message"] == "Values match exactly."


def test_exact_match_fails_different_values():
    result = grade_exact_match(expected="get_weather", actual="search_docs")
    assert result.passed is False
    assert result.score == 0.0
    assert result.failure_reason == "wrong_tool"
    assert result.evidence["message"] == "Expected 'get_weather', received 'search_docs'."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_exact_match.py -q`
Expected: FAIL — `GradeResult` import or attribute errors (old shape).

- [ ] **Step 3: Rewrite exact_match.py to use the canonical GradeResult**

Replace the entire contents of `src/agent_eval_lab/graders/exact_match.py`:

```python
"""OutputMatchSpec scorer (formerly the standalone exact-match grader)."""

from agent_eval_lab.tasks.grading import GradeResult

_GRADER_ID = "output_match"


def grade_exact_match(*, expected: str, actual: str) -> GradeResult:
    """Grade values that match exactly. Survives as the OutputMatchSpec scorer."""
    if expected == actual:
        return GradeResult(
            grader_id=_GRADER_ID,
            passed=True,
            score=1.0,
            evidence={"message": "Values match exactly."},
        )
    return GradeResult(
        grader_id=_GRADER_ID,
        passed=False,
        score=0.0,
        evidence={"message": f"Expected {expected!r}, received {actual!r}."},
        failure_reason="wrong_tool",
    )
```

- [ ] **Step 4: Update the graders package re-exports**

Replace the entire contents of `src/agent_eval_lab/graders/__init__.py`:

```python
"""Pure grading: output match + schema-first AST tool-call grading."""

from agent_eval_lab.graders.exact_match import grade_exact_match
from agent_eval_lab.tasks.grading import GradeResult

__all__ = ["GradeResult", "grade_exact_match"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_exact_match.py -q`
Expected: PASS — 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/graders/exact_match.py src/agent_eval_lab/graders/__init__.py tests/graders/test_exact_match.py
git commit -m "refactor(graders): migrate GradeResult to canonical shape; exact_match -> OutputMatchSpec scorer"
```

### Task 11: Value-preserving canonicalization

**Files:**
- Create: `src/agent_eval_lab/graders/canonicalize.py`
- Test: `tests/graders/test_canonicalize.py`

- [ ] **Step 1: Write the failing test**

`tests/graders/test_canonicalize.py`:

```python
from agent_eval_lab.graders.canonicalize import canonicalize


def test_sorts_object_keys():
    assert canonicalize({"b": 1, "a": 2}) == canonicalize({"a": 2, "b": 1})


def test_is_idempotent():
    value = {"b": [3, {"y": 1, "x": 2}], "a": "s"}
    once = canonicalize(value)
    assert canonicalize(once) == once


def test_preserves_values_no_coercion():
    # canonicalization must NOT turn "1" into 1.
    assert canonicalize({"n": "1"}) != canonicalize({"n": 1})


def test_distinguishes_bool_from_int():
    assert canonicalize(True) != canonicalize(1)


def test_lists_keep_order():
    assert canonicalize([1, 2, 3]) != canonicalize([3, 2, 1])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_canonicalize.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write canonicalize (pure)**

`src/agent_eval_lab/graders/canonicalize.py`:

```python
"""Value-preserving, idempotent canonicalization for structural comparison.

Produces a hashable, order-normalized, type-tagged form so that True != 1 and
"1" != 1. Strictly value-preserving: never coerces or drops information.

Idempotence is a true fixed point: the output is a tagged tuple
``(tag, payload)`` whose first element is a known tag; re-applying canonicalize
to an already-canonical value returns it unchanged. This is required by spec A4
(``canonicalize(canonicalize(x)) == canonicalize(x)``) and lets canonical forms
be used directly as ``Counter`` keys in the multiset grader.

Domain note: inputs come from JSON (deserialized tool arguments), so they are
only dict / list / str / int / float / bool / None — never tuples. The only
tuples canonicalize ever sees are its own outputs, so the ``_is_canonical``
fixed-point guard is safe.
"""

from typing import Any

_TAGS = frozenset({"bool", "int", "float", "str", "NoneType", "dict", "list"})


def _is_canonical(value: Any) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and value[0] in _TAGS
    )


def canonicalize(value: Any) -> Any:
    """Return a hashable, order-normalized, type-tagged form of value (idempotent)."""
    if _is_canonical(value):
        return value
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float, str)) or value is None:
        return (type(value).__name__, value)
    if isinstance(value, dict):
        return ("dict", tuple(sorted((k, canonicalize(v)) for k, v in value.items())))
    if isinstance(value, (list, tuple)):
        return ("list", tuple(canonicalize(v) for v in value))
    raise TypeError(f"cannot canonicalize {type(value).__name__}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_canonicalize.py -q`
Expected: PASS — 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/canonicalize.py tests/graders/test_canonicalize.py
git commit -m "feat(graders): add value-preserving idempotent canonicalization"
```

### Task 12: Schema-first AST tool-call grader

**Files:**
- Create: `src/agent_eval_lab/graders/ast_tool_match.py`
- Test: `tests/graders/test_ast_tool_match.py`

- [ ] **Step 1: Write the failing taxonomy test**

`tests/graders/test_ast_tool_match.py`:

```python
from agent_eval_lab.graders.ast_tool_match import grade_tool_calls
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS


def _observed(name, args, call_id="c1"):
    return (ToolCall(call_id=call_id, name=name, arguments=args),)


def _spec(*expected, match="exact_sequence"):
    return ToolCallMatchSpec(expected_tool_calls=tuple(expected), match=match)


def test_exact_match_passes():
    spec = _spec(ExpectedToolCall(name="create_ticket", arguments={"title": "x", "priority": "low"}))
    obs = _observed("create_ticket", {"title": "x", "priority": "low"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.passed is True
    assert result.failure_reason is None


def test_schema_violation_type_coercion_never_passes():
    spec = _spec(ExpectedToolCall(name="create_ticket", arguments={"title": "x", "priority": "low"}))
    obs = _observed("create_ticket", {"title": 1, "priority": "low"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.passed is False
    assert result.failure_reason == "schema_violation"


def test_enum_violation_is_schema_violation():
    spec = _spec(ExpectedToolCall(name="create_ticket", arguments={"title": "x", "priority": "low"}))
    obs = _observed("create_ticket", {"title": "x", "priority": "urgent"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "schema_violation"


def test_unknown_tool_name_is_malformed_call():
    spec = _spec(ExpectedToolCall(name="create_ticket", arguments={"title": "x", "priority": "low"}))
    obs = _observed("nonexistent_tool", {})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "malformed_call"


def test_wrong_tool():
    spec = _spec(ExpectedToolCall(name="search_docs", arguments={"query": "x"}))
    obs = _observed("create_ticket", {"title": "x", "priority": "low"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "wrong_tool"


def test_wrong_args():
    spec = _spec(ExpectedToolCall(name="search_docs", arguments={"query": "install"}))
    obs = _observed("search_docs", {"query": "deploy"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "wrong_args"


def test_missing_call():
    spec = _spec(
        ExpectedToolCall(name="create_ticket", arguments={"title": "x", "priority": "low"}),
        ExpectedToolCall(name="update_ticket", arguments={"ticket_id": "T-1", "status": "closed"}),
    )
    obs = _observed("create_ticket", {"title": "x", "priority": "low"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "missing_call"


def test_extra_call():
    spec = _spec(ExpectedToolCall(name="search_docs", arguments={"query": "x"}))
    obs = (
        ToolCall(call_id="c1", name="search_docs", arguments={"query": "x"}),
        ToolCall(call_id="c2", name="search_docs", arguments={"query": "y"}),
    )
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "extra_call"


def test_order_mismatch_in_exact_sequence():
    spec = _spec(
        ExpectedToolCall(name="create_ticket", arguments={"title": "x", "priority": "low"}),
        ExpectedToolCall(name="update_ticket", arguments={"ticket_id": "T-1", "status": "closed"}),
    )
    obs = (
        ToolCall(call_id="c1", name="update_ticket", arguments={"ticket_id": "T-1", "status": "closed"}),
        ToolCall(call_id="c2", name="create_ticket", arguments={"title": "x", "priority": "low"}),
    )
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.failure_reason == "order_mismatch"


def test_multiset_ignores_order_but_keeps_count():
    spec = _spec(
        ExpectedToolCall(name="create_ticket", arguments={"title": "x", "priority": "low"}),
        ExpectedToolCall(name="update_ticket", arguments={"ticket_id": "T-1", "status": "closed"}),
        match="multiset",
    )
    obs = (
        ToolCall(call_id="c1", name="update_ticket", arguments={"ticket_id": "T-1", "status": "closed"}),
        ToolCall(call_id="c2", name="create_ticket", arguments={"title": "x", "priority": "low"}),
    )
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.passed is True


def test_multiset_duplicate_count_mismatch_fails():
    spec = _spec(
        ExpectedToolCall(name="search_docs", arguments={"query": "x"}),
        ExpectedToolCall(name="search_docs", arguments={"query": "x"}),
        match="multiset",
    )
    obs = _observed("search_docs", {"query": "x"})
    result = grade_tool_calls(spec, obs, TOOL_SCHEMAS)
    assert result.passed is False
    assert result.failure_reason == "missing_call"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_ast_tool_match.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the AST grader (pure)**

`src/agent_eval_lab/graders/ast_tool_match.py`:

```python
"""Schema-first AST tool-call grader (design §6).

Pipeline per observed call:
  1. parse/name-known   -> else malformed_call
  2. validate vs schema -> else schema_violation (NEVER coerced)
Then structural compare (canonicalized) against ExpectedToolCall sequence:
  wrong_tool | wrong_args | missing_call | extra_call | order_mismatch.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from agent_eval_lab.graders.canonicalize import canonicalize
from agent_eval_lab.tasks.grading import FailureCategory, GradeResult
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.jsonschema_mini import validate

_GRADER_ID = "ast_tool_match"


def _fail(reason: FailureCategory, message: str, **evidence: Any) -> GradeResult:
    return GradeResult(
        grader_id=_GRADER_ID,
        passed=False,
        score=0.0,
        evidence={"message": message, **evidence},
        failure_reason=reason,
    )


def _passed() -> GradeResult:
    return GradeResult(grader_id=_GRADER_ID, passed=True, score=1.0, evidence={"message": "match"})


def _precheck(observed: Sequence[ToolCall], schemas: Mapping[str, Any]) -> GradeResult | None:
    """Stage 1+2: unknown tool -> malformed_call; bad args -> schema_violation."""
    for call in observed:
        if call.name not in schemas:
            return _fail("malformed_call", f"unknown tool {call.name!r}", tool=call.name)
        errors = validate(dict(call.arguments), schemas[call.name])
        if errors:
            return _fail("schema_violation", "; ".join(errors), tool=call.name)
    return None


def _key(call: ToolCall | ExpectedToolCall) -> Any:
    return (call.name, canonicalize(dict(call.arguments)))


def _grade_exact_sequence(
    expected: Sequence[ExpectedToolCall], observed: Sequence[ToolCall]
) -> GradeResult:
    if len(observed) < len(expected):
        return _fail("missing_call", f"expected {len(expected)} calls, saw {len(observed)}")
    if len(observed) > len(expected):
        return _fail("extra_call", f"expected {len(expected)} calls, saw {len(observed)}")
    for exp, obs in zip(expected, observed, strict=True):
        if exp.name != obs.name:
            if Counter(o.name for o in observed) == Counter(e.name for e in expected):
                return _fail("order_mismatch", "right tools, wrong order")
            return _fail("wrong_tool", f"expected {exp.name!r}, saw {obs.name!r}")
        if _key(exp) != _key(obs):
            return _fail("wrong_args", f"argument mismatch for {obs.name!r}")
    return _passed()


def _grade_multiset(
    expected: Sequence[ExpectedToolCall], observed: Sequence[ToolCall]
) -> GradeResult:
    exp_counts = Counter(_key(e) for e in expected)
    obs_counts = Counter(_key(o) for o in observed)
    if obs_counts == exp_counts:
        return _passed()
    missing = exp_counts - obs_counts
    extra = obs_counts - exp_counts
    if extra and not missing:
        return _fail("extra_call", "unexpected call(s) present")
    expected_names = {e.name for e in expected}
    if any(name not in expected_names for (name, _args) in extra):
        return _fail("wrong_tool", "unexpected tool in multiset")
    return _fail("missing_call", "expected call(s) absent or wrong args")


def grade_tool_calls(
    spec: ToolCallMatchSpec,
    observed: Sequence[ToolCall],
    schemas: Mapping[str, Any],
) -> GradeResult:
    """Grade observed tool calls against the spec via the schema-first pipeline."""
    precheck = _precheck(observed, schemas)
    if precheck is not None:
        return precheck
    if spec.match == "multiset":
        return _grade_multiset(spec.expected_tool_calls, observed)
    return _grade_exact_sequence(spec.expected_tool_calls, observed)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_ast_tool_match.py -q`
Expected: PASS — 12 passed.

> Note on `_grade_multiset` `wrong_tool` branch: the generator expression `(k for k in extra)` iterates `extra`'s keys (each a `(name, canon_args)` tuple); `name not in {expected names}` detects an unexpected tool. The duplicate-count test exercises the `missing_call` branch.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/ast_tool_match.py tests/graders/test_ast_tool_match.py
git commit -m "feat(graders): add schema-first AST tool-call grader with failure taxonomy"
```

### Task 13: Verification dispatch (grade_task)

**Files:**
- Create: `src/agent_eval_lab/graders/grade.py`
- Test: `tests/graders/test_grade.py`

- [ ] **Step 1: Write the failing dispatch test**

`tests/graders/test_grade.py`:

```python
import pytest

from agent_eval_lab.graders.grade import grade_trajectory
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn
from agent_eval_lab.tasks.verification import OutputMatchSpec, ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS


def test_tool_call_match_dispatch_passes():
    spec = ToolCallMatchSpec(
        expected_tool_calls=(ExpectedToolCall(name="search_docs", arguments={"query": "x"}),),
    )
    turns = (ToolCallTurn(tool_calls=(ToolCall(call_id="c1", name="search_docs", arguments={"query": "x"}),)),)
    result = grade_trajectory(spec, turns, TOOL_SCHEMAS)
    assert result.passed is True


def test_output_match_dispatch_uses_last_assistant_message():
    spec = OutputMatchSpec(expected_output="42")
    turns = (MessageTurn(role="assistant", content="42"),)
    result = grade_trajectory(spec, turns, TOOL_SCHEMAS)
    assert result.passed is True
    assert result.grader_id == "output_match"


def test_unsupported_spec_type_raises():
    class FakeSpec:
        type = "final_state"

    with pytest.raises(Exception) as exc:
        grade_trajectory(FakeSpec(), (), TOOL_SCHEMAS)
    assert "not implemented" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_grade.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the dispatch (pure)**

`src/agent_eval_lab/graders/grade.py`:

```python
"""Pure verification dispatch: VerificationSpec + trajectory turns -> GradeResult."""

from collections.abc import Mapping, Sequence
from typing import Any

from agent_eval_lab.graders.ast_tool_match import grade_tool_calls
from agent_eval_lab.graders.exact_match import grade_exact_match
from agent_eval_lab.tasks.grading import GradeResult
from agent_eval_lab.tasks.tool_calls import ToolCall
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn
from agent_eval_lab.tasks.verification import (
    OutputMatchSpec,
    ToolCallMatchSpec,
    ensure_supported,
)


def _observed_calls(turns: Sequence[Any]) -> tuple[ToolCall, ...]:
    calls: list[ToolCall] = []
    for turn in turns:
        if isinstance(turn, ToolCallTurn):
            calls.extend(turn.tool_calls)
    return tuple(calls)


def _last_assistant_text(turns: Sequence[Any]) -> str:
    texts = [t.content for t in turns if isinstance(t, MessageTurn) and t.role == "assistant"]
    return texts[-1] if texts else ""


def grade_trajectory(
    spec: Any, turns: Sequence[Any], schemas: Mapping[str, Any]
) -> GradeResult:
    """Dispatch on spec.type; reject unimplemented variants with a typed error."""
    ensure_supported(spec.type)
    if isinstance(spec, ToolCallMatchSpec):
        return grade_tool_calls(spec, _observed_calls(turns), schemas)
    if isinstance(spec, OutputMatchSpec):
        return grade_exact_match(expected=spec.expected_output, actual=_last_assistant_text(turns))
    raise AssertionError(f"unreachable spec dispatch for {spec.type!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_grade.py -q`
Expected: PASS — 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/graders/grade.py tests/graders/test_grade.py
git commit -m "feat(graders): add pure verification dispatch (grade_trajectory)"
```

### Task 14: The ~20-task dataset (replace tool_selection.jsonl)

**Files:**
- Create: `examples/datasets/tool_use.jsonl`
- Delete: `examples/datasets/tool_selection.jsonl`
- Test: `tests/tasks/test_dataset_loads.py`

**Dataset format:** one full `Task` JSONL record per line (the codec dict shape from Task 6). Every task: `capability` ∈ {`tool_selection`, `argument_extraction`}; `metadata.world_template_id = "workspace"`; `metadata.difficulty_knob` ∈ {`baseline`, `distractor`, `enum_arg`, `multi_step`}; `verification` is always a `tool_call_match` spec.

**Generation recipe (the impl agent follows this to produce all ~20 lines):**

- **Tool-selection tasks (8):** user asks for one action; `available_tools` lists all three schemas (so two are distractors). Half target `search_docs`, the rest split between `create_ticket` and `update_ticket`. `match="exact_sequence"`, single expected call. `difficulty_knob`: `baseline` when the wording is direct, `distractor` when the phrasing tempts a wrong tool.
- **Argument-extraction tasks (8):** the right tool is named/obvious; the challenge is pulling exact args. Cover each `priority` enum value, each `status` enum value, and at least one task whose correct answer requires the precise query string. `difficulty_knob="enum_arg"`.
- **Multi-step tasks (4):** two expected calls (create then update). Two use `match="exact_sequence"`, two use `match="multiset"`. `difficulty_knob="multi_step"`. Include `initial_state` where the update targets a pre-seeded ticket (e.g. `{"tickets": {"T-1": {"title": "Old", "priority": "low", "status": "open"}}, "docs": {}}`).

Use ids `tool-use-001` … `tool-use-020`. Split: first 14 `"dev"`, last 6 `"held_out"`. `provenance="handwritten"`, `version="1"`.

- [ ] **Step 1: Write the failing dataset-loads test**

`tests/tasks/test_dataset_loads.py`:

```python
from pathlib import Path

from agent_eval_lab.tasks.codec import to_dict
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.verification import ToolCallMatchSpec

DATASET = Path("examples/datasets/tool_use.jsonl")


def test_dataset_has_about_twenty_tasks():
    tasks = load_tasks(DATASET)
    assert 18 <= len(tasks) <= 22


def test_every_task_roundtrips_and_uses_tool_call_match():
    tasks = load_tasks(DATASET)
    for task in tasks:
        assert isinstance(task.verification, ToolCallMatchSpec)
        # round-trip integrity
        from agent_eval_lab.tasks.codec import from_dict
        from agent_eval_lab.tasks.task import Task
        assert from_dict(Task, to_dict(task)) == task


def test_capabilities_and_ids_are_distinct():
    tasks = load_tasks(DATASET)
    ids = [t.id for t in tasks]
    assert len(ids) == len(set(ids))
    assert {t.capability for t in tasks} <= {"tool_selection", "argument_extraction"}


def test_both_match_modes_present():
    tasks = load_tasks(DATASET)
    modes = {t.verification.match for t in tasks}
    assert "exact_sequence" in modes
    assert "multiset" in modes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tasks/test_dataset_loads.py -q`
Expected: FAIL — file `examples/datasets/tool_use.jsonl` does not exist.

- [ ] **Step 3: Author the dataset**

Create `examples/datasets/tool_use.jsonl` with ~20 lines following the recipe above. Two **exact, verbatim reference lines** (the impl agent writes the rest in this style — one JSON object per line, no pretty-printing):

Tool-selection (line 1):

```json
{"id":"tool-use-001","capability":"tool_selection","input":{"messages":[{"type":"message","role":"user","content":"Find the install instructions in our docs."}],"available_tools":[{"name":"search_docs","schema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"],"additionalProperties":false}},{"name":"create_ticket","schema":{"type":"object","properties":{"title":{"type":"string"},"priority":{"type":"string","enum":["low","medium","high"]}},"required":["title","priority"],"additionalProperties":false}},{"name":"update_ticket","schema":{"type":"object","properties":{"ticket_id":{"type":"string"},"status":{"type":"string","enum":["open","closed"]}},"required":["ticket_id","status"],"additionalProperties":false}}]},"verification":{"type":"tool_call_match","match":"exact_sequence","expected_tool_calls":[{"name":"search_docs","arguments":{"query":"install"}}]},"metadata":{"split":"dev","version":"1","provenance":"handwritten","world_template_id":"workspace","difficulty_knob":"baseline"},"initial_state":null}
```

Multi-step / multiset (line 17, held_out, with initial_state):

```json
{"id":"tool-use-017","capability":"argument_extraction","input":{"messages":[{"type":"message","role":"user","content":"Open a high-priority ticket titled 'Outage' and then close ticket T-1."}],"available_tools":[{"name":"create_ticket","schema":{"type":"object","properties":{"title":{"type":"string"},"priority":{"type":"string","enum":["low","medium","high"]}},"required":["title","priority"],"additionalProperties":false}},{"name":"update_ticket","schema":{"type":"object","properties":{"ticket_id":{"type":"string"},"status":{"type":"string","enum":["open","closed"]}},"required":["ticket_id","status"],"additionalProperties":false}}]},"verification":{"type":"tool_call_match","match":"multiset","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"Outage","priority":"high"}},{"name":"update_ticket","arguments":{"ticket_id":"T-1","status":"closed"}}]},"metadata":{"split":"held_out","version":"1","provenance":"handwritten","world_template_id":"workspace","difficulty_knob":"multi_step"},"initial_state":{"tickets":{"T-1":{"title":"Old","priority":"low","status":"open"}},"docs":{}}}
```

Note: `available_tools` entries are `{"name", "schema"}` objects (the model is shown the JSON schema). The grader and world key tools by name; the embedded `schema` mirrors `TOOL_SCHEMAS`. Ensure at least one `exact_sequence` multi-step task (e.g. `tool-use-016`) and at least one `multiset` task (line 17 above) so `test_both_match_modes_present` passes.

- [ ] **Step 4: Delete the obsolete dataset**

```bash
git rm examples/datasets/tool_selection.jsonl
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/tasks/test_dataset_loads.py -q`
Expected: PASS — 4 passed.

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all pass; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add examples/datasets/tool_use.jsonl tests/tasks/test_dataset_loads.py
git commit -m "feat(datasets): add ~20 full Task tool-use dataset; drop name-only seed"
```

---

## Phase 4 — provider client + adapter (fake transport) (Tasks 15–16)

**Verification point:** the client builds OpenAI-compatible requests from `ProviderConfig`, parses tool-call responses into canonical `ToolCall`/`Turn`, applies the optional adapter, reads the API key from the env var *named* by `api_key_env`, and is exercised only through a fake transport. No network, no real key required.

### Task 15: ProviderConfig + pure request builder / response parser + adapter

**Files:**
- Create: `src/agent_eval_lab/runners/__init__.py`
- Create: `src/agent_eval_lab/runners/provider.py`
- Test: `tests/runners/test_provider.py`

- [ ] **Step 1: Create the package marker**

`src/agent_eval_lab/runners/__init__.py`:

```python
"""Imperative shell: provider client, model<->tool loop, multi-run runner."""
```

- [ ] **Step 2: Write the failing provider test**

`tests/runners/test_provider.py`:

```python
import json
from pathlib import Path

from agent_eval_lab.runners.provider import (
    ProviderClient,
    ProviderConfig,
    build_request,
    parse_response,
)
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn

CFG = ProviderConfig(
    id="fake",
    base_url="https://example.invalid/v1",
    api_key_env="FAKE_API_KEY",
    model_id="fake-model",
)


def test_build_request_uses_model_id_and_tools():
    req = build_request(CFG, messages=[{"role": "user", "content": "hi"}], tools=[{"name": "t"}])
    assert req["model"] == "fake-model"
    assert req["messages"] == [{"role": "user", "content": "hi"}]
    assert req["tools"] == [{"name": "t"}]


def test_parse_response_message():
    payload = {"choices": [{"message": {"role": "assistant", "content": "hello"}}],
               "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}}
    turn, usage = parse_response(CFG, payload)
    assert isinstance(turn, MessageTurn)
    assert turn.content == "hello"
    assert usage["total_tokens"] == 4


def test_parse_response_tool_calls_canonical():
    payload = {"choices": [{"message": {"role": "assistant", "content": None,
              "tool_calls": [{"id": "call_1", "function": {"name": "create_ticket",
              "arguments": "{\"title\": \"x\", \"priority\": \"low\"}"}}]}}],
              "usage": {"total_tokens": 9}}
    turn, _ = parse_response(CFG, payload)
    assert isinstance(turn, ToolCallTurn)
    call = turn.tool_calls[0]
    assert call.call_id == "call_1"
    assert call.name == "create_ticket"
    assert call.arguments == {"title": "x", "priority": "low"}


def test_malformed_arguments_become_empty_dict_with_raw_evidence():
    payload = {"choices": [{"message": {"tool_calls": [{"id": "c", "function":
              {"name": "t", "arguments": "{not json"}}]}}], "usage": {"total_tokens": 1}}
    turn, _ = parse_response(CFG, payload)
    assert turn.tool_calls[0].arguments == {"__raw__": "{not json"}


def test_client_reads_key_from_named_env(monkeypatch):
    monkeypatch.setenv("FAKE_API_KEY", "secret-123")
    captured = {}

    def transport(request):
        captured.update(request)
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"total_tokens": 2}}

    client = ProviderClient(CFG, transport=transport)
    turn, usage = client.complete(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert captured["headers"]["Authorization"] == "Bearer secret-123"
    assert isinstance(turn, MessageTurn)


def test_client_missing_key_does_not_crash_at_import_but_at_call(monkeypatch):
    monkeypatch.delenv("FAKE_API_KEY", raising=False)
    client = ProviderClient(CFG, transport=lambda r: {"choices": [{"message":
             {"content": "x"}}], "usage": {"total_tokens": 1}})
    # No key set: Authorization header is empty string, transport still injectable.
    turn, _ = client.complete(messages=[], tools=[])
    assert isinstance(turn, MessageTurn)


def test_cassette_replay(tmp_path: Path):
    cassette = {"choices": [{"message": {"role": "assistant", "content": "from cassette"}}],
                "usage": {"total_tokens": 5}}
    path = tmp_path / "c.json"
    path.write_text(json.dumps(cassette))

    def transport(_request):
        return json.loads(path.read_text())

    client = ProviderClient(CFG, transport=transport)
    turn, _ = client.complete(messages=[], tools=[])
    assert turn.content == "from cassette"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_provider.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write the provider module (edge; pure builder/parser + thin client)**

`src/agent_eval_lab/runners/provider.py`:

```python
"""OpenAI-compatible provider client. Pure request/response transforms; the only
effect is the injected transport. Key is read from the env var NAMED by
api_key_env (never hard-coded); tests inject a fake transport (no network).
"""

import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from agent_eval_lab.tasks.tool_calls import ToolCall
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn

Transport = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True, kw_only=True)
class ProviderConfig:
    id: str
    base_url: str
    api_key_env: str
    model_id: str
    extra_headers: Mapping[str, str] = field(default_factory=dict)
    adapter: str | None = None


def build_request(
    config: ProviderConfig,
    *,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build an OpenAI-compatible /chat/completions request body (pure)."""
    body: dict[str, Any] = {"model": config.model_id, "messages": list(messages)}
    if tools:
        body["tools"] = list(tools)
    return body


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    try:
        return dict(json.loads(raw))
    except (ValueError, TypeError):
        return {"__raw__": raw}


def parse_response(
    config: ProviderConfig, payload: Mapping[str, Any]
) -> tuple[MessageTurn | ToolCallTurn, dict[str, int]]:
    """Parse a /chat/completions response into a canonical Turn (pure)."""
    message = payload["choices"][0]["message"]
    usage = dict(payload.get("usage", {}))
    raw_calls = message.get("tool_calls")
    if raw_calls:
        calls = tuple(
            ToolCall(
                call_id=c.get("id", ""),
                name=c["function"]["name"],
                arguments=_parse_arguments(c["function"].get("arguments", {})),
            )
            for c in raw_calls
        )
        return ToolCallTurn(tool_calls=calls, content=message.get("content")), usage
    return MessageTurn(role="assistant", content=message.get("content") or ""), usage


def _real_transport(config: ProviderConfig) -> Transport:  # pragma: no cover - never run in tests
    import urllib.request

    def send(request: Mapping[str, Any]) -> Mapping[str, Any]:
        data = json.dumps(request["body"]).encode("utf-8")
        req = urllib.request.Request(
            f"{config.base_url}/chat/completions", data=data, headers=request["headers"]
        )
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    return send


class ProviderClient:
    """Thin client: build request, call transport, parse response."""

    def __init__(self, config: ProviderConfig, transport: Transport | None = None) -> None:
        self._config = config
        self._transport = transport if transport is not None else _real_transport(config)

    def _headers(self) -> dict[str, str]:
        key = os.environ.get(self._config.api_key_env, "")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        return {**headers, **dict(self._config.extra_headers)}

    def complete(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> tuple[MessageTurn | ToolCallTurn, dict[str, int]]:
        body = build_request(self._config, messages=messages, tools=tools)
        payload = self._transport({"body": body, "headers": self._headers()})
        return parse_response(self._config, payload)
```

> The fake transport in the test receives `{"body", "headers"}` and asserts on `request["headers"]["Authorization"]`. The `test_build_request_*` and `test_parse_response_*` tests call the pure functions directly. `_real_transport` is `# pragma: no cover` and never imported in tests.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_provider.py -q`
Expected: PASS — 7 passed.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/runners/__init__.py src/agent_eval_lab/runners/provider.py tests/runners/test_provider.py
git commit -m "feat(runners): add OpenAI-compatible provider client (fake-transport tested)"
```

### Task 16: Deterministic fake model

**Files:**
- Create: `src/agent_eval_lab/runners/fake_model.py`
- Test: `tests/runners/test_fake_model.py`

- [ ] **Step 1: Write the failing fake-model test**

`tests/runners/test_fake_model.py`:

```python
from agent_eval_lab.runners.fake_model import FakeModel
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn


def test_scripted_steps_replayed_in_order():
    model = FakeModel(scripts={"t1": [
        {"type": "tool_call", "name": "search_docs", "arguments": {"query": "x"}},
        {"type": "message", "content": "done"},
    ]})
    first = model.respond(task_id="t1", step=0)
    second = model.respond(task_id="t1", step=1)
    assert isinstance(first, ToolCallTurn)
    assert first.tool_calls[0].name == "search_docs"
    assert isinstance(second, MessageTurn)


def test_deterministic_same_inputs_same_call_id():
    script = {"t1": [{"type": "tool_call", "name": "search_docs", "arguments": {"query": "x"}}]}
    a = FakeModel(scripts=script).respond(task_id="t1", step=0)
    b = FakeModel(scripts=script).respond(task_id="t1", step=0)
    assert a.tool_calls[0].call_id == b.tool_calls[0].call_id


def test_usage_is_fixed_per_step():
    model = FakeModel(scripts={"t1": [{"type": "message", "content": "hi"}]})
    _, usage = model.respond_with_usage(task_id="t1", step=0)
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_fake_model.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the fake model**

`src/agent_eval_lab/runners/fake_model.py`:

```python
"""Deterministic fake model for runner tests + the report CLI smoke.

Replays a per-task script of canonical turns. call_id is derived deterministically
from (task_id, step, index) so the same inputs always yield the same trajectory.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.tasks.tool_calls import ToolCall
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn

_FIXED_USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def _to_turn(task_id: str, step: int, spec: Mapping[str, Any]) -> MessageTurn | ToolCallTurn:
    if spec["type"] == "message":
        return MessageTurn(role="assistant", content=spec["content"])
    call = ToolCall(
        call_id=f"{task_id}-{step}-0",
        name=spec["name"],
        arguments=dict(spec.get("arguments", {})),
    )
    return ToolCallTurn(tool_calls=(call,), content=spec.get("content"))


@dataclass(frozen=True, kw_only=True)
class FakeModel:
    scripts: Mapping[str, Sequence[Mapping[str, Any]]]

    def respond(self, *, task_id: str, step: int) -> MessageTurn | ToolCallTurn:
        return _to_turn(task_id, step, self.scripts[task_id][step])

    def respond_with_usage(
        self, *, task_id: str, step: int
    ) -> tuple[MessageTurn | ToolCallTurn, dict[str, int]]:
        return self.respond(task_id=task_id, step=step), dict(_FIXED_USAGE)

    def num_steps(self, task_id: str) -> int:
        return len(self.scripts[task_id])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_fake_model.py -q`
Expected: PASS — 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/fake_model.py tests/runners/test_fake_model.py
git commit -m "feat(runners): add deterministic fake model for runner tests"
```

---

## Phase 5 — multi-run runner with limits + cost/latency (Tasks 17–18)

**Verification point:** the runner threads world state explicitly, enforces max-turns/max-tool-calls, runs k ≥ 2 runs per task, emits `Trajectory` with cost+latency+run_index+termination_reason; same seed + input ⇒ identical trajectory hash. Driven by the deterministic fake model. No network.

### Task 17: The model↔tool loop with limits + multi-run

**Files:**
- Create: `src/agent_eval_lab/runners/runner.py`
- Test: `tests/runners/test_runner.py`

- [ ] **Step 1: Write the failing runner test**

`tests/runners/test_runner.py`:

```python
from agent_eval_lab.runners.fake_model import FakeModel
from agent_eval_lab.runners.runner import RunLimits, run_task
from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn, ToolResultTurn
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS, initial_state


def _task():
    return Task(
        id="t1", capability="tool_selection",
        input=TaskInput(messages=(MessageTurn(role="user", content="search install"),),
                        available_tools=({"name": "search_docs"},)),
        verification=ToolCallMatchSpec(
            expected_tool_calls=(ExpectedToolCall(name="search_docs", arguments={"query": "install"}),)),
        metadata=TaskMetadata(split="dev", version="1", provenance="handwritten",
                              world_template_id="workspace", difficulty_knob="baseline"),
        initial_state=initial_state(),
    )


def _model():
    return FakeModel(scripts={"t1": [
        {"type": "tool_call", "name": "search_docs", "arguments": {"query": "install"}},
        {"type": "message", "content": "Found it."},
    ]})


def test_run_task_emits_k_trajectories():
    results = run_task(_task(), _model(), TOOL_SCHEMAS, k=3, limits=RunLimits())
    assert [r.run_index for r in results] == [0, 1, 2]
    assert all(r.task_id == "t1" for r in results)


def test_trajectory_carries_cost_latency_and_termination():
    results = run_task(_task(), _model(), TOOL_SCHEMAS, k=1, limits=RunLimits())
    traj = results[0].trajectory
    assert traj.cost_usd >= 0.0
    assert traj.latency_ms >= 0
    assert traj.termination_reason == "stop"
    assert traj.usage["total_tokens"] > 0


def test_tool_result_turn_threaded_into_trajectory():
    results = run_task(_task(), _model(), TOOL_SCHEMAS, k=1, limits=RunLimits())
    kinds = [type(t).__name__ for t in results[0].trajectory.turns]
    assert "ToolCallTurn" in kinds
    assert "ToolResultTurn" in kinds


def test_grade_is_attached_and_passes():
    results = run_task(_task(), _model(), TOOL_SCHEMAS, k=1, limits=RunLimits())
    assert results[0].grade.passed is True


def test_max_tool_calls_limit_terminates_with_reason():
    model = FakeModel(scripts={"t1": [
        {"type": "tool_call", "name": "search_docs", "arguments": {"query": "a"}},
        {"type": "tool_call", "name": "search_docs", "arguments": {"query": "b"}},
        {"type": "message", "content": "done"},
    ]})
    results = run_task(_task(), model, TOOL_SCHEMAS, k=1, limits=RunLimits(max_tool_calls=1))
    assert results[0].trajectory.termination_reason == "max_tool_calls"
    assert results[0].grade.failure_reason == "step_limit_exceeded"


def test_max_turns_limit_terminates_with_reason():
    # Each tool-call step appends 2 turns (call + result); max_turns=2 trips at step 1.
    model = FakeModel(scripts={"t1": [
        {"type": "tool_call", "name": "search_docs", "arguments": {"query": "a"}},
        {"type": "tool_call", "name": "search_docs", "arguments": {"query": "b"}},
        {"type": "message", "content": "done"},
    ]})
    results = run_task(_task(), model, TOOL_SCHEMAS, k=1,
                       limits=RunLimits(max_turns=2, max_tool_calls=8))
    assert results[0].trajectory.termination_reason == "max_turns"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_runner.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the runner (edge)**

`src/agent_eval_lab/runners/runner.py`:

```python
"""Multi-run model<->tool loop (imperative shell).

Threads world state explicitly via tools.apply, enforces limits, runs k runs per
task, grades each, and emits RunResult records. Deterministic given a FakeModel.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.graders.grade import grade_trajectory
from agent_eval_lab.runners.fake_model import FakeModel
from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.task import Task
from agent_eval_lab.tasks.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolResultTurn,
)
from agent_eval_lab.tools.workspace_world import apply

_COST_PER_1K_TOKENS = 0.0005  # fixed synthetic price for the fake model


@dataclass(frozen=True, kw_only=True)
class RunLimits:
    max_turns: int = 8
    max_tool_calls: int = 8


def _cost(total_tokens: int) -> float:
    return round((total_tokens / 1000) * _COST_PER_1K_TOKENS, 8)


def _run_once(task: Task, model: FakeModel, schemas: Mapping[str, Any], run_index: int) -> RunResult:
    limits = _LIMITS_CTX[run_index] if run_index in _LIMITS_CTX else RunLimits()
    return _execute(task, model, schemas, run_index, limits)


def _execute(
    task: Task, model: FakeModel, schemas: Mapping[str, Any], run_index: int, limits: RunLimits
) -> RunResult:
    state = dict(task.initial_state or {})
    turns: list[Any] = []
    total_tokens = 0
    tool_calls_made = 0
    termination = "stop"
    for step in range(model.num_steps(task.id)):
        if len(turns) >= limits.max_turns:
            termination = "max_turns"
            break
        turn, usage = model.respond_with_usage(task_id=task.id, step=step)
        total_tokens += usage.get("total_tokens", 0)
        turns.append(turn)
        if isinstance(turn, ToolCallTurn):
            if tool_calls_made + len(turn.tool_calls) > limits.max_tool_calls:
                termination = "max_tool_calls"
                break
            for call in turn.tool_calls:
                state, outcome = apply(call.name, call.arguments, state)
                turns.append(ToolResultTurn(call_id=call.call_id, outcome=outcome))
                tool_calls_made += 1
        elif isinstance(turn, MessageTurn):
            termination = "stop"
            break
    trajectory = Trajectory(
        turns=tuple(turns),
        usage={"total_tokens": total_tokens},
        cost_usd=_cost(total_tokens),
        latency_ms=total_tokens,  # deterministic synthetic latency proxy
        run_index=run_index,
        termination_reason=termination,
    )
    grade = _grade(task, trajectory, schemas, termination)
    return RunResult(
        task_id=task.id, condition_id=task.metadata.split, run_index=run_index,
        trajectory=trajectory, grade=grade,
    )


def _grade(task: Task, trajectory: Trajectory, schemas, termination: str) -> GradeResult:
    if termination in ("max_turns", "max_tool_calls"):
        return GradeResult(
            grader_id="runner", passed=False, score=0.0,
            evidence={"termination_reason": termination},
            failure_reason="step_limit_exceeded",
        )
    return grade_trajectory(task.verification, trajectory.turns, schemas)


_LIMITS_CTX: dict[int, RunLimits] = {}


def run_task(
    task: Task, model: FakeModel, schemas: Mapping[str, Any], *, k: int, limits: RunLimits
) -> list[RunResult]:
    """Run the task k times under the given limits; emit one RunResult per run."""
    return [_execute(task, model, schemas, i, limits) for i in range(k)]
```

> Remove the unused `_run_once`/`_LIMITS_CTX` indirection in Step 4 refactor below — they are placeholders the green step does not need. Keep `_execute` + `run_task`.

- [ ] **Step 4: Run test, then refactor away dead code**

Run: `uv run pytest tests/runners/test_runner.py -q`
Expected: PASS — 6 passed.

Then delete the `_run_once` function and the `_LIMITS_CTX` dict (dead code), and re-run:

Run: `uv run pytest tests/runners/test_runner.py -q && uv run ruff check src/agent_eval_lab/runners/runner.py`
Expected: PASS — 6 passed; ruff clean (no unused-symbol warnings).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/runner.py tests/runners/test_runner.py
git commit -m "feat(runners): add multi-run model<->tool loop with limits + cost/latency"
```

### Task 18: Determinism guard (trajectory hash)

**Files:**
- Create: `src/agent_eval_lab/runners/hashing.py`
- Test: `tests/runners/test_runner_determinism.py`

- [ ] **Step 1: Write the failing determinism test (property-based)**

`tests/runners/test_runner_determinism.py`:

```python
from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.runners.fake_model import FakeModel
from agent_eval_lab.runners.hashing import trajectory_hash
from agent_eval_lab.runners.runner import RunLimits, run_task
from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall
from agent_eval_lab.tasks.turns import MessageTurn
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS, initial_state


def _task():
    return Task(
        id="t1", capability="tool_selection",
        input=TaskInput(messages=(MessageTurn(role="user", content="go"),),
                        available_tools=({"name": "search_docs"},)),
        verification=ToolCallMatchSpec(
            expected_tool_calls=(ExpectedToolCall(name="search_docs", arguments={"query": "x"}),)),
        metadata=TaskMetadata(split="dev", version="1", provenance="handwritten",
                              world_template_id="workspace", difficulty_knob="baseline"),
        initial_state=initial_state(),
    )


def _model():
    return FakeModel(scripts={"t1": [
        {"type": "tool_call", "name": "search_docs", "arguments": {"query": "x"}},
        {"type": "message", "content": "done"},
    ]})


@given(st.just(0))
def test_same_inputs_same_trajectory_hash(_seed):
    a = run_task(_task(), _model(), TOOL_SCHEMAS, k=1, limits=RunLimits())[0]
    b = run_task(_task(), _model(), TOOL_SCHEMAS, k=1, limits=RunLimits())[0]
    assert trajectory_hash(a.trajectory) == trajectory_hash(b.trajectory)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_runner_determinism.py -q`
Expected: FAIL — `ModuleNotFoundError` (hashing) and/or hypothesis not installed.

- [ ] **Step 3: Add hypothesis dev dep**

Edit `pyproject.toml`, change the `dev` group to:

```toml
[dependency-groups]
dev = [
  "pytest>=9.0.0",
  "ruff>=0.15.0",
  "hypothesis>=6.0.0",
]
```

Run: `uv sync --dev`
Expected: hypothesis installed.

- [ ] **Step 4: Write the trajectory hash (pure)**

`src/agent_eval_lab/runners/hashing.py`:

```python
"""Deterministic content hash over a Trajectory (determinism guard)."""

import hashlib
import json

from agent_eval_lab.tasks.codec import to_dict
from agent_eval_lab.tasks.grading import Trajectory


def trajectory_hash(trajectory: Trajectory) -> str:
    """SHA-256 over the canonical JSON serialization of the trajectory."""
    payload = json.dumps(to_dict(trajectory), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_runner_determinism.py -q`
Expected: PASS — 1 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/agent_eval_lab/runners/hashing.py tests/runners/test_runner_determinism.py
git commit -m "feat(runners): add trajectory-hash determinism guard; add hypothesis dev dep"
```

---

## Phase 6 — minimal metrics + pure baseline report + CLI (Tasks 19–21)

**Verification point:** metrics aggregate pass-over-k + cost/latency + failure-category counts purely; the report renders deterministically; `python -m agent_eval_lab.reports.baseline <runs.jsonl>` prints a report from committed recorded runs.

### Task 19: Minimal metrics aggregation

**Files:**
- Create: `src/agent_eval_lab/metrics/__init__.py`
- Create: `src/agent_eval_lab/metrics/baseline.py`
- Test: `tests/metrics/test_baseline.py`

- [ ] **Step 1: Create the package marker**

`src/agent_eval_lab/metrics/__init__.py`:

```python
"""Pure aggregation for the baseline report."""
```

- [ ] **Step 2: Write the failing metrics test**

`tests/metrics/test_baseline.py`:

```python
from agent_eval_lab.metrics.baseline import aggregate
from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.turns import MessageTurn


def _rr(task_id, run_index, passed, reason=None, cost=0.001, latency=10):
    traj = Trajectory(turns=(MessageTurn(role="assistant", content="x"),),
                      usage={"total_tokens": 15}, cost_usd=cost, latency_ms=latency,
                      run_index=run_index, termination_reason="stop")
    grade = GradeResult(grader_id="g", passed=passed, score=1.0 if passed else 0.0,
                        failure_reason=reason)
    return RunResult(task_id=task_id, condition_id="c", run_index=run_index,
                     trajectory=traj, grade=grade)


def test_pass_over_k_requires_all_runs_pass():
    runs = [_rr("t1", 0, True), _rr("t1", 1, False, reason="wrong_args")]
    summary = aggregate(runs)
    assert summary.per_task["t1"].runs == 2
    assert summary.per_task["t1"].passes == 1
    assert summary.per_task["t1"].pass_over_k is False


def test_aggregate_totals_and_failure_counts():
    runs = [_rr("t1", 0, True), _rr("t2", 0, False, reason="wrong_tool"),
            _rr("t2", 1, False, reason="schema_violation")]
    summary = aggregate(runs)
    assert summary.total_runs == 3
    assert summary.tasks_passing_all_k == 1  # only t1
    assert summary.failure_counts["wrong_tool"] == 1
    assert summary.failure_counts["schema_violation"] == 1
    assert round(summary.total_cost_usd, 6) == 0.003
    assert summary.mean_latency_ms == 10.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/metrics/test_baseline.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write the metrics (pure)**

`src/agent_eval_lab/metrics/baseline.py`:

```python
"""Pure baseline aggregation: pass-over-k, cost/latency, failure-category counts."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from agent_eval_lab.tasks.grading import RunResult


@dataclass(frozen=True, kw_only=True)
class TaskSummary:
    task_id: str
    runs: int
    passes: int
    pass_over_k: bool


@dataclass(frozen=True, kw_only=True)
class BaselineSummary:
    per_task: dict[str, TaskSummary]
    total_runs: int
    tasks_passing_all_k: int
    total_cost_usd: float
    mean_latency_ms: float
    failure_counts: dict[str, int]


def aggregate(runs: Sequence[RunResult]) -> BaselineSummary:
    """Aggregate RunResults into a deterministic baseline summary."""
    by_task: dict[str, list[RunResult]] = {}
    for run in runs:
        by_task.setdefault(run.task_id, []).append(run)
    per_task = {
        task_id: TaskSummary(
            task_id=task_id,
            runs=len(group),
            passes=sum(1 for r in group if r.grade.passed),
            pass_over_k=all(r.grade.passed for r in group),
        )
        for task_id, group in by_task.items()
    }
    failures = Counter(
        r.grade.failure_reason for r in runs if r.grade.failure_reason is not None
    )
    total_latency = sum(r.trajectory.latency_ms for r in runs)
    return BaselineSummary(
        per_task=per_task,
        total_runs=len(runs),
        tasks_passing_all_k=sum(1 for s in per_task.values() if s.pass_over_k),
        total_cost_usd=round(sum(r.trajectory.cost_usd for r in runs), 8),
        mean_latency_ms=(total_latency / len(runs)) if runs else 0.0,
        failure_counts=dict(failures),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/metrics/test_baseline.py -q`
Expected: PASS — 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/metrics/__init__.py src/agent_eval_lab/metrics/baseline.py tests/metrics/test_baseline.py
git commit -m "feat(metrics): add pure baseline aggregation (pass-over-k, cost, failures)"
```

### Task 20: Pure baseline report model + renderer

**Files:**
- Create: `src/agent_eval_lab/reports/__init__.py`
- Create: `src/agent_eval_lab/reports/baseline.py` (model + renderer; CLI added in Task 21)
- Test: `tests/reports/test_baseline_report.py`

- [ ] **Step 1: Create the package marker**

`src/agent_eval_lab/reports/__init__.py`:

```python
"""Pure report models + renderer; file write at the edge."""
```

- [ ] **Step 2: Write the failing renderer test**

`tests/reports/test_baseline_report.py`:

```python
from agent_eval_lab.metrics.baseline import aggregate
from agent_eval_lab.reports.baseline import render_report
from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.turns import MessageTurn


def _rr(task_id, run_index, passed, reason=None):
    traj = Trajectory(turns=(MessageTurn(role="assistant", content="x"),),
                      usage={"total_tokens": 15}, cost_usd=0.001, latency_ms=10,
                      run_index=run_index, termination_reason="stop")
    grade = GradeResult(grader_id="g", passed=passed, score=1.0 if passed else 0.0,
                        failure_reason=reason)
    return RunResult(task_id=task_id, condition_id="c", run_index=run_index,
                     trajectory=traj, grade=grade)


def test_render_is_deterministic_and_contains_headline_numbers():
    runs = [_rr("t1", 0, True), _rr("t1", 1, True), _rr("t2", 0, False, reason="wrong_tool")]
    summary = aggregate(runs)
    out_a = render_report(summary)
    out_b = render_report(summary)
    assert out_a == out_b
    assert "Baseline Report" in out_a
    assert "tasks passing all k: 1" in out_a
    assert "total runs: 3" in out_a
    assert "wrong_tool: 1" in out_a
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/reports/test_baseline_report.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write the report model + renderer (pure)**

`src/agent_eval_lab/reports/baseline.py`:

```python
"""Pure baseline report renderer. File write + CLI live at the edge (Task 21)."""

from agent_eval_lab.metrics.baseline import BaselineSummary


def render_report(summary: BaselineSummary) -> str:
    """Render a deterministic plain-text baseline report from a summary (pure)."""
    lines = ["# Baseline Report", ""]
    lines.append(f"total runs: {summary.total_runs}")
    lines.append(f"tasks: {len(summary.per_task)}")
    lines.append(f"tasks passing all k: {summary.tasks_passing_all_k}")
    lines.append(f"total cost (USD): {summary.total_cost_usd}")
    lines.append(f"mean latency (ms): {summary.mean_latency_ms}")
    lines.append("")
    lines.append("## Per-task (passes/runs, pass^k)")
    for task_id in sorted(summary.per_task):
        s = summary.per_task[task_id]
        lines.append(f"- {task_id}: {s.passes}/{s.runs} pass^k={s.pass_over_k}")
    lines.append("")
    lines.append("## Failure categories")
    if summary.failure_counts:
        for category in sorted(summary.failure_counts):
            lines.append(f"- {category}: {summary.failure_counts[category]}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/reports/test_baseline_report.py -q`
Expected: PASS — 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/reports/__init__.py src/agent_eval_lab/reports/baseline.py tests/reports/test_baseline_report.py
git commit -m "feat(reports): add pure baseline report renderer"
```

### Task 21: CLI entry point + committed recorded runs (/verify smoke target)

**Files:**
- Modify: `src/agent_eval_lab/reports/baseline.py` (append `main` + `__main__` guard)
- Create: `examples/datasets/recorded_runs.jsonl` (committed fake RunResults)
- Test: `tests/reports/test_baseline_cli.py`

- [ ] **Step 1: Generate the committed recorded runs**

Run this one-off (it writes a deterministic file from the fake model + runner; it performs file I/O at the edge only):

```bash
uv run python -c "
from pathlib import Path
from agent_eval_lab.runners.fake_model import FakeModel
from agent_eval_lab.runners.runner import RunLimits, run_task
from agent_eval_lab.tasks.loader import write_run_results
from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall
from agent_eval_lab.tasks.turns import MessageTurn
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS, initial_state

def task(tid, query):
    return Task(id=tid, capability='tool_selection',
      input=TaskInput(messages=(MessageTurn(role='user', content='search '+query),),
        available_tools=({'name':'search_docs'},)),
      verification=ToolCallMatchSpec(expected_tool_calls=(ExpectedToolCall(name='search_docs', arguments={'query': query}),)),
      metadata=TaskMetadata(split='dev', version='1', provenance='handwritten', world_template_id='workspace', difficulty_knob='baseline'),
      initial_state=initial_state())

# t1 passes; t2 calls wrong tool -> wrong_tool failure
m1 = FakeModel(scripts={'t1': [{'type':'tool_call','name':'search_docs','arguments':{'query':'install'}}, {'type':'message','content':'done'}]})
m2 = FakeModel(scripts={'t2': [{'type':'tool_call','name':'create_ticket','arguments':{'title':'x','priority':'low'}}, {'type':'message','content':'done'}]})
runs = run_task(task('t1','install'), m1, TOOL_SCHEMAS, k=2, limits=RunLimits())
runs += run_task(task('t2','install'), m2, TOOL_SCHEMAS, k=2, limits=RunLimits())
write_run_results(Path('examples/datasets/recorded_runs.jsonl'), runs)
print('wrote', len(runs), 'runs')
"
```

Expected: `wrote 4 runs` and the file `examples/datasets/recorded_runs.jsonl` exists with 4 lines.

- [ ] **Step 2: Write the failing CLI test**

`tests/reports/test_baseline_cli.py`:

```python
from pathlib import Path

from agent_eval_lab.reports.baseline import main


def test_cli_renders_report_from_recorded_runs(capsys):
    code = main(["examples/datasets/recorded_runs.jsonl"])
    out = capsys.readouterr().out
    assert code == 0
    assert "# Baseline Report" in out
    assert "total runs: 4" in out


def test_cli_committed_file_exists():
    assert Path("examples/datasets/recorded_runs.jsonl").exists()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/reports/test_baseline_cli.py -q`
Expected: FAIL — `ImportError: cannot import name 'main'`.

- [ ] **Step 4: Append the CLI edge to reports/baseline.py**

Add to the end of `src/agent_eval_lab/reports/baseline.py`:

```python
def main(argv: list[str] | None = None) -> int:
    """CLI edge: render a baseline report from a RunResult JSONL file."""
    import sys
    from pathlib import Path

    from agent_eval_lab.metrics.baseline import aggregate
    from agent_eval_lab.tasks.loader import load_run_results

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python -m agent_eval_lab.reports.baseline <runs.jsonl>")
        return 2
    runs = load_run_results(Path(args[0]))
    print(render_report(aggregate(runs)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/reports/test_baseline_cli.py -q`
Expected: PASS — 2 passed.

- [ ] **Step 6: Smoke the CLI manually (this is the `/verify` target)**

Run: `uv run python -m agent_eval_lab.reports.baseline examples/datasets/recorded_runs.jsonl`
Expected: prints a report with `total runs: 4`, `tasks passing all k: 1`, and `wrong_tool: 2` under failure categories.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/reports/baseline.py examples/datasets/recorded_runs.jsonl tests/reports/test_baseline_cli.py
git commit -m "feat(reports): add baseline CLI + committed recorded runs (/verify smoke)"
```

---

## Phase 7 — golden conformance suite + property-based tests (Tasks 22–23)

**Verification point:** every taxonomy category in A3 has a hand-verified golden fixture graded through the harness equal to the oracle; canonicalization idempotence and the "schema-invalid never passes" invariant hold under Hypothesis. Runs in CI.

### Task 22: Golden conformance suite

**Files:**
- Create: `tests/graders/conformance/cases.json`
- Create: `tests/graders/test_conformance.py`

- [ ] **Step 1: Write the conformance fixtures (hand-verified oracle)**

`tests/graders/conformance/cases.json` — each case is `{name, match, expected, observed, oracle}` where `oracle = {passed, failure_reason}`:

```json
[
  {"name": "exact_pass", "match": "exact_sequence",
   "expected": [{"name": "search_docs", "arguments": {"query": "install"}}],
   "observed": [{"call_id": "c1", "name": "search_docs", "arguments": {"query": "install"}}],
   "oracle": {"passed": true, "failure_reason": null}},
  {"name": "malformed_call", "match": "exact_sequence",
   "expected": [{"name": "search_docs", "arguments": {"query": "x"}}],
   "observed": [{"call_id": "c1", "name": "no_such_tool", "arguments": {}}],
   "oracle": {"passed": false, "failure_reason": "malformed_call"}},
  {"name": "schema_violation_coercion", "match": "exact_sequence",
   "expected": [{"name": "create_ticket", "arguments": {"title": "x", "priority": "low"}}],
   "observed": [{"call_id": "c1", "name": "create_ticket", "arguments": {"title": 1, "priority": "low"}}],
   "oracle": {"passed": false, "failure_reason": "schema_violation"}},
  {"name": "schema_violation_enum", "match": "exact_sequence",
   "expected": [{"name": "create_ticket", "arguments": {"title": "x", "priority": "low"}}],
   "observed": [{"call_id": "c1", "name": "create_ticket", "arguments": {"title": "x", "priority": "urgent"}}],
   "oracle": {"passed": false, "failure_reason": "schema_violation"}},
  {"name": "wrong_tool", "match": "exact_sequence",
   "expected": [{"name": "search_docs", "arguments": {"query": "x"}}],
   "observed": [{"call_id": "c1", "name": "create_ticket", "arguments": {"title": "x", "priority": "low"}}],
   "oracle": {"passed": false, "failure_reason": "wrong_tool"}},
  {"name": "wrong_args", "match": "exact_sequence",
   "expected": [{"name": "search_docs", "arguments": {"query": "install"}}],
   "observed": [{"call_id": "c1", "name": "search_docs", "arguments": {"query": "deploy"}}],
   "oracle": {"passed": false, "failure_reason": "wrong_args"}},
  {"name": "missing_call", "match": "exact_sequence",
   "expected": [{"name": "create_ticket", "arguments": {"title": "x", "priority": "low"}},
                {"name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}}],
   "observed": [{"call_id": "c1", "name": "create_ticket", "arguments": {"title": "x", "priority": "low"}}],
   "oracle": {"passed": false, "failure_reason": "missing_call"}},
  {"name": "extra_call", "match": "exact_sequence",
   "expected": [{"name": "search_docs", "arguments": {"query": "x"}}],
   "observed": [{"call_id": "c1", "name": "search_docs", "arguments": {"query": "x"}},
                {"call_id": "c2", "name": "search_docs", "arguments": {"query": "y"}}],
   "oracle": {"passed": false, "failure_reason": "extra_call"}},
  {"name": "order_mismatch", "match": "exact_sequence",
   "expected": [{"name": "create_ticket", "arguments": {"title": "x", "priority": "low"}},
                {"name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}}],
   "observed": [{"call_id": "c1", "name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}},
                {"call_id": "c2", "name": "create_ticket", "arguments": {"title": "x", "priority": "low"}}],
   "oracle": {"passed": false, "failure_reason": "order_mismatch"}},
  {"name": "multiset_pass_unordered", "match": "multiset",
   "expected": [{"name": "create_ticket", "arguments": {"title": "x", "priority": "low"}},
                {"name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}}],
   "observed": [{"call_id": "c1", "name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}},
                {"call_id": "c2", "name": "create_ticket", "arguments": {"title": "x", "priority": "low"}}],
   "oracle": {"passed": true, "failure_reason": null}}
]
```

- [ ] **Step 2: Write the conformance test that drives every case through the harness**

`tests/graders/test_conformance.py`:

```python
import json
from pathlib import Path

import pytest

from agent_eval_lab.graders.ast_tool_match import grade_tool_calls
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS

CASES = json.loads((Path(__file__).parent / "conformance" / "cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_conformance_matches_oracle(case):
    spec = ToolCallMatchSpec(
        expected_tool_calls=tuple(
            ExpectedToolCall(name=e["name"], arguments=e["arguments"]) for e in case["expected"]
        ),
        match=case["match"],
    )
    observed = tuple(
        ToolCall(call_id=o["call_id"], name=o["name"], arguments=o["arguments"])
        for o in case["observed"]
    )
    result = grade_tool_calls(spec, observed, TOOL_SCHEMAS)
    assert result.passed is case["oracle"]["passed"]
    assert result.failure_reason == case["oracle"]["failure_reason"]
```

- [ ] **Step 3: Run test to verify it passes (the grader already exists)**

Run: `uv run pytest tests/graders/test_conformance.py -q`
Expected: PASS — 10 passed (one per case). If any case fails, the grader (Task 12) is wrong — fix the grader, not the oracle.

- [ ] **Step 4: Commit**

```bash
git add tests/graders/conformance/cases.json tests/graders/test_conformance.py
git commit -m "test(graders): add golden conformance suite covering the failure taxonomy"
```

### Task 23: Property-based invariants (A4)

**Files:**
- Create: `tests/graders/test_canonicalize_properties.py`

- [ ] **Step 1: Write the property-based tests**

`tests/graders/test_canonicalize_properties.py`:

```python
from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.graders.ast_tool_match import grade_tool_calls
from agent_eval_lab.graders.canonicalize import canonicalize
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS

# JSON-ish values the grader may encounter.
json_scalars = st.none() | st.booleans() | st.integers() | st.text()
json_values = st.recursive(
    json_scalars,
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=8,
)


@given(json_values)
def test_canonicalize_is_idempotent(value):
    once = canonicalize(value)
    assert canonicalize(value) == once  # stable across repeated calls
    assert canonicalize(once) == once  # true fixed point: f(f(x)) == f(x)


@given(st.text(min_size=1))
def test_schema_invalid_priority_never_passes(bad_priority):
    # Any priority outside the enum must never grade as pass.
    from hypothesis import assume

    assume(bad_priority not in ("low", "medium", "high"))
    spec = ToolCallMatchSpec(
        expected_tool_calls=(
            ExpectedToolCall(name="create_ticket", arguments={"title": "x", "priority": "low"}),
        )
    )
    observed = (ToolCall(call_id="c1", name="create_ticket",
                         arguments={"title": "x", "priority": bad_priority}),)
    result = grade_tool_calls(spec, observed, TOOL_SCHEMAS)
    assert result.passed is False
    assert result.failure_reason == "schema_violation"


@given(st.integers())
def test_type_coercion_title_never_passes(bad_title):
    # An int title (type-coercion attempt) must never pass.
    spec = ToolCallMatchSpec(
        expected_tool_calls=(
            ExpectedToolCall(name="create_ticket", arguments={"title": "x", "priority": "low"}),
        )
    )
    observed = (ToolCall(call_id="c1", name="create_ticket",
                         arguments={"title": bad_title, "priority": "low"}),)
    result = grade_tool_calls(spec, observed, TOOL_SCHEMAS)
    assert result.passed is False
    assert result.failure_reason == "schema_violation"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_canonicalize_properties.py -q`
Expected: PASS — 3 passed (Hypothesis runs many examples each).

- [ ] **Step 3: Run the FULL suite + lint (phase gate)**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: everything passes (~80+ tests); ruff clean. Reformat + amend if `ruff format --check` flags anything.

- [ ] **Step 4: Commit**

```bash
git add tests/graders/test_canonicalize_properties.py
git commit -m "test(graders): add property-based canonicalization + never-pass-invalid invariants"
```

---

## Phase 8 — docs reconcile (Task 24)

**Verification point:** ARCHITECTURE.md, ROADMAP.md, and design §13 reflect what shipped; the dataset note documents the new format. `uv run pytest && uv run ruff check . && uv run ruff format --check .` still green.

### Task 24: Reconcile docs

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/superpowers/specs/2026-06-09-agent-eval-pipeline-design.md`
- Create: `docs/2026-06-10-tool-use-slice/items/dataset-note.md`

- [ ] **Step 1: Update ARCHITECTURE.md "Initial Vertical Slice" section**

In `docs/ARCHITECTURE.md`, replace the final "Initial Vertical Slice" paragraph with text that states what landed: the locked record spine (`tasks/`), the schema-validated `workspace-world` (`search_docs`, `create_ticket`, `update_ticket` over `{tickets, docs}`), the schema-first AST grader with the 7-category tool-call taxonomy + `step_limit_exceeded`, the OpenAI-compatible provider client (fake-transport tested), the multi-run runner with limits and cost/latency, the golden conformance suite, and the baseline report + CLI. Note that JSON-Schema validation is a single vendored validator shared by the world boundary and the grader.

- [ ] **Step 2: Update ROADMAP.md Wk 1–2 row to landed status**

In `docs/ROADMAP.md`, mark the Weeks 1–2 deliverable as delivered (e.g. prefix with `[done]` or move to a "Shipped" subsection if the file has one) listing the eight deliverables from the spec. Keep the rest of the roadmap unchanged.

- [ ] **Step 3: Update design §13 delta toward "done"**

In `docs/superpowers/specs/2026-06-09-agent-eval-pipeline-design.md` §13, annotate the landed rows: Graders (AST tool grader + `evidence`/`failure_reason` now present), Dataset (`tool_use.jsonl` full Task records), Modules (`tasks/ tools/ runners/ metrics/ reports/` now exist), Runs (`Trajectory`, multi-run, cost/latency present). Leave `experiments/`, `data/`, `finetune/` as not-yet. Do not rewrite the rationale — just mark landed pieces (e.g. a trailing "✅ landed (slice 001)" note per row).

- [ ] **Step 4: Write the dataset note**

`docs/2026-06-10-tool-use-slice/items/dataset-note.md`:

```markdown
# Dataset note — `examples/datasets/tool_use.jsonl`

Replaces the name-only `tool_selection.jsonl`. Each line is a full `Task` record
(see `src/agent_eval_lab/tasks/codec.py` for the exact dict shape).

## Schema (per line)

- `id` — `tool-use-NNN`.
- `capability` — `tool_selection` | `argument_extraction`.
- `input.messages` — tuple of `MessageTurn` dicts (`{type:"message", role, content}`).
- `input.available_tools` — list of `{name, schema}`; `schema` mirrors the tool's
  entry in `tools/workspace_world.TOOL_SCHEMAS`.
- `verification` — always a `tool_call_match` spec with `match` ∈
  {`exact_sequence`, `multiset`} and `expected_tool_calls` (no `call_id`).
- `metadata` — `split` (`dev`|`held_out`), `version`, `provenance`,
  `world_template_id` (`workspace`), `difficulty_knob`
  (`baseline`|`distractor`|`enum_arg`|`multi_step`).
- `initial_state` — `{tickets, docs}` or `null`.

## Coverage

~20 tasks: tool-selection (distractor tools present), argument-extraction
(enum + exact-string args), and multi-step (create→update, both match modes).
The world boundary and the AST grader validate args with the **same** vendored
JSON-Schema validator, so "invalid" means the same thing in both.
```

- [ ] **Step 5: Verify the suite + lint still pass**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green (docs changes do not affect tests).

- [ ] **Step 6: Commit**

```bash
git add docs/ARCHITECTURE.md docs/ROADMAP.md docs/superpowers/specs/2026-06-09-agent-eval-pipeline-design.md docs/2026-06-10-tool-use-slice/items/dataset-note.md
git commit -m "docs: reconcile ARCHITECTURE/ROADMAP/design-delta with shipped tool-use slice"
```

---

## Final verification (whole-slice acceptance gate)

- [ ] **Run the entire suite, lint, and format check**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all tests pass; `ruff check` clean; `ruff format --check` reports nothing to reformat.

- [ ] **Smoke the CLI (the `/verify` target)**

Run: `uv run python -m agent_eval_lab.reports.baseline examples/datasets/recorded_runs.jsonl`
Expected: a deterministic baseline report printing `total runs: 4`, `tasks passing all k: 1`, and a `wrong_tool` failure count.

- [ ] **Confirm no live network / no API key required**

Run: `env -u DEEPSEEK_API_KEY -u DASHSCOPE_API_KEY -u OPENAI_API_KEY -u FAKE_API_KEY uv run pytest -q`
Expected: still all pass — nothing in the suite requires a key or a socket.

---

## Acceptance-criteria → task map (self-review coverage)

| Spec criterion | Delivered by |
|---|---|
| A1 records + JSONL round-trip (incl. discriminators) | Tasks 1–7 (codec round-trip Task 6) |
| A2 workspace-world 2–3 tools, pure apply, valid→Success/invalid→Failure, no mutation | Task 9 |
| A3 AST grader emits every FailureCategory | Task 12 + conformance Task 22 |
| A4 canonicalization value-preserving + idempotent; invalid never passes (property) | Tasks 11, 23 |
| A5 provider client OpenAI-compatible, fake transport, key from named env, adapter hook | Task 15 |
| A6 runner: loop, explicit state, limits, k≥2 runs, cost+latency, determinism guard | Tasks 17, 18 |
| A7 golden conformance suite matches oracle in CI | Task 22 |
| A8 pure baseline report from RunResults; committed example | Tasks 19, 20, 21 |
| A9 `uv run pytest`/`ruff`/`format` green; hypothesis dev dep; CI without secrets | Tasks 18 (dep), final gate |
| A10 docs reconciled (ARCHITECTURE, ROADMAP, §13, dataset note) | Task 24 |
| GradeResult migration; exact_match → OutputMatchSpec scorer | Task 10 |
| Open VerificationSpec union rejects unimplemented variants | Tasks 3, 13 |

---

## Execution Handoff

Plan complete and saved to `docs/2026-06-10-tool-use-slice/items/001-plan.md`. Recommended execution: **subagent-driven** (REQUIRED SUB-SKILL: superpowers:subagent-driven-development) — a fresh subagent per task with two-stage review, since each task is independently testable and the plan is bite-sized. Inline execution (superpowers:executing-plans) is the alternative if a single session is preferred.
