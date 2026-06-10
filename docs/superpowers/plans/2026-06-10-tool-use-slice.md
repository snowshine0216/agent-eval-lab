# Weeks 1–2 Tool-Use Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimum evaluation system for tool use: locked record types and `VerificationSpec` subset, a schema-validated synthetic workspace-world, an AST tool-call grader with a structured failure taxonomy, an OpenAI-compatible provider client, a multi-run model↔tool loop with limits and cost capture, a 20-task dataset, a golden conformance suite, and a baseline report generator.

**Architecture:** Functional core / imperative shell (see [docs/ARCHITECTURE.md](../../ARCHITECTURE.md)). All records are frozen `kw_only` stdlib dataclasses serializable to JSONL. Pure modules: `records/`, `tasks/` (schema+parse), `tools/`, `graders/`, `metrics/`, `reports/`. Edges: `tasks/loader.py`, `runners/`, `cli.py`. Source spec: [2026-06-09-agent-eval-pipeline-design.md](../specs/2026-06-09-agent-eval-pipeline-design.md) §16.

**Tech Stack:** Python 3.11, stdlib `dataclasses`, `jsonschema` (arg validation), `httpx` (client), `pytest` + `hypothesis` (tests), `uv`, `ruff`.

**Validation before every commit** (per AGENTS.md):

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
```

If `ruff format --check` reports differences, run `uv run ruff format .` to apply the canonical formatting (it reflows long call expressions under the 88-column limit), re-run the tests, and then commit.

## Design decisions locked by this plan

1. **`records/` package (not in the spec's module list).** Turn/Trajectory/Grade records are shared by `tasks`, `graders`, `runners`, `metrics`. Putting them in `runners/` would force pure graders to import from the imperative shell. `records/` is a pure leaf; every other module depends on it, never the reverse.
2. **Weeks 1–2 `VerificationSpec` subset = `OutputMatchSpec | ToolCallMatchSpec`.** `FinalStateSpec`/`TrajectorySpec`/`AllOf`/judge specs arrive in Weeks 3–4 per the roadmap. The union is extended later without breaking serialization (each variant is discriminated by `type`).
3. **`malformed_call` is captured at the parse boundary.** The runner parses provider payloads with a pure function; an unparseable tool call becomes `Trajectory.parse_failure`, which the grader maps to `malformed_call`. Schema validation happens on the parsed-as-is JSON values (no coercion), so `"1"` where an int is required is a `schema_violation` — never repaired.
4. **Tasks reference tools by name; `WORKSPACE_TOOLS` is the single source of truth for schemas.** The grader and the world validate with the same `validate_args` function, so they agree on what "invalid" means.
5. **`Task.scripted_user` is omitted until Phase 1b (multi-turn, Weeks 9–10).** Adding a `kw_only` field with a default later is non-breaking.
6. **Cost is derived, not stored:** `Usage` captures tokens + latency per run; `TokenPrice` (CLI flags) converts to USD at report time. No hardcoded price tables that go stale.
7. **Failure-category precedence (documented + tested):** `malformed_call` > `schema_violation` > `missing_call`/`extra_call` (length) > `order_mismatch` > `wrong_tool` > `wrong_args`.

## File structure

```text
src/agent_eval_lab/
  records/
    __init__.py
    turns.py        ToolCall, MessageTurn, ToolCallTurn, ToolSuccess/ToolFailure, ToolResultTurn, Turn
    trajectory.py   ParseFailure, Usage, Trajectory
    grade.py        FailureCategory, GradeResult, RunResult
    serialize.py    dict round-trip for turns/trajectories; to_dict for grades/runs
  tasks/
    __init__.py
    schema.py       ExpectedToolCall, OutputMatchSpec, ToolCallMatchSpec, VerificationSpec, TaskInput, TaskMetadata, Task
    parse.py        pure dict -> Task / VerificationSpec
    loader.py       EDGE: JSONL file -> tuple[Task, ...]
  tools/
    __init__.py
    validation.py   validate_args(schema, args) -> str | None  (jsonschema)
    workspace.py    ToolDef, WORKSPACE_TOOLS, apply(registry, name, arguments, state) -> (state', ToolOutcome)
  graders/
    __init__.py
    canonical.py    canonicalize() — sorted keys, sequences -> tuples, value-preserving
    exact_match.py  grade_exact_match (reworked to new GradeResult)
    tool_call.py    grade_tool_call_match — AST pipeline + failure taxonomy
    dispatch.py     grade_trajectory / grade_output_match
  runners/
    __init__.py
    config.py       ProviderConfig, PROVIDERS registry
    parse.py        pure: provider message dict -> MessageTurn | ToolCallTurn | ParseFailure
    wire.py         pure: ToolDef/Turn -> OpenAI wire format
    client.py       EDGE: chat_completion via httpx, retry, latency
    loop.py         EDGE: run_single model<->tool loop with max_steps
    multi_run.py    EDGE: run_task_k -> tuple[RunResult, ...]
  metrics/
    __init__.py
    reliability.py  pass_at_1, pass_pow_k, failure_counts, mean_latency_s, token_totals
    cost.py         TokenPrice, total_cost_usd
  reports/
    __init__.py
    baseline.py     BaselineReport, build_baseline_report, render_markdown (pure)
  cli.py            EDGE: run-baseline command
tests/
  records/  tasks/  tools/  graders/  runners/  metrics/  reports/  datasets/
  golden/           11 hand-verified conformance cases (JSON)
  test_golden_conformance.py
  test_cli.py
examples/datasets/workspace_tool_use_v1.jsonl   20 tasks (replaces tool_selection.jsonl)
```

---

### Task 1: Dependencies

**Files:**
- Modify: `pyproject.toml` (via `uv add`)

- [ ] **Step 1: Add runtime and dev dependencies**

```bash
uv add "jsonschema>=4.21" "httpx>=0.27"
uv add --dev "hypothesis>=6.100"
```

- [ ] **Step 2: Verify the environment still passes**

Run: `uv run pytest && uv run ruff check .`
Expected: 2 passed; no lint errors.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add jsonschema, httpx, hypothesis dependencies"
```

---

### Task 2: Conversation records — turns and tool calls

**Files:**
- Create: `src/agent_eval_lab/records/__init__.py`
- Create: `src/agent_eval_lab/records/turns.py`
- Test: `tests/records/test_turns.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/records/test_turns.py
from dataclasses import FrozenInstanceError

import pytest

from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)


def test_message_turn_has_discriminator_and_is_frozen() -> None:
    turn = MessageTurn(role="user", content="hi")

    assert turn.type == "message"
    with pytest.raises(FrozenInstanceError):
        turn.content = "changed"  # type: ignore[misc]


def test_tool_call_turn_supports_parallel_calls() -> None:
    calls = (
        ToolCall(call_id="c1", name="search_docs", arguments={"query": "a"}),
        ToolCall(call_id="c2", name="search_docs", arguments={"query": "b"}),
    )
    turn = ToolCallTurn(tool_calls=calls)

    assert turn.type == "tool_call"
    assert turn.content is None
    assert len(turn.tool_calls) == 2


def test_tool_outcome_variants_are_mutually_exclusive_by_construction() -> None:
    success = ToolSuccess(result={"doc_ids": ["doc-1"]})
    failure = ToolFailure(error="schema violation: priority")

    assert success.type == "success"
    assert failure.type == "failure"
    assert not hasattr(success, "error")
    assert not hasattr(failure, "result")


def test_tool_result_turn_links_to_call_id() -> None:
    turn = ToolResultTurn(call_id="c1", outcome=ToolSuccess(result=None))

    assert turn.type == "tool_result"
    assert turn.call_id == "c1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/records/test_turns.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.records'`

- [ ] **Step 3: Implement the records**

```python
# src/agent_eval_lab/records/__init__.py
"""Immutable record spine shared by tasks, tools, graders, runners, metrics."""
```

```python
# src/agent_eval_lab/records/turns.py
"""Conversation turns and tool calls (spec §4.1–§4.2 of the design doc)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, kw_only=True)
class ToolCall:
    """Run-time tool call; call_id is generated by the provider."""

    call_id: str
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, kw_only=True)
class MessageTurn:
    type: Literal["message"] = "message"
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, kw_only=True)
class ToolCallTurn:
    type: Literal["tool_call"] = "tool_call"
    tool_calls: tuple[ToolCall, ...]
    content: str | None = None


@dataclass(frozen=True, kw_only=True)
class ToolSuccess:
    type: Literal["success"] = "success"
    result: Any


@dataclass(frozen=True, kw_only=True)
class ToolFailure:
    type: Literal["failure"] = "failure"
    error: str


ToolOutcome = ToolSuccess | ToolFailure


@dataclass(frozen=True, kw_only=True)
class ToolResultTurn:
    type: Literal["tool_result"] = "tool_result"
    call_id: str
    outcome: ToolOutcome


Turn = MessageTurn | ToolCallTurn | ToolResultTurn
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/records/test_turns.py -v`
Expected: 4 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/records tests/records
git commit -m "feat: add conversation turn and tool-call records"
```

---

### Task 3: Trajectory, usage, and grade records; rework exact_match

**Files:**
- Create: `src/agent_eval_lab/records/trajectory.py`
- Create: `src/agent_eval_lab/records/grade.py`
- Modify: `src/agent_eval_lab/graders/exact_match.py`
- Test: `tests/records/test_trajectory.py`
- Modify: `tests/graders/test_exact_match.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/records/test_trajectory.py
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _trajectory(**overrides):
    defaults = dict(
        turns=(MessageTurn(role="user", content="hi"),),
        usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.5),
        run_index=0,
        stop_reason="completed",
    )
    return Trajectory(**{**defaults, **overrides})


def test_trajectory_defaults_to_no_parse_failure() -> None:
    trajectory = _trajectory()

    assert trajectory.parse_failure is None
    assert trajectory.stop_reason == "completed"


def test_trajectory_records_parse_failure() -> None:
    failure = ParseFailure(raw='{"query": ', error="arguments not valid JSON")
    trajectory = _trajectory(stop_reason="parse_failure", parse_failure=failure)

    assert trajectory.parse_failure.error == "arguments not valid JSON"


def test_run_result_links_task_condition_and_grade() -> None:
    grade = GradeResult(
        grader_id="ast_tool_match",
        passed=True,
        score=1.0,
        evidence={},
        failure_reason=None,
    )
    run = RunResult(
        task_id="ws-001",
        condition_id="local:qwen3-8b",
        run_index=2,
        trajectory=_trajectory(run_index=2),
        grade=grade,
    )

    assert run.run_index == 2
    assert run.grade.passed is True
```

Replace the whole of `tests/graders/test_exact_match.py` with:

```python
# tests/graders/test_exact_match.py
from agent_eval_lab.graders.exact_match import grade_exact_match


def test_exact_match_passes_identical_values() -> None:
    result = grade_exact_match(expected="get_weather", actual="get_weather")

    assert result.passed is True
    assert result.score == 1.0
    assert result.grader_id == "output_match"
    assert result.failure_reason is None
    assert result.evidence == {"expected": "get_weather", "actual": "get_weather"}


def test_exact_match_fails_different_values() -> None:
    result = grade_exact_match(expected="get_weather", actual="search_docs")

    assert result.passed is False
    assert result.score == 0.0
    assert result.failure_reason is None
    assert result.evidence == {"expected": "get_weather", "actual": "search_docs"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/records/test_trajectory.py tests/graders/test_exact_match.py -v`
Expected: FAIL — no module `records.trajectory` / `records.grade`; exact_match assertions fail on `grader_id`.

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/records/trajectory.py
"""Run-time trajectory records emitted by the runner."""

from dataclasses import dataclass
from typing import Literal

from agent_eval_lab.records.turns import Turn


@dataclass(frozen=True, kw_only=True)
class ParseFailure:
    """Provider output that could not be parsed into a Turn (malformed call)."""

    type: Literal["parse_failure"] = "parse_failure"
    raw: str
    error: str


@dataclass(frozen=True, kw_only=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    latency_s: float


@dataclass(frozen=True, kw_only=True)
class Trajectory:
    turns: tuple[Turn, ...]
    usage: Usage
    run_index: int
    stop_reason: Literal["completed", "max_steps", "parse_failure"]
    parse_failure: ParseFailure | None = None
```

```python
# src/agent_eval_lab/records/grade.py
"""Grading records and the structured failure taxonomy (spec §4.5)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.trajectory import Trajectory

FailureCategory = Literal[
    "malformed_call",
    "schema_violation",
    "wrong_tool",
    "wrong_args",
    "missing_call",
    "extra_call",
    "order_mismatch",
    "forbidden_action",
    "step_limit_exceeded",
]


@dataclass(frozen=True, kw_only=True)
class GradeResult:
    grader_id: str
    passed: bool
    score: float
    evidence: Mapping[str, Any]
    failure_reason: FailureCategory | None = None


@dataclass(frozen=True, kw_only=True)
class RunResult:
    task_id: str
    condition_id: str
    run_index: int
    trajectory: Trajectory
    grade: GradeResult
```

Replace the whole of `src/agent_eval_lab/graders/exact_match.py` with:

```python
# src/agent_eval_lab/graders/exact_match.py
"""Deterministic exact-match grading (the OutputMatchSpec scorer)."""

from agent_eval_lab.records.grade import GradeResult


def grade_exact_match(*, expected: str, actual: str) -> GradeResult:
    """Grade values that match exactly."""
    passed = expected == actual
    return GradeResult(
        grader_id="output_match",
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={"expected": expected, "actual": actual},
        failure_reason=None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all tests pass (old GradeResult is gone; nothing else imported it).

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add -A src tests
git commit -m "feat: add trajectory/grade records; extend GradeResult with evidence and failure_reason"
```

---

### Task 4: Serialization round-trip

**Files:**
- Create: `src/agent_eval_lab/records/serialize.py`
- Test: `tests/records/test_serialize.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/records/test_serialize.py
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.serialize import (
    grade_result_to_dict,
    run_result_to_dict,
    trajectory_from_dict,
    trajectory_to_dict,
    turn_from_dict,
    turn_to_dict,
)
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)

TURNS = (
    MessageTurn(role="user", content="Close ticket T-7."),
    ToolCallTurn(
        tool_calls=(
            ToolCall(
                call_id="c1",
                name="update_ticket",
                arguments={"ticket_id": "T-7", "status": "closed"},
            ),
        ),
        content=None,
    ),
    ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"ticket_id": "T-7"})),
    ToolResultTurn(call_id="c2", outcome=ToolFailure(error="unknown ticket_id: T-9")),
    MessageTurn(role="assistant", content="Done."),
)


def test_every_turn_variant_round_trips() -> None:
    for turn in TURNS:
        assert turn_from_dict(turn_to_dict(turn)) == turn


def test_trajectory_round_trips_including_parse_failure() -> None:
    trajectory = Trajectory(
        turns=TURNS,
        usage=Usage(prompt_tokens=12, completion_tokens=7, latency_s=0.25),
        run_index=1,
        stop_reason="parse_failure",
        parse_failure=ParseFailure(raw='{"q": ', error="bad json"),
    )

    assert trajectory_from_dict(trajectory_to_dict(trajectory)) == trajectory


def test_trajectory_from_dict_applies_defaults() -> None:
    trajectory = trajectory_from_dict(
        {"turns": [{"type": "message", "role": "user", "content": "hi"}]}
    )

    assert trajectory.usage == Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0)
    assert trajectory.run_index == 0
    assert trajectory.stop_reason == "completed"
    assert trajectory.parse_failure is None


def test_run_result_to_dict_is_json_shaped() -> None:
    run = RunResult(
        task_id="ws-001",
        condition_id="local:qwen3-8b",
        run_index=0,
        trajectory=trajectory_from_dict(
            {"turns": [{"type": "message", "role": "user", "content": "hi"}]}
        ),
        grade=GradeResult(
            grader_id="ast_tool_match",
            passed=False,
            score=0.0,
            evidence={"error": "x"},
            failure_reason="wrong_tool",
        ),
    )
    data = run_result_to_dict(run)

    assert data["task_id"] == "ws-001"
    assert data["grade"]["failure_reason"] == "wrong_tool"
    assert data["trajectory"]["turns"][0]["type"] == "message"


def test_grade_result_to_dict_keeps_none_failure_reason() -> None:
    grade = GradeResult(
        grader_id="output_match", passed=True, score=1.0, evidence={}
    )

    assert grade_result_to_dict(grade)["failure_reason"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/records/test_serialize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.records.serialize'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/records/serialize.py
"""Pure dict round-trips for records (JSONL persistence + golden suite)."""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolOutcome,
    ToolResultTurn,
    ToolSuccess,
    Turn,
)


def outcome_to_dict(outcome: ToolOutcome) -> dict[str, Any]:
    if isinstance(outcome, ToolSuccess):
        return {"type": "success", "result": outcome.result}
    return {"type": "failure", "error": outcome.error}


def outcome_from_dict(data: Mapping[str, Any]) -> ToolOutcome:
    if data["type"] == "success":
        return ToolSuccess(result=data["result"])
    if data["type"] == "failure":
        return ToolFailure(error=data["error"])
    raise ValueError(f"unknown outcome type: {data['type']!r}")


def turn_to_dict(turn: Turn) -> dict[str, Any]:
    if isinstance(turn, MessageTurn):
        return {"type": "message", "role": turn.role, "content": turn.content}
    if isinstance(turn, ToolCallTurn):
        return {
            "type": "tool_call",
            "content": turn.content,
            "tool_calls": [
                {"call_id": c.call_id, "name": c.name, "arguments": dict(c.arguments)}
                for c in turn.tool_calls
            ],
        }
    if isinstance(turn, ToolResultTurn):
        return {
            "type": "tool_result",
            "call_id": turn.call_id,
            "outcome": outcome_to_dict(turn.outcome),
        }
    raise ValueError(f"unknown turn: {turn!r}")


def turn_from_dict(data: Mapping[str, Any]) -> Turn:
    kind = data["type"]
    if kind == "message":
        return MessageTurn(role=data["role"], content=data["content"])
    if kind == "tool_call":
        calls = tuple(
            ToolCall(call_id=c["call_id"], name=c["name"], arguments=c["arguments"])
            for c in data["tool_calls"]
        )
        return ToolCallTurn(tool_calls=calls, content=data.get("content"))
    if kind == "tool_result":
        return ToolResultTurn(
            call_id=data["call_id"], outcome=outcome_from_dict(data["outcome"])
        )
    raise ValueError(f"unknown turn type: {kind!r}")


def trajectory_to_dict(trajectory: Trajectory) -> dict[str, Any]:
    parse_failure = trajectory.parse_failure
    return {
        "turns": [turn_to_dict(t) for t in trajectory.turns],
        "usage": {
            "prompt_tokens": trajectory.usage.prompt_tokens,
            "completion_tokens": trajectory.usage.completion_tokens,
            "latency_s": trajectory.usage.latency_s,
        },
        "run_index": trajectory.run_index,
        "stop_reason": trajectory.stop_reason,
        "parse_failure": (
            None
            if parse_failure is None
            else {"raw": parse_failure.raw, "error": parse_failure.error}
        ),
    }


def trajectory_from_dict(data: Mapping[str, Any]) -> Trajectory:
    usage = data.get("usage", {})
    parse_failure = data.get("parse_failure")
    return Trajectory(
        turns=tuple(turn_from_dict(t) for t in data["turns"]),
        usage=Usage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_s=usage.get("latency_s", 0.0),
        ),
        run_index=data.get("run_index", 0),
        stop_reason=data.get("stop_reason", "completed"),
        parse_failure=(
            None
            if parse_failure is None
            else ParseFailure(raw=parse_failure["raw"], error=parse_failure["error"])
        ),
    )


def grade_result_to_dict(grade: GradeResult) -> dict[str, Any]:
    return {
        "grader_id": grade.grader_id,
        "passed": grade.passed,
        "score": grade.score,
        "evidence": dict(grade.evidence),
        "failure_reason": grade.failure_reason,
    }


def run_result_to_dict(run: RunResult) -> dict[str, Any]:
    return {
        "task_id": run.task_id,
        "condition_id": run.condition_id,
        "run_index": run.run_index,
        "trajectory": trajectory_to_dict(run.trajectory),
        "grade": grade_result_to_dict(run.grade),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/records/test_serialize.py -v`
Expected: 5 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/records tests/records
git commit -m "feat: add dict serialization round-trip for records"
```

---

### Task 5: Task schema and pure parser

**Files:**
- Create: `src/agent_eval_lab/tasks/__init__.py`
- Create: `src/agent_eval_lab/tasks/schema.py`
- Create: `src/agent_eval_lab/tasks/parse.py`
- Test: `tests/tasks/test_parse.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tasks/test_parse.py
import pytest

from agent_eval_lab.tasks.parse import parse_task, verification_from_dict
from agent_eval_lab.tasks.schema import OutputMatchSpec, ToolCallMatchSpec

TASK_DATA = {
    "id": "ws-001",
    "capability": "tool_selection",
    "input": {
        "messages": [
            {"type": "message", "role": "system", "content": "You are a support agent."},
            {"type": "message", "role": "user", "content": "Search the docs for 'refund policy'."},
        ],
        "available_tools": ["search_docs", "create_ticket", "update_ticket"],
    },
    "verification": {
        "type": "tool_call_match",
        "expected_tool_calls": [
            {"name": "search_docs", "arguments": {"query": "refund policy"}}
        ],
        "match": "exact_sequence",
    },
    "metadata": {
        "split": "dev",
        "version": "1",
        "provenance": "hand_written",
        "world_template_id": "workspace-v1",
    },
    "initial_state": {"docs": {}, "tickets": {}},
}


def test_parse_task_builds_full_record() -> None:
    task = parse_task(TASK_DATA)

    assert task.id == "ws-001"
    assert task.capability == "tool_selection"
    assert len(task.input.messages) == 2
    assert task.input.available_tools == ("search_docs", "create_ticket", "update_ticket")
    assert isinstance(task.verification, ToolCallMatchSpec)
    assert task.verification.expected_tool_calls[0].name == "search_docs"
    assert task.metadata.split == "dev"
    assert task.metadata.world_template_id == "workspace-v1"
    assert task.metadata.difficulty_knob is None
    assert task.initial_state == {"docs": {}, "tickets": {}}


def test_parse_task_rejects_bad_split() -> None:
    bad = {**TASK_DATA, "metadata": {**TASK_DATA["metadata"], "split": "test"}}

    with pytest.raises(ValueError, match="split"):
        parse_task(bad)


def test_parse_task_rejects_non_message_input_turns() -> None:
    bad_input = {
        **TASK_DATA["input"],
        "messages": [{"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": None}}],
    }

    with pytest.raises(ValueError, match="message"):
        parse_task({**TASK_DATA, "input": bad_input})


def test_verification_from_dict_parses_output_match() -> None:
    spec = verification_from_dict(
        {"type": "output_match", "expected_output": "Done.", "normalizer": None}
    )

    assert isinstance(spec, OutputMatchSpec)
    assert spec.expected_output == "Done."
    assert spec.normalizer is None


def test_verification_from_dict_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown verification type"):
        verification_from_dict({"type": "final_state", "constraints": []})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tasks/test_parse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.tasks'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/tasks/__init__.py
"""Task schema, validation (pure), and dataset loading (edge)."""
```

```python
# src/agent_eval_lab/tasks/schema.py
"""Task records and the Weeks 1-2 VerificationSpec subset (spec §4.3-§4.4)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.turns import MessageTurn


@dataclass(frozen=True, kw_only=True)
class ExpectedToolCall:
    """Spec-time tool call; call_id is unknowable when authoring."""

    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, kw_only=True)
class OutputMatchSpec:
    type: Literal["output_match"] = "output_match"
    expected_output: str
    normalizer: str | None = None


@dataclass(frozen=True, kw_only=True)
class ToolCallMatchSpec:
    type: Literal["tool_call_match"] = "tool_call_match"
    expected_tool_calls: tuple[ExpectedToolCall, ...]
    match: Literal["exact_sequence", "multiset"] = "exact_sequence"


# Weeks 1-2 locked subset; FinalStateSpec/TrajectorySpec/AllOf/LlmJudgeSpec
# extend this union in Weeks 3-4 without breaking serialization.
VerificationSpec = OutputMatchSpec | ToolCallMatchSpec


@dataclass(frozen=True, kw_only=True)
class TaskInput:
    messages: tuple[MessageTurn, ...]
    available_tools: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class TaskMetadata:
    split: Literal["dev", "held_out"]
    version: str
    provenance: str
    world_template_id: str | None = None
    difficulty_knob: str | None = None


@dataclass(frozen=True, kw_only=True)
class Task:
    id: str
    capability: str
    input: TaskInput
    verification: VerificationSpec
    metadata: TaskMetadata
    initial_state: Mapping[str, Any] | None = None
```

```python
# src/agent_eval_lab/tasks/parse.py
"""Pure parsing: JSON-shaped dicts -> Task records."""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.serialize import turn_from_dict
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import (
    ExpectedToolCall,
    OutputMatchSpec,
    Task,
    TaskInput,
    TaskMetadata,
    ToolCallMatchSpec,
    VerificationSpec,
)

_SPLITS = ("dev", "held_out")
_MATCH_MODES = ("exact_sequence", "multiset")


def verification_from_dict(data: Mapping[str, Any]) -> VerificationSpec:
    kind = data["type"]
    if kind == "output_match":
        return OutputMatchSpec(
            expected_output=data["expected_output"],
            normalizer=data.get("normalizer"),
        )
    if kind == "tool_call_match":
        match = data.get("match", "exact_sequence")
        if match not in _MATCH_MODES:
            raise ValueError(f"unknown match mode: {match!r}")
        return ToolCallMatchSpec(
            expected_tool_calls=tuple(
                ExpectedToolCall(name=c["name"], arguments=c["arguments"])
                for c in data["expected_tool_calls"]
            ),
            match=match,
        )
    raise ValueError(f"unknown verification type: {kind!r}")


def _parse_messages(raw: list[Mapping[str, Any]]) -> tuple[MessageTurn, ...]:
    messages = tuple(turn_from_dict(m) for m in raw)
    for turn in messages:
        if not isinstance(turn, MessageTurn):
            raise ValueError(f"task input turns must be message turns, got {turn.type!r}")
    return messages


def _parse_metadata(data: Mapping[str, Any]) -> TaskMetadata:
    if data["split"] not in _SPLITS:
        raise ValueError(f"unknown split: {data['split']!r}")
    return TaskMetadata(
        split=data["split"],
        version=data["version"],
        provenance=data["provenance"],
        world_template_id=data.get("world_template_id"),
        difficulty_knob=data.get("difficulty_knob"),
    )


def parse_task(data: Mapping[str, Any]) -> Task:
    input_data = data["input"]
    return Task(
        id=data["id"],
        capability=data["capability"],
        input=TaskInput(
            messages=_parse_messages(input_data["messages"]),
            available_tools=tuple(input_data["available_tools"]),
        ),
        verification=verification_from_dict(data["verification"]),
        metadata=_parse_metadata(data["metadata"]),
        initial_state=data.get("initial_state"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tasks/test_parse.py -v`
Expected: 5 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/tasks tests/tasks
git commit -m "feat: add task schema and pure parser for the locked VerificationSpec subset"
```

---

### Task 6: Dataset loader (edge)

**Files:**
- Create: `src/agent_eval_lab/tasks/loader.py`
- Test: `tests/tasks/test_loader.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tasks/test_loader.py
import json
from pathlib import Path

import pytest

from agent_eval_lab.tasks.loader import load_tasks

LINE = {
    "id": "ws-001",
    "capability": "tool_selection",
    "input": {
        "messages": [{"type": "message", "role": "user", "content": "hi"}],
        "available_tools": ["search_docs"],
    },
    "verification": {
        "type": "tool_call_match",
        "expected_tool_calls": [{"name": "search_docs", "arguments": {"query": "x"}}],
        "match": "exact_sequence",
    },
    "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
}


def _write(path: Path, lines: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    return path


def test_load_tasks_reads_jsonl(tmp_path: Path) -> None:
    second = {**LINE, "id": "ws-002"}
    dataset = _write(tmp_path / "tasks.jsonl", [LINE, second])

    tasks = load_tasks(dataset)

    assert [t.id for t in tasks] == ["ws-001", "ws-002"]


def test_load_tasks_skips_blank_lines(tmp_path: Path) -> None:
    dataset = tmp_path / "tasks.jsonl"
    dataset.write_text(json.dumps(LINE) + "\n\n")

    assert len(load_tasks(dataset)) == 1


def test_load_tasks_rejects_duplicate_ids(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "tasks.jsonl", [LINE, LINE])

    with pytest.raises(ValueError, match="duplicate task id"):
        load_tasks(dataset)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tasks/test_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.tasks.loader'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/tasks/loader.py
"""EDGE: read JSONL dataset files into Task records."""

import json
from pathlib import Path

from agent_eval_lab.tasks.parse import parse_task
from agent_eval_lab.tasks.schema import Task


def load_tasks(path: Path) -> tuple[Task, ...]:
    lines = path.read_text().splitlines()
    tasks = tuple(parse_task(json.loads(line)) for line in lines if line.strip())
    seen: set[str] = set()
    for task in tasks:
        if task.id in seen:
            raise ValueError(f"duplicate task id: {task.id!r}")
        seen.add(task.id)
    return tasks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tasks/test_loader.py -v`
Expected: 3 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/tasks tests/tasks
git commit -m "feat: add JSONL dataset loader edge"
```

---

### Task 7: Schema validation and the workspace world

**Files:**
- Create: `src/agent_eval_lab/tools/__init__.py`
- Create: `src/agent_eval_lab/tools/validation.py`
- Create: `src/agent_eval_lab/tools/workspace.py`
- Test: `tests/tools/test_validation.py`
- Test: `tests/tools/test_workspace.py`
- Test: `tests/tools/test_workspace_properties.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tools/test_validation.py
from agent_eval_lab.tools.validation import validate_args

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["title", "priority"],
    "additionalProperties": False,
}


def test_valid_args_return_none() -> None:
    assert validate_args(SCHEMA, {"title": "x", "priority": "low"}) is None


def test_missing_required_field_is_reported() -> None:
    error = validate_args(SCHEMA, {"title": "x"})

    assert error is not None
    assert "priority" in error


def test_wrong_type_is_never_coerced() -> None:
    error = validate_args(SCHEMA, {"title": "x", "priority": 1})

    assert error is not None
    assert "priority" in error


def test_enum_violation_is_reported() -> None:
    assert validate_args(SCHEMA, {"title": "x", "priority": "urgent"}) is not None


def test_additional_properties_are_rejected() -> None:
    error = validate_args(SCHEMA, {"title": "x", "priority": "low", "extra": 1})

    assert error is not None
```

```python
# tests/tools/test_workspace.py
from agent_eval_lab.records.turns import ToolFailure, ToolSuccess
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS, apply

STATE = {
    "docs": {
        "doc-1": {"title": "Refund policy", "body": "Refunds take 5 business days."},
        "doc-2": {"title": "Onboarding guide", "body": "Verify email to activate."},
    },
    "tickets": {"T-7": {"title": "Login broken", "priority": "high", "status": "open"}},
}


def test_registry_exposes_three_tools_with_schemas() -> None:
    assert set(WORKSPACE_TOOLS) == {"search_docs", "create_ticket", "update_ticket"}
    for tool in WORKSPACE_TOOLS.values():
        assert tool.parameters["type"] == "object"
        assert tool.description


def test_search_docs_matches_title_and_body_case_insensitive() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="search_docs",
        arguments={"query": "refund"},
        state=STATE,
    )

    assert new_state == STATE
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"doc_ids": ["doc-1"]}


def test_create_ticket_assigns_next_id_and_does_not_mutate_input() -> None:
    before = {"docs": {}, "tickets": {"T-7": {"title": "a", "priority": "low", "status": "open"}}}
    snapshot = {"docs": {}, "tickets": {"T-7": {"title": "a", "priority": "low", "status": "open"}}}

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="create_ticket",
        arguments={"title": "Printer offline", "priority": "low"},
        state=before,
    )

    assert before == snapshot
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result == {"ticket_id": "T-8"}
    assert new_state["tickets"]["T-8"] == {
        "title": "Printer offline",
        "priority": "low",
        "status": "open",
    }


def test_update_ticket_changes_status() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="update_ticket",
        arguments={"ticket_id": "T-7", "status": "closed"},
        state=STATE,
    )

    assert isinstance(outcome, ToolSuccess)
    assert new_state["tickets"]["T-7"]["status"] == "closed"
    assert STATE["tickets"]["T-7"]["status"] == "open"


def test_update_unknown_ticket_is_a_business_failure() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="update_ticket",
        arguments={"ticket_id": "T-99", "status": "closed"},
        state=STATE,
    )

    assert new_state == STATE
    assert isinstance(outcome, ToolFailure)
    assert "T-99" in outcome.error


def test_schema_invalid_args_fail_like_a_real_api() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="create_ticket",
        arguments={"title": "x", "priority": "urgent"},
        state=STATE,
    )

    assert new_state == STATE
    assert isinstance(outcome, ToolFailure)
    assert outcome.error.startswith("schema violation")


def test_unknown_tool_fails() -> None:
    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS, name="send_email", arguments={}, state=STATE
    )

    assert new_state == STATE
    assert isinstance(outcome, ToolFailure)
    assert "unknown tool" in outcome.error
```

```python
# tests/tools/test_workspace_properties.py
from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.records.turns import ToolFailure
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS, apply

invalid_priority = st.text(max_size=20).filter(
    lambda s: s not in {"low", "medium", "high"}
)


@given(priority=invalid_priority)
def test_schema_invalid_priority_never_succeeds(priority: str) -> None:
    state = {"docs": {}, "tickets": {}}

    new_state, outcome = apply(
        registry=WORKSPACE_TOOLS,
        name="create_ticket",
        arguments={"title": "x", "priority": priority},
        state=state,
    )

    assert isinstance(outcome, ToolFailure)
    assert new_state == state
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.tools'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/tools/__init__.py
"""Synthetic tool-world: JSON schemas + pure implementations over explicit state."""
```

```python
# src/agent_eval_lab/tools/validation.py
"""Shared JSON-Schema argument validation (the world and graders agree)."""

from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator


def validate_args(schema: Mapping[str, Any], args: Mapping[str, Any]) -> str | None:
    """Return None when args satisfy schema, else a human-readable error."""
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(dict(args)), key=lambda e: list(e.absolute_path))
    if not errors:
        return None
    first = errors[0]
    path = ".".join(str(p) for p in first.absolute_path) or "<root>"
    return f"{path}: {first.message}"
```

```python
# src/agent_eval_lab/tools/workspace.py
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
    return new_state, ToolSuccess(result={"ticket_id": ticket_id, "status": args["status"]})


_IMPLS: Mapping[str, Callable[[Mapping[str, Any], State], tuple[State, ToolOutcome]]] = {
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tools -v`
Expected: 13 passed (5 validation + 7 workspace + 1 property).

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/tools tests/tools
git commit -m "feat: add schema-validated workspace tool-world"
```

---

### Task 8: Canonicalization

**Files:**
- Create: `src/agent_eval_lab/graders/canonical.py`
- Test: `tests/graders/test_canonical.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/graders/test_canonical.py
from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.graders.canonical import canonicalize


def test_sorts_mapping_keys_recursively_and_freezes_sequences() -> None:
    value = {"b": 1, "a": [{"d": 1, "c": 2}]}

    result = canonicalize(value)

    assert result == {"a": ({"c": 2, "d": 1},), "b": 1}
    assert list(result) == ["a", "b"]
    assert isinstance(result["a"], tuple)


def test_values_are_never_coerced() -> None:
    assert canonicalize({"n": "1"}) == {"n": "1"}
    assert canonicalize({"n": 1}) == {"n": 1}
    assert canonicalize({"n": "1"}) != canonicalize({"n": 1})


json_values = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(st.text(max_size=8), children, max_size=4),
    max_leaves=16,
)


@given(value=json_values)
def test_canonicalize_is_idempotent(value) -> None:
    once = canonicalize(value)

    assert canonicalize(once) == once
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graders/test_canonical.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.graders.canonical'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/graders/canonical.py
"""Value-preserving canonicalization for comparing and serializing arguments.

Only proven-equivalent forms are normalized (mapping key order; sequence type).
Type coercion is NEVER performed here — `"1"` and `1` stay distinct; the
schema validator decides whether a value is legal.
"""

from collections.abc import Mapping
from typing import Any


def canonicalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return tuple(canonicalize(item) for item in value)
    return value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graders/test_canonical.py -v`
Expected: 3 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/graders tests/graders
git commit -m "feat: add value-preserving canonicalization with idempotency property test"
```

---

### Task 9: AST tool-call grader

**Files:**
- Create: `src/agent_eval_lab/graders/tool_call.py`
- Test: `tests/graders/test_tool_call.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/graders/test_tool_call.py
from agent_eval_lab.graders.tool_call import grade_tool_call_match
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.tasks.schema import ExpectedToolCall, ToolCallMatchSpec
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

SEARCH = ExpectedToolCall(name="search_docs", arguments={"query": "refund policy"})
CREATE = ExpectedToolCall(
    name="create_ticket", arguments={"title": "Printer offline", "priority": "low"}
)


def _spec(*expected: ExpectedToolCall, match: str = "exact_sequence") -> ToolCallMatchSpec:
    return ToolCallMatchSpec(expected_tool_calls=expected, match=match)


def _call(name: str, arguments: dict, call_id: str = "c1") -> ToolCall:
    return ToolCall(call_id=call_id, name=name, arguments=arguments)


def _trajectory(*calls: ToolCall, parse_failure: ParseFailure | None = None) -> Trajectory:
    turns = (ToolCallTurn(tool_calls=calls),) if calls else ()
    return Trajectory(
        turns=turns,
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="parse_failure" if parse_failure else "completed",
        parse_failure=parse_failure,
    )


def _grade(spec: ToolCallMatchSpec, trajectory: Trajectory):
    return grade_tool_call_match(
        spec=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )


def test_exact_sequence_pass_ignores_key_order() -> None:
    observed = _call("create_ticket", {"priority": "low", "title": "Printer offline"})

    result = _grade(_spec(CREATE), _trajectory(observed))

    assert result.passed is True
    assert result.failure_reason is None
    assert result.grader_id == "ast_tool_match"


def test_parse_failure_grades_as_malformed_call() -> None:
    failure = ParseFailure(raw='{"query": ', error="arguments not valid JSON")

    result = _grade(_spec(SEARCH), _trajectory(parse_failure=failure))

    assert result.passed is False
    assert result.failure_reason == "malformed_call"
    assert result.evidence["error"] == "arguments not valid JSON"


def test_schema_invalid_args_grade_as_schema_violation_never_repaired() -> None:
    observed = _call("create_ticket", {"title": "x", "priority": 1})

    result = _grade(_spec(CREATE), _trajectory(observed))

    assert result.failure_reason == "schema_violation"


def test_unknown_tool_name_grades_as_wrong_tool() -> None:
    observed = _call("send_email", {"to": "a@b.c"})

    result = _grade(_spec(SEARCH), _trajectory(observed))

    assert result.failure_reason == "wrong_tool"


def test_same_position_name_mismatch_is_wrong_tool() -> None:
    observed = _call("create_ticket", {"title": "x", "priority": "low"})

    result = _grade(_spec(SEARCH), _trajectory(observed))

    assert result.failure_reason == "wrong_tool"


def test_same_tool_different_args_is_wrong_args() -> None:
    observed = _call("search_docs", {"query": "billing"})

    result = _grade(_spec(SEARCH), _trajectory(observed))

    assert result.failure_reason == "wrong_args"
    assert result.evidence["position"] == 0


def test_fewer_calls_than_expected_is_missing_call() -> None:
    result = _grade(_spec(SEARCH, CREATE), _trajectory(_call("search_docs", {"query": "refund policy"})))

    assert result.failure_reason == "missing_call"


def test_more_calls_than_expected_is_extra_call() -> None:
    observed = (
        _call("search_docs", {"query": "refund policy"}, "c1"),
        _call("create_ticket", {"title": "x", "priority": "low"}, "c2"),
    )

    result = _grade(_spec(SEARCH), _trajectory(*observed))

    assert result.failure_reason == "extra_call"


def test_swapped_order_is_order_mismatch_in_exact_sequence() -> None:
    observed = (
        _call("create_ticket", {"title": "Printer offline", "priority": "low"}, "c1"),
        _call("search_docs", {"query": "refund policy"}, "c2"),
    )

    result = _grade(_spec(SEARCH, CREATE), _trajectory(*observed))

    assert result.failure_reason == "order_mismatch"


def test_swapped_order_passes_in_multiset_mode() -> None:
    observed = (
        _call("create_ticket", {"title": "Printer offline", "priority": "low"}, "c1"),
        _call("search_docs", {"query": "refund policy"}, "c2"),
    )

    result = _grade(_spec(SEARCH, CREATE, match="multiset"), _trajectory(*observed))

    assert result.passed is True


def test_multiset_same_names_different_args_is_wrong_args() -> None:
    observed = _call("search_docs", {"query": "billing"})

    result = _grade(_spec(SEARCH, match="multiset"), _trajectory(observed))

    assert result.failure_reason == "wrong_args"


def test_no_calls_expected_and_none_observed_passes() -> None:
    trajectory = Trajectory(
        turns=(MessageTurn(role="assistant", content="No action needed."),),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
    )

    result = _grade(_spec(), trajectory)

    assert result.passed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graders/test_tool_call.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.graders.tool_call'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/graders/tool_call.py
"""AST tool-call grading: schema-first pipeline, never repairs (spec §6).

Pipeline: parse failure -> malformed_call; raw args vs schema ->
schema_violation; canonicalize proven-equivalent forms; structural compare.
Precedence: malformed_call > schema_violation > missing_call/extra_call >
order_mismatch > wrong_tool > wrong_args.
"""

import json
from collections import Counter
from collections.abc import Mapping
from typing import Any

from agent_eval_lab.graders.canonical import canonicalize
from agent_eval_lab.records.grade import FailureCategory, GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import ToolCallTurn
from agent_eval_lab.tasks.schema import ToolCallMatchSpec
from agent_eval_lab.tools.validation import validate_args
from agent_eval_lab.tools.workspace import ToolDef

GRADER_ID = "ast_tool_match"

Pair = tuple[str, Any]


def _fail(reason: FailureCategory, evidence: Mapping[str, Any]) -> GradeResult:
    return GradeResult(
        grader_id=GRADER_ID,
        passed=False,
        score=0.0,
        evidence=evidence,
        failure_reason=reason,
    )


def _passed(evidence: Mapping[str, Any]) -> GradeResult:
    return GradeResult(
        grader_id=GRADER_ID, passed=True, score=1.0, evidence=evidence, failure_reason=None
    )


def _pairs(calls) -> tuple[Pair, ...]:
    return tuple((call.name, canonicalize(call.arguments)) for call in calls)


def _multiset(pairs: tuple[Pair, ...]) -> Counter:
    return Counter((name, json.dumps(args, sort_keys=True)) for name, args in pairs)


def grade_tool_call_match(
    *,
    spec: ToolCallMatchSpec,
    trajectory: Trajectory,
    registry: Mapping[str, ToolDef],
) -> GradeResult:
    if trajectory.parse_failure is not None:
        return _fail(
            "malformed_call",
            {"raw": trajectory.parse_failure.raw, "error": trajectory.parse_failure.error},
        )
    observed = tuple(
        call
        for turn in trajectory.turns
        if isinstance(turn, ToolCallTurn)
        for call in turn.tool_calls
    )
    expected_pairs = _pairs(spec.expected_tool_calls)
    observed_pairs = _pairs(observed)
    evidence = {"expected": expected_pairs, "observed": observed_pairs}
    for call in observed:
        tool = registry.get(call.name)
        if tool is None:
            return _fail("wrong_tool", {**evidence, "unknown_tool": call.name})
        error = validate_args(tool.parameters, call.arguments)
        if error is not None:
            return _fail(
                "schema_violation", {**evidence, "call_id": call.call_id, "error": error}
            )
    if spec.match == "multiset":
        return _grade_multiset(expected_pairs, observed_pairs, evidence)
    return _grade_sequence(expected_pairs, observed_pairs, evidence)


def _grade_sequence(
    expected: tuple[Pair, ...],
    observed: tuple[Pair, ...],
    evidence: Mapping[str, Any],
) -> GradeResult:
    if observed == expected:
        return _passed(evidence)
    if len(observed) < len(expected):
        return _fail("missing_call", evidence)
    if len(observed) > len(expected):
        return _fail("extra_call", evidence)
    if _multiset(observed) == _multiset(expected):
        return _fail("order_mismatch", evidence)
    position = next(
        i for i, (exp, obs) in enumerate(zip(expected, observed)) if exp != obs
    )
    expected_name = expected[position][0]
    observed_name = observed[position][0]
    reason = "wrong_tool" if expected_name != observed_name else "wrong_args"
    return _fail(reason, {**evidence, "position": position})


def _grade_multiset(
    expected: tuple[Pair, ...],
    observed: tuple[Pair, ...],
    evidence: Mapping[str, Any],
) -> GradeResult:
    if _multiset(observed) == _multiset(expected):
        return _passed(evidence)
    if len(observed) < len(expected):
        return _fail("missing_call", evidence)
    if len(observed) > len(expected):
        return _fail("extra_call", evidence)
    expected_names = Counter(name for name, _ in expected)
    observed_names = Counter(name for name, _ in observed)
    reason = "wrong_args" if expected_names == observed_names else "wrong_tool"
    return _fail(reason, evidence)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graders/test_tool_call.py -v`
Expected: 12 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/graders tests/graders
git commit -m "feat: add schema-first AST tool-call grader with failure taxonomy"
```

---

### Task 10: Verification dispatch

**Files:**
- Create: `src/agent_eval_lab/graders/dispatch.py`
- Test: `tests/graders/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/graders/test_dispatch.py
import pytest

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.tasks.schema import (
    ExpectedToolCall,
    OutputMatchSpec,
    ToolCallMatchSpec,
)
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS


def _trajectory(*turns) -> Trajectory:
    return Trajectory(
        turns=turns,
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
    )


def test_dispatches_output_match_to_final_assistant_message() -> None:
    trajectory = _trajectory(
        MessageTurn(role="user", content="Say done."),
        MessageTurn(role="assistant", content="Done."),
    )
    spec = OutputMatchSpec(expected_output="Done.")

    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )

    assert result.passed is True
    assert result.grader_id == "output_match"


def test_output_match_fails_when_no_assistant_message() -> None:
    trajectory = _trajectory(MessageTurn(role="user", content="Say done."))
    spec = OutputMatchSpec(expected_output="Done.")

    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )

    assert result.passed is False
    assert result.evidence == {"error": "no assistant message in trajectory"}


def test_output_match_rejects_unsupported_normalizer() -> None:
    trajectory = _trajectory(MessageTurn(role="assistant", content="Done."))
    spec = OutputMatchSpec(expected_output="Done.", normalizer="lowercase")

    with pytest.raises(ValueError, match="unsupported normalizer"):
        grade_trajectory(
            verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
        )


def test_dispatches_tool_call_match() -> None:
    trajectory = _trajectory(
        ToolCallTurn(
            tool_calls=(
                ToolCall(call_id="c1", name="search_docs", arguments={"query": "x"}),
            )
        )
    )
    spec = ToolCallMatchSpec(
        expected_tool_calls=(
            ExpectedToolCall(name="search_docs", arguments={"query": "x"}),
        )
    )

    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )

    assert result.passed is True
    assert result.grader_id == "ast_tool_match"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graders/test_dispatch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.graders.dispatch'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/graders/dispatch.py
"""Pure dispatch from VerificationSpec variants to their graders."""

from collections.abc import Mapping

from agent_eval_lab.graders.exact_match import grade_exact_match
from agent_eval_lab.graders.tool_call import grade_tool_call_match
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import (
    OutputMatchSpec,
    ToolCallMatchSpec,
    VerificationSpec,
)
from agent_eval_lab.tools.workspace import ToolDef


def grade_output_match(*, spec: OutputMatchSpec, trajectory: Trajectory) -> GradeResult:
    if spec.normalizer is not None:
        raise ValueError(f"unsupported normalizer: {spec.normalizer!r}")
    final = next(
        (
            turn
            for turn in reversed(trajectory.turns)
            if isinstance(turn, MessageTurn) and turn.role == "assistant"
        ),
        None,
    )
    if final is None:
        return GradeResult(
            grader_id="output_match",
            passed=False,
            score=0.0,
            evidence={"error": "no assistant message in trajectory"},
            failure_reason=None,
        )
    return grade_exact_match(expected=spec.expected_output, actual=final.content)


def grade_trajectory(
    *,
    verification: VerificationSpec,
    trajectory: Trajectory,
    registry: Mapping[str, ToolDef],
) -> GradeResult:
    if isinstance(verification, OutputMatchSpec):
        return grade_output_match(spec=verification, trajectory=trajectory)
    if isinstance(verification, ToolCallMatchSpec):
        return grade_tool_call_match(
            spec=verification, trajectory=trajectory, registry=registry
        )
    raise ValueError(f"unsupported verification spec: {verification!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/graders/test_dispatch.py -v`
Expected: 4 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/graders tests/graders
git commit -m "feat: add verification dispatch for the locked spec subset"
```

---

### Task 11: Golden conformance suite

Hand-verified trajectories with known-correct grades — the correctness oracle for the harness, in CI (spec §8). The test is written first (fails: no golden files), then the 11 cases are added.

**Files:**
- Create: `tests/test_golden_conformance.py`
- Create: `tests/golden/01_pass_exact_sequence.json` … `tests/golden/11_output_match_pass.json`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_golden_conformance.py
"""Golden conformance suite: hand-verified trajectories with known grades.

Each JSON case carries a verification spec, a trajectory, and the
hand-verified expected grade. The harness must reproduce the oracle.
"""

import json
from pathlib import Path

import pytest

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.serialize import trajectory_from_dict
from agent_eval_lab.tasks.parse import verification_from_dict
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_CASES = sorted(GOLDEN_DIR.glob("*.json"))


def test_golden_suite_is_present() -> None:
    assert len(GOLDEN_CASES) == 11


@pytest.mark.parametrize("path", GOLDEN_CASES, ids=lambda p: p.stem)
def test_golden_conformance(path: Path) -> None:
    case = json.loads(path.read_text())

    grade = grade_trajectory(
        verification=verification_from_dict(case["verification"]),
        trajectory=trajectory_from_dict(case["trajectory"]),
        registry=WORKSPACE_TOOLS,
    )

    assert grade.passed == case["expected"]["passed"], case["name"]
    assert grade.failure_reason == case["expected"]["failure_reason"], case["name"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_golden_conformance.py -v`
Expected: FAIL — `test_golden_suite_is_present` asserts 11, finds 0.

- [ ] **Step 3: Add the 11 golden cases**

`tests/golden/01_pass_exact_sequence.json`:

```json
{
  "name": "single matching call passes in exact_sequence mode",
  "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "search_docs", "arguments": {"query": "refund policy"}}], "match": "exact_sequence"},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "Search the docs for 'refund policy'."},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "search_docs", "arguments": {"query": "refund policy"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"doc_ids": ["doc-1"]}}},
    {"type": "message", "role": "assistant", "content": "Found doc-1."}
  ]},
  "expected": {"passed": true, "failure_reason": null}
}
```

`tests/golden/02_malformed_call.json`:

```json
{
  "name": "unparseable tool-call arguments grade as malformed_call",
  "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "search_docs", "arguments": {"query": "refund policy"}}], "match": "exact_sequence"},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "Search the docs for 'refund policy'."}
  ], "stop_reason": "parse_failure", "parse_failure": {"raw": "{\"query\": ", "error": "arguments not valid JSON"}},
  "expected": {"passed": false, "failure_reason": "malformed_call"}
}
```

`tests/golden/03_schema_violation_wrong_type.json`:

```json
{
  "name": "integer where the enum string is required is a schema_violation, never coerced",
  "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "create_ticket", "arguments": {"title": "Printer offline", "priority": "low"}}], "match": "exact_sequence"},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "Create a ticket titled 'Printer offline' with priority low."},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "create_ticket", "arguments": {"title": "Printer offline", "priority": 1}}]}
  ]},
  "expected": {"passed": false, "failure_reason": "schema_violation"}
}
```

`tests/golden/04_schema_violation_enum.json`:

```json
{
  "name": "value outside the enum is a schema_violation",
  "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "create_ticket", "arguments": {"title": "Printer offline", "priority": "low"}}], "match": "exact_sequence"},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "create_ticket", "arguments": {"title": "Printer offline", "priority": "urgent"}}]}
  ]},
  "expected": {"passed": false, "failure_reason": "schema_violation"}
}
```

`tests/golden/05_wrong_tool.json`:

```json
{
  "name": "schema-valid call to the wrong tool is wrong_tool",
  "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "search_docs", "arguments": {"query": "refund policy"}}], "match": "exact_sequence"},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "create_ticket", "arguments": {"title": "Refund policy", "priority": "low"}}]}
  ]},
  "expected": {"passed": false, "failure_reason": "wrong_tool"}
}
```

`tests/golden/06_wrong_args.json`:

```json
{
  "name": "right tool with wrong argument value is wrong_args",
  "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "search_docs", "arguments": {"query": "refund policy"}}], "match": "exact_sequence"},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "search_docs", "arguments": {"query": "billing"}}]}
  ]},
  "expected": {"passed": false, "failure_reason": "wrong_args"}
}
```

`tests/golden/07_missing_call.json`:

```json
{
  "name": "stopping after the first of two expected calls is missing_call",
  "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "create_ticket", "arguments": {"title": "Data export failing", "priority": "high"}}, {"name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}}], "match": "exact_sequence"},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "create_ticket", "arguments": {"title": "Data export failing", "priority": "high"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"ticket_id": "T-1"}}},
    {"type": "message", "role": "assistant", "content": "Created T-1."}
  ]},
  "expected": {"passed": false, "failure_reason": "missing_call"}
}
```

`tests/golden/08_extra_call.json`:

```json
{
  "name": "an unrequested extra call is extra_call",
  "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "search_docs", "arguments": {"query": "refund policy"}}], "match": "exact_sequence"},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "search_docs", "arguments": {"query": "refund policy"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"doc_ids": ["doc-1"]}}},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c2", "name": "create_ticket", "arguments": {"title": "Refund question", "priority": "low"}}]}
  ]},
  "expected": {"passed": false, "failure_reason": "extra_call"}
}
```

`tests/golden/09_order_mismatch.json`:

```json
{
  "name": "same calls in the wrong order are order_mismatch in exact_sequence mode",
  "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "search_docs", "arguments": {"query": "refund policy"}}, {"name": "create_ticket", "arguments": {"title": "Refund question", "priority": "low"}}], "match": "exact_sequence"},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "create_ticket", "arguments": {"title": "Refund question", "priority": "low"}}, {"call_id": "c2", "name": "search_docs", "arguments": {"query": "refund policy"}}]}
  ]},
  "expected": {"passed": false, "failure_reason": "order_mismatch"}
}
```

`tests/golden/10_multiset_pass.json`:

```json
{
  "name": "same calls in any order pass in multiset mode",
  "verification": {"type": "tool_call_match", "expected_tool_calls": [{"name": "search_docs", "arguments": {"query": "refund policy"}}, {"name": "create_ticket", "arguments": {"title": "Refund question", "priority": "low"}}], "match": "multiset"},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "create_ticket", "arguments": {"title": "Refund question", "priority": "low"}}, {"call_id": "c2", "name": "search_docs", "arguments": {"query": "refund policy"}}]}
  ]},
  "expected": {"passed": true, "failure_reason": null}
}
```

`tests/golden/11_output_match_pass.json`:

```json
{
  "name": "output match grades the final assistant message",
  "verification": {"type": "output_match", "expected_output": "All done.", "normalizer": null},
  "trajectory": {"turns": [
    {"type": "message", "role": "user", "content": "Say 'All done.'"},
    {"type": "message", "role": "assistant", "content": "All done."}
  ]},
  "expected": {"passed": true, "failure_reason": null}
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_golden_conformance.py -v`
Expected: 12 passed (1 presence + 11 cases).

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add tests/golden tests/test_golden_conformance.py
git commit -m "test: add golden conformance suite (11 hand-verified cases)"
```

---

### Task 12: Provider config and payload parsing

**Files:**
- Create: `src/agent_eval_lab/runners/__init__.py`
- Create: `src/agent_eval_lab/runners/config.py`
- Create: `src/agent_eval_lab/runners/parse.py`
- Test: `tests/runners/test_config.py`
- Test: `tests/runners/test_parse.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/runners/test_config.py
from agent_eval_lab.runners.config import PROVIDERS, ProviderConfig


def test_registry_covers_the_design_provider_lineup() -> None:
    assert set(PROVIDERS) == {
        "deepseek", "glm", "minimax", "qwen", "openrouter", "local",
    }


def test_configs_hold_env_var_names_never_keys() -> None:
    for config in PROVIDERS.values():
        assert "key" not in config.api_key_env.lower() or config.api_key_env.isupper()
        assert config.base_url.startswith(("https://", "http://localhost"))


def test_local_provider_needs_no_key() -> None:
    assert PROVIDERS["local"].api_key_env == ""


def test_extra_headers_default_is_not_shared() -> None:
    first = ProviderConfig(id="a", base_url="https://x", api_key_env="X", model_id="m")
    second = ProviderConfig(id="b", base_url="https://y", api_key_env="Y", model_id="m")

    assert first.extra_headers == {}
    assert first.extra_headers is not second.extra_headers
```

```python
# tests/runners/test_parse.py
import json

from agent_eval_lab.records.trajectory import ParseFailure
from agent_eval_lab.records.turns import MessageTurn, ToolCallTurn
from agent_eval_lab.runners.parse import parse_assistant_payload


def test_plain_content_becomes_assistant_message() -> None:
    parsed = parse_assistant_payload({"role": "assistant", "content": "Done."})

    assert parsed == MessageTurn(role="assistant", content="Done.")


def test_tool_calls_are_parsed_with_arguments_decoded() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "search_docs",
                    "arguments": json.dumps({"query": "refund policy"}),
                },
            }
        ],
    }

    parsed = parse_assistant_payload(message)

    assert isinstance(parsed, ToolCallTurn)
    assert parsed.tool_calls[0].call_id == "call_1"
    assert parsed.tool_calls[0].arguments == {"query": "refund policy"}


def test_invalid_arguments_json_is_a_parse_failure() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "search_docs", "arguments": '{"query": '}}
        ],
    }

    parsed = parse_assistant_payload(message)

    assert isinstance(parsed, ParseFailure)
    assert "not valid JSON" in parsed.error


def test_non_object_arguments_is_a_parse_failure() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "search_docs", "arguments": "[1, 2]"}}
        ],
    }

    parsed = parse_assistant_payload(message)

    assert isinstance(parsed, ParseFailure)
    assert "JSON object" in parsed.error


def test_missing_function_name_is_a_parse_failure() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "c1", "type": "function", "function": {"arguments": "{}"}}],
    }

    parsed = parse_assistant_payload(message)

    assert isinstance(parsed, ParseFailure)
    assert "name" in parsed.error


def test_neither_content_nor_tool_calls_is_a_parse_failure() -> None:
    parsed = parse_assistant_payload({"role": "assistant", "content": None})

    assert isinstance(parsed, ParseFailure)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runners -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.runners'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/runners/__init__.py
"""IMPERATIVE SHELL: provider client, model<->tool loop, multi-run."""
```

```python
# src/agent_eval_lab/runners/config.py
"""Provider configuration (spec §3): one OpenAI-compatible client, many configs."""

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class ProviderConfig:
    id: str
    base_url: str
    api_key_env: str  # env var NAME holding the dedicated key (never the key)
    model_id: str
    extra_headers: Mapping[str, str] = field(default_factory=dict)
    adapter: str | None = None  # reserved: pure tool-call dialect normalizer


PROVIDERS: Mapping[str, ProviderConfig] = {
    "deepseek": ProviderConfig(
        id="deepseek",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        model_id="deepseek-v4",
    ),
    "glm": ProviderConfig(
        id="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key_env="ZHIPU_API_KEY",
        model_id="glm-5",
    ),
    "minimax": ProviderConfig(
        id="minimax",
        base_url="https://api.minimax.io/v1",
        api_key_env="MINIMAX_API_KEY",
        model_id="minimax-m2.1",
    ),
    "qwen": ProviderConfig(
        id="qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        model_id="qwen3-max",
    ),
    "openrouter": ProviderConfig(
        id="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        model_id="anthropic/claude-sonnet-4-6",
    ),
    "local": ProviderConfig(
        id="local",
        base_url="http://localhost:11434/v1",
        api_key_env="",
        model_id="qwen3-8b",
    ),
}
```

```python
# src/agent_eval_lab/runners/parse.py
"""Pure parsing of OpenAI-compatible assistant messages into Turn records.

Parse failures here are what the grader later reports as malformed_call.
"""

import json
from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.trajectory import ParseFailure
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn


def parse_assistant_payload(
    message: Mapping[str, Any],
) -> MessageTurn | ToolCallTurn | ParseFailure:
    tool_calls = message.get("tool_calls")
    if tool_calls:
        return _parse_tool_calls(tool_calls, message.get("content"))
    content = message.get("content")
    if content is None:
        return ParseFailure(
            raw=json.dumps(dict(message)),
            error="assistant message has neither content nor tool_calls",
        )
    return MessageTurn(role="assistant", content=content)


def _parse_tool_calls(
    raw_calls: list[Mapping[str, Any]], content: str | None
) -> ToolCallTurn | ParseFailure:
    calls: list[ToolCall] = []
    for index, raw in enumerate(raw_calls):
        function = raw.get("function", {})
        name = function.get("name")
        if not name:
            return ParseFailure(
                raw=json.dumps(dict(raw)), error="tool call missing function name"
            )
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            return ParseFailure(
                raw=raw_arguments, error=f"arguments not valid JSON: {exc}"
            )
        if not isinstance(arguments, dict):
            return ParseFailure(
                raw=raw_arguments, error="arguments must be a JSON object"
            )
        calls.append(
            ToolCall(
                call_id=raw.get("id", f"call-{index}"), name=name, arguments=arguments
            )
        )
    return ToolCallTurn(tool_calls=tuple(calls), content=content)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/runners -v`
Expected: 10 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/runners tests/runners
git commit -m "feat: add provider config registry and pure payload parsing"
```

---

### Task 13: Provider client (edge)

**Files:**
- Create: `src/agent_eval_lab/runners/client.py`
- Test: `tests/runners/test_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/runners/test_client.py
import httpx
import pytest

from agent_eval_lab.runners.client import chat_completion
from agent_eval_lab.runners.config import ProviderConfig

CONFIG = ProviderConfig(
    id="test",
    base_url="https://api.test.example",
    api_key_env="TEST_API_KEY",
    model_id="test-model",
)
OK_PAYLOAD = {
    "choices": [{"message": {"role": "assistant", "content": "Done."}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sends_bearer_key_from_env_and_returns_payload(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        return httpx.Response(200, json=OK_PAYLOAD)

    response = chat_completion(
        config=CONFIG,
        messages=({"role": "user", "content": "hi"},),
        tools=(),
        temperature=0.0,
        http_client=_client(handler),
    )

    assert seen["auth"] == "Bearer sk-test"
    assert seen["url"] == "https://api.test.example/chat/completions"
    assert response.payload == OK_PAYLOAD
    assert response.latency_s >= 0.0


def test_missing_key_env_raises(monkeypatch) -> None:
    monkeypatch.delenv("TEST_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="TEST_API_KEY"):
        chat_completion(
            config=CONFIG,
            messages=(),
            tools=(),
            temperature=0.0,
            http_client=_client(lambda request: httpx.Response(200, json=OK_PAYLOAD)),
        )


def test_empty_api_key_env_skips_auth_header() -> None:
    local = ProviderConfig(
        id="local", base_url="http://localhost:11434/v1", api_key_env="", model_id="m"
    )
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=OK_PAYLOAD)

    chat_completion(
        config=local,
        messages=(),
        tools=(),
        temperature=0.0,
        http_client=_client(handler),
    )

    assert seen["auth"] is None


def test_retries_on_server_error_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json=OK_PAYLOAD)

    response = chat_completion(
        config=CONFIG,
        messages=(),
        tools=(),
        temperature=0.0,
        http_client=_client(handler),
        sleep=lambda seconds: None,
    )

    assert attempts["n"] == 3
    assert response.payload == OK_PAYLOAD


def test_exhausted_retries_raise(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")

    with pytest.raises(httpx.HTTPStatusError):
        chat_completion(
            config=CONFIG,
            messages=(),
            tools=(),
            temperature=0.0,
            http_client=_client(lambda request: httpx.Response(429, json={})),
            sleep=lambda seconds: None,
        )


def test_tools_are_included_only_when_present(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        bodies.append(_json.loads(request.content))
        return httpx.Response(200, json=OK_PAYLOAD)

    client = _client(handler)
    chat_completion(
        config=CONFIG, messages=(), tools=(), temperature=0.5, http_client=client
    )
    chat_completion(
        config=CONFIG,
        messages=(),
        tools=({"type": "function", "function": {"name": "x"}},),
        temperature=0.5,
        http_client=client,
    )

    assert "tools" not in bodies[0]
    assert bodies[1]["tools"] == [{"type": "function", "function": {"name": "x"}}]
    assert bodies[1]["model"] == "test-model"
    assert bodies[1]["temperature"] == 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runners/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.runners.client'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/runners/client.py
"""EDGE: OpenAI-compatible /chat/completions client with retry and latency."""

import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from agent_eval_lab.runners.config import ProviderConfig

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True, kw_only=True)
class ProviderResponse:
    payload: Mapping[str, Any]
    latency_s: float


def _headers(config: ProviderConfig) -> dict[str, str]:
    headers = dict(config.extra_headers)
    if config.api_key_env:
        key = os.environ.get(config.api_key_env)
        if not key:
            raise RuntimeError(f"missing environment variable: {config.api_key_env}")
        headers["Authorization"] = f"Bearer {key}"
    return headers


def chat_completion(
    *,
    config: ProviderConfig,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]],
    temperature: float,
    http_client: httpx.Client,
    max_attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> ProviderResponse:
    headers = _headers(config)
    body: dict[str, Any] = {
        "model": config.model_id,
        "messages": list(messages),
        "temperature": temperature,
    }
    if tools:
        body["tools"] = list(tools)
    url = f"{config.base_url}/chat/completions"
    for attempt in range(1, max_attempts + 1):
        start = time.monotonic()
        try:
            response = http_client.post(url, json=body, headers=headers)
        except httpx.TransportError:
            if attempt == max_attempts:
                raise
            sleep(float(attempt))
            continue
        if response.status_code in _RETRYABLE_STATUS and attempt < max_attempts:
            sleep(float(attempt))
            continue
        response.raise_for_status()
        return ProviderResponse(
            payload=response.json(), latency_s=time.monotonic() - start
        )
    raise RuntimeError("unreachable: retry loop exited without return or raise")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/runners/test_client.py -v`
Expected: 6 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/runners tests/runners
git commit -m "feat: add OpenAI-compatible provider client with retry and latency capture"
```

---

### Task 14: Wire format and the model↔tool loop

**Files:**
- Create: `src/agent_eval_lab/runners/wire.py`
- Create: `src/agent_eval_lab/runners/loop.py`
- Test: `tests/runners/test_wire.py`
- Test: `tests/runners/test_loop.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/runners/test_wire.py
import json

from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.runners.wire import tooldef_to_openai, turn_to_message
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS


def test_tooldef_renders_openai_function_format() -> None:
    rendered = tooldef_to_openai(WORKSPACE_TOOLS["search_docs"])

    assert rendered["type"] == "function"
    assert rendered["function"]["name"] == "search_docs"
    assert rendered["function"]["parameters"]["required"] == ["query"]


def test_message_turn_renders_role_and_content() -> None:
    assert turn_to_message(MessageTurn(role="user", content="hi")) == {
        "role": "user",
        "content": "hi",
    }


def test_tool_call_turn_renders_arguments_as_json_string() -> None:
    turn = ToolCallTurn(
        tool_calls=(
            ToolCall(call_id="c1", name="search_docs", arguments={"query": "x"}),
        )
    )

    rendered = turn_to_message(turn)

    assert rendered["role"] == "assistant"
    call = rendered["tool_calls"][0]
    assert call["id"] == "c1"
    assert json.loads(call["function"]["arguments"]) == {"query": "x"}


def test_tool_result_turns_render_success_and_failure() -> None:
    success = turn_to_message(
        ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"doc_ids": []}))
    )
    failure = turn_to_message(
        ToolResultTurn(call_id="c2", outcome=ToolFailure(error="schema violation: x"))
    )

    assert success == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": json.dumps({"doc_ids": []}),
    }
    assert failure == {
        "role": "tool",
        "tool_call_id": "c2",
        "content": json.dumps({"error": "schema violation: x"}),
    }
```

```python
# tests/runners/test_loop.py
import json

import httpx

from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.tasks.parse import parse_task
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

CONFIG = ProviderConfig(
    id="local", base_url="http://localhost:11434/v1", api_key_env="", model_id="m"
)

TASK = parse_task(
    {
        "id": "ws-017",
        "capability": "multi_step",
        "input": {
            "messages": [
                {"type": "message", "role": "user", "content": "Create then close."}
            ],
            "available_tools": ["search_docs", "create_ticket", "update_ticket"],
        },
        "verification": {
            "type": "tool_call_match",
            "expected_tool_calls": [
                {"name": "create_ticket", "arguments": {"title": "x", "priority": "low"}},
                {"name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}},
            ],
            "match": "exact_sequence",
        },
        "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
        "initial_state": {"docs": {}, "tickets": {}},
    }
)


def _tool_call_response(name: str, arguments: dict, call_id: str) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
    }


def _final_response(content: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 30, "completion_tokens": 5},
    }


def _scripted_client(responses: list[dict]) -> httpx.Client:
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=remaining.pop(0))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_loop_threads_state_and_stops_on_final_message() -> None:
    client = _scripted_client(
        [
            _tool_call_response("create_ticket", {"title": "x", "priority": "low"}, "c1"),
            _tool_call_response(
                "update_ticket", {"ticket_id": "T-1", "status": "closed"}, "c2"
            ),
            _final_response("Done."),
        ]
    )

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=6,
        temperature=0.0,
    )

    assert trajectory.stop_reason == "completed"
    kinds = [type(turn) for turn in trajectory.turns]
    assert kinds == [
        MessageTurn,        # user
        ToolCallTurn,       # create
        ToolResultTurn,
        ToolCallTurn,       # update
        ToolResultTurn,
        MessageTurn,        # final assistant
    ]
    create_result = trajectory.turns[2]
    assert isinstance(create_result.outcome, ToolSuccess)
    assert create_result.outcome.result == {"ticket_id": "T-1"}
    update_result = trajectory.turns[4]
    assert update_result.outcome.result == {"ticket_id": "T-1", "status": "closed"}
    assert trajectory.usage.prompt_tokens == 70
    assert trajectory.usage.completion_tokens == 25
    assert trajectory.run_index == 0


def test_loop_records_parse_failure_and_stops() -> None:
    bad = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {"name": "search_docs", "arguments": '{"query": '},
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
    }
    client = _scripted_client([bad])

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=1,
        max_steps=6,
        temperature=0.0,
    )

    assert trajectory.stop_reason == "parse_failure"
    assert trajectory.parse_failure is not None
    assert trajectory.run_index == 1


def test_loop_enforces_max_steps() -> None:
    responses = [
        _tool_call_response("search_docs", {"query": "x"}, f"c{i}") for i in range(5)
    ]
    client = _scripted_client(responses)

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=2,
        temperature=0.0,
    )

    assert trajectory.stop_reason == "max_steps"
    tool_call_turns = [t for t in trajectory.turns if isinstance(t, ToolCallTurn)]
    assert len(tool_call_turns) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runners/test_wire.py tests/runners/test_loop.py -v`
Expected: FAIL — no modules `runners.wire` / `runners.loop`.

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/runners/wire.py
"""Pure conversions between Turn records and the OpenAI wire format."""

import json
from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolResultTurn,
    ToolSuccess,
    Turn,
)
from agent_eval_lab.tools.workspace import ToolDef


def tooldef_to_openai(tool: ToolDef) -> Mapping[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def turn_to_message(turn: Turn) -> Mapping[str, Any]:
    if isinstance(turn, MessageTurn):
        return {"role": turn.role, "content": turn.content}
    if isinstance(turn, ToolCallTurn):
        return {
            "role": "assistant",
            "content": turn.content,
            "tool_calls": [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(dict(call.arguments), sort_keys=True),
                    },
                }
                for call in turn.tool_calls
            ],
        }
    if isinstance(turn, ToolResultTurn):
        content = (
            json.dumps(turn.outcome.result)
            if isinstance(turn.outcome, ToolSuccess)
            else json.dumps({"error": turn.outcome.error})
        )
        return {"role": "tool", "tool_call_id": turn.call_id, "content": content}
    raise ValueError(f"unknown turn: {turn!r}")
```

```python
# src/agent_eval_lab/runners/loop.py
"""EDGE: the model<->tool loop. Holds state, threads it through pure `apply`."""

from collections.abc import Mapping

import httpx

from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolResultTurn, Turn
from agent_eval_lab.runners.client import chat_completion
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.parse import parse_assistant_payload
from agent_eval_lab.runners.wire import tooldef_to_openai, turn_to_message
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.workspace import ToolDef, apply


def run_single(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    run_index: int,
    max_steps: int,
    temperature: float,
) -> Trajectory:
    state = dict(task.initial_state or {})
    turns: list[Turn] = list(task.input.messages)
    tools = tuple(tooldef_to_openai(registry[name]) for name in task.input.available_tools)
    prompt_tokens = 0
    completion_tokens = 0
    latency_s = 0.0
    parse_failure: ParseFailure | None = None
    stop_reason = "max_steps"

    for _ in range(max_steps):
        response = chat_completion(
            config=config,
            messages=tuple(turn_to_message(turn) for turn in turns),
            tools=tools,
            temperature=temperature,
            http_client=http_client,
        )
        usage = response.payload.get("usage", {})
        prompt_tokens += usage.get("prompt_tokens", 0)
        completion_tokens += usage.get("completion_tokens", 0)
        latency_s += response.latency_s
        parsed = parse_assistant_payload(response.payload["choices"][0]["message"])
        if isinstance(parsed, ParseFailure):
            parse_failure = parsed
            stop_reason = "parse_failure"
            break
        turns.append(parsed)
        if isinstance(parsed, MessageTurn):
            stop_reason = "completed"
            break
        for call in parsed.tool_calls:
            state, outcome = apply(
                registry=registry, name=call.name, arguments=call.arguments, state=state
            )
            turns.append(ToolResultTurn(call_id=call.call_id, outcome=outcome))

    return Trajectory(
        turns=tuple(turns),
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_s=latency_s,
        ),
        run_index=run_index,
        stop_reason=stop_reason,
        parse_failure=parse_failure,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/runners -v`
Expected: all runner tests pass (config + parse + client + wire + loop).

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/runners tests/runners
git commit -m "feat: add model-tool loop with step limits and usage capture"
```

---

### Task 15: Multi-run

**Files:**
- Create: `src/agent_eval_lab/runners/multi_run.py`
- Test: `tests/runners/test_multi_run.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runners/test_multi_run.py
import json

import httpx

from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.multi_run import run_task_k
from agent_eval_lab.tasks.parse import parse_task
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

CONFIG = ProviderConfig(
    id="local", base_url="http://localhost:11434/v1", api_key_env="", model_id="qwen3-8b"
)

TASK = parse_task(
    {
        "id": "ws-001",
        "capability": "tool_selection",
        "input": {
            "messages": [
                {
                    "type": "message",
                    "role": "user",
                    "content": "Search the docs for 'refund policy'.",
                }
            ],
            "available_tools": ["search_docs", "create_ticket", "update_ticket"],
        },
        "verification": {
            "type": "tool_call_match",
            "expected_tool_calls": [
                {"name": "search_docs", "arguments": {"query": "refund policy"}}
            ],
            "match": "exact_sequence",
        },
        "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
        "initial_state": {"docs": {}, "tickets": {}},
    }
)


def _handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if any(message["role"] == "tool" for message in body["messages"]):
        message = {"role": "assistant", "content": "Done."}
    else:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "search_docs",
                        "arguments": json.dumps({"query": "refund policy"}),
                    },
                }
            ],
        }
    return httpx.Response(
        200,
        json={
            "choices": [{"message": message}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


def test_runs_k_times_and_grades_each_run() -> None:
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    results = run_task_k(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k=3,
        max_steps=6,
        temperature=0.0,
    )

    assert len(results) == 3
    assert [run.run_index for run in results] == [0, 1, 2]
    assert all(run.task_id == "ws-001" for run in results)
    assert all(run.condition_id == "local:qwen3-8b" for run in results)
    assert all(run.grade.passed for run in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_multi_run.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.runners.multi_run'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/runners/multi_run.py
"""EDGE: run a task k times (multi-run from day 1) and grade every run."""

from collections.abc import Mapping

import httpx

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.workspace import ToolDef


def run_task_k(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    k: int,
    max_steps: int,
    temperature: float,
) -> tuple[RunResult, ...]:
    condition_id = f"{config.id}:{config.model_id}"
    results = []
    for run_index in range(k):
        trajectory = run_single(
            task=task,
            registry=registry,
            config=config,
            http_client=http_client,
            run_index=run_index,
            max_steps=max_steps,
            temperature=temperature,
        )
        grade = grade_trajectory(
            verification=task.verification, trajectory=trajectory, registry=registry
        )
        results.append(
            RunResult(
                task_id=task.id,
                condition_id=condition_id,
                run_index=run_index,
                trajectory=trajectory,
                grade=grade,
            )
        )
    return tuple(results)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_multi_run.py -v`
Expected: 1 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/runners tests/runners
git commit -m "feat: add multi-run execution producing graded RunResults"
```

---

### Task 16: Metrics

**Files:**
- Create: `src/agent_eval_lab/metrics/__init__.py`
- Create: `src/agent_eval_lab/metrics/reliability.py`
- Create: `src/agent_eval_lab/metrics/cost.py`
- Test: `tests/metrics/test_reliability.py`
- Test: `tests/metrics/test_cost.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/metrics/test_reliability.py
import pytest

from agent_eval_lab.metrics.reliability import (
    failure_counts,
    mean_latency_s,
    pass_at_1,
    pass_pow_k,
    token_totals,
)
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _run(task_id: str, run_index: int, passed: bool, failure_reason=None) -> RunResult:
    return RunResult(
        task_id=task_id,
        condition_id="local:qwen3-8b",
        run_index=run_index,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=100, completion_tokens=20, latency_s=0.5),
            run_index=run_index,
            stop_reason="completed",
        ),
        grade=GradeResult(
            grader_id="ast_tool_match",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=failure_reason,
        ),
    )


# Task A passes all runs; task B fails run 1 of 2.
RESULTS = (
    _run("a", 0, True),
    _run("a", 1, True),
    _run("b", 0, True),
    _run("b", 1, False, "wrong_args"),
)


def test_pass_at_1_is_trial_accuracy() -> None:
    assert pass_at_1(RESULTS) == 0.75


def test_pass_pow_k_is_task_level_reliability() -> None:
    assert pass_pow_k(RESULTS) == 0.5


def test_metrics_reject_empty_results() -> None:
    with pytest.raises(ValueError, match="no results"):
        pass_at_1(())
    with pytest.raises(ValueError, match="no results"):
        pass_pow_k(())


def test_failure_counts_groups_by_category() -> None:
    results = RESULTS + (_run("c", 0, False, None),)

    assert failure_counts(results) == {"wrong_args": 1, "unclassified": 1}


def test_token_totals_and_latency() -> None:
    assert token_totals(RESULTS) == (400, 80)
    assert mean_latency_s(RESULTS) == 0.5
```

```python
# tests/metrics/test_cost.py
from agent_eval_lab.metrics.cost import TokenPrice, total_cost_usd
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _run(prompt_tokens: int, completion_tokens: int) -> RunResult:
    return RunResult(
        task_id="a",
        condition_id="c",
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_s=0.0,
            ),
            run_index=0,
            stop_reason="completed",
        ),
        grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}),
    )


def test_cost_is_tokens_times_price_per_million() -> None:
    results = (_run(500_000, 100_000), _run(500_000, 100_000))
    price = TokenPrice(input_per_mtok=1.0, output_per_mtok=5.0)

    assert total_cost_usd(results, price=price) == 1.0 + 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/metrics -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.metrics'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/metrics/__init__.py
"""Pure aggregation over RunResults."""
```

```python
# src/agent_eval_lab/metrics/reliability.py
"""pass@1 (trial accuracy) and pass^k (task-level reliability), spec §4.6.

A task passes pass^k iff ALL of its runs pass; the estimand is the
proportion of tasks that pass every run — not trial-level accuracy.
"""

from collections.abc import Sequence

from agent_eval_lab.records.grade import RunResult


def _require_results(results: Sequence[RunResult]) -> None:
    if not results:
        raise ValueError("no results to aggregate")


def pass_at_1(results: Sequence[RunResult]) -> float:
    _require_results(results)
    return sum(1 for run in results if run.grade.passed) / len(results)


def pass_pow_k(results: Sequence[RunResult]) -> float:
    _require_results(results)
    by_task: dict[str, list[bool]] = {}
    for run in results:
        by_task.setdefault(run.task_id, []).append(run.grade.passed)
    reliable = sum(1 for passes in by_task.values() if all(passes))
    return reliable / len(by_task)


def failure_counts(results: Sequence[RunResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in results:
        if run.grade.passed:
            continue
        key = run.grade.failure_reason or "unclassified"
        counts[key] = counts.get(key, 0) + 1
    return counts


def token_totals(results: Sequence[RunResult]) -> tuple[int, int]:
    prompt = sum(run.trajectory.usage.prompt_tokens for run in results)
    completion = sum(run.trajectory.usage.completion_tokens for run in results)
    return prompt, completion


def mean_latency_s(results: Sequence[RunResult]) -> float:
    _require_results(results)
    return sum(run.trajectory.usage.latency_s for run in results) / len(results)
```

```python
# src/agent_eval_lab/metrics/cost.py
"""Derived cost: captured tokens x explicit prices. No stale hardcoded tables."""

from collections.abc import Sequence
from dataclasses import dataclass

from agent_eval_lab.metrics.reliability import token_totals
from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class TokenPrice:
    input_per_mtok: float
    output_per_mtok: float


def total_cost_usd(results: Sequence[RunResult], *, price: TokenPrice) -> float:
    prompt, completion = token_totals(results)
    return (prompt * price.input_per_mtok + completion * price.output_per_mtok) / 1_000_000
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/metrics -v`
Expected: 6 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/metrics tests/metrics
git commit -m "feat: add pass@1, pass^k, failure counts, and derived cost metrics"
```

---

### Task 17: Baseline report

**Files:**
- Create: `src/agent_eval_lab/reports/__init__.py`
- Create: `src/agent_eval_lab/reports/baseline.py`
- Test: `tests/reports/test_baseline.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/reports/test_baseline.py
from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.reports.baseline import build_baseline_report, render_markdown


def _run(task_id: str, run_index: int, passed: bool, failure_reason=None) -> RunResult:
    return RunResult(
        task_id=task_id,
        condition_id="local:qwen3-8b",
        run_index=run_index,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=100, completion_tokens=20, latency_s=0.5),
            run_index=run_index,
            stop_reason="completed",
        ),
        grade=GradeResult(
            grader_id="ast_tool_match",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=failure_reason,
        ),
    )


RESULTS = (
    _run("a", 0, True),
    _run("a", 1, True),
    _run("b", 0, False, "wrong_args"),
    _run("b", 1, False, "schema_violation"),
)


def test_build_report_aggregates_metrics() -> None:
    report = build_baseline_report(
        RESULTS, dataset_id="workspace_tool_use_v1", condition_id="local:qwen3-8b", k=2
    )

    assert report.n_tasks == 2
    assert report.k == 2
    assert report.pass_at_1 == 0.5
    assert report.pass_pow_k == 0.5
    assert report.failure_counts == {"wrong_args": 1, "schema_violation": 1}
    assert report.prompt_tokens == 400
    assert report.completion_tokens == 80
    assert report.total_cost_usd is None
    assert report.mean_latency_s == 0.5


def test_build_report_computes_cost_when_price_given() -> None:
    report = build_baseline_report(
        RESULTS,
        dataset_id="d",
        condition_id="c",
        k=2,
        price=TokenPrice(input_per_mtok=1.0, output_per_mtok=5.0),
    )

    assert report.total_cost_usd == (400 * 1.0 + 80 * 5.0) / 1_000_000


def test_render_markdown_contains_headline_numbers() -> None:
    report = build_baseline_report(
        RESULTS, dataset_id="workspace_tool_use_v1", condition_id="local:qwen3-8b", k=2
    )

    text = render_markdown(report)

    assert "# Baseline report — local:qwen3-8b" in text
    assert "pass@1 (trial accuracy): 0.500" in text
    assert "pass^2 (task reliability): 0.500" in text
    assert "| wrong_args | 1 |" in text
    assert "not computed" in text


def test_render_markdown_handles_no_failures() -> None:
    report = build_baseline_report(
        (_run("a", 0, True),), dataset_id="d", condition_id="c", k=1
    )

    assert "No failures recorded." in render_markdown(report)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/reports -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.reports'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/reports/__init__.py
"""Pure report models and rendering."""
```

```python
# src/agent_eval_lab/reports/baseline.py
"""Baseline report: pure build + markdown rendering. File I/O stays in cli."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.metrics.cost import TokenPrice, total_cost_usd
from agent_eval_lab.metrics.reliability import (
    failure_counts,
    mean_latency_s,
    pass_at_1,
    pass_pow_k,
    token_totals,
)
from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class BaselineReport:
    dataset_id: str
    condition_id: str
    n_tasks: int
    k: int
    pass_at_1: float
    pass_pow_k: float
    failure_counts: Mapping[str, int]
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float | None
    mean_latency_s: float


def build_baseline_report(
    results: Sequence[RunResult],
    *,
    dataset_id: str,
    condition_id: str,
    k: int,
    price: TokenPrice | None = None,
) -> BaselineReport:
    prompt_tokens, completion_tokens = token_totals(results)
    return BaselineReport(
        dataset_id=dataset_id,
        condition_id=condition_id,
        n_tasks=len({run.task_id for run in results}),
        k=k,
        pass_at_1=pass_at_1(results),
        pass_pow_k=pass_pow_k(results),
        failure_counts=failure_counts(results),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=None if price is None else total_cost_usd(results, price=price),
        mean_latency_s=mean_latency_s(results),
    )


def render_markdown(report: BaselineReport) -> str:
    cost = (
        f"${report.total_cost_usd:.4f}"
        if report.total_cost_usd is not None
        else "not computed (no price given)"
    )
    lines = [
        f"# Baseline report — {report.condition_id}",
        "",
        f"- Dataset: `{report.dataset_id}`",
        f"- Tasks: {report.n_tasks} · runs per task: k={report.k}",
        f"- pass@1 (trial accuracy): {report.pass_at_1:.3f}",
        f"- pass^{report.k} (task reliability): {report.pass_pow_k:.3f}",
        f"- Tokens: {report.prompt_tokens} prompt · {report.completion_tokens} completion",
        f"- Estimated cost: {cost}",
        f"- Mean run latency: {report.mean_latency_s:.2f}s",
        "",
        "## Failures by category",
        "",
    ]
    if not report.failure_counts:
        lines.append("No failures recorded.")
    else:
        lines.extend(["| category | count |", "| --- | --- |"])
        ordered = sorted(report.failure_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        lines.extend(f"| {name} | {count} |" for name, count in ordered)
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/reports -v`
Expected: 4 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/reports tests/reports
git commit -m "feat: add pure baseline report build and markdown rendering"
```

---

### Task 18: The 20-task dataset

Replaces the legacy `examples/datasets/tool_selection.jsonl` (name-only expected values, no schemas/args — superseded by the `Task` format; nothing in the code loads it). Capabilities: 8 `tool_selection`, 8 `argument_extraction`, 4 `multi_step`. Every user message pins the exact argument values so deterministic grading is fair; loosening this is Weeks 3–4 work (state-based verification).

**Files:**
- Create: `examples/datasets/workspace_tool_use_v1.jsonl`
- Delete: `examples/datasets/tool_selection.jsonl`
- Test: `tests/datasets/test_workspace_tool_use.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/datasets/test_workspace_tool_use.py
"""Dataset conformance: every task loads, references known tools, and has
schema-valid expected calls (the dataset can never be wrong about the world).
"""

from pathlib import Path

from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import ToolCallMatchSpec
from agent_eval_lab.tools.validation import validate_args
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

DATASET = Path(__file__).parent.parent.parent / "examples/datasets/workspace_tool_use_v1.jsonl"


def test_dataset_has_twenty_tasks_across_three_capabilities() -> None:
    tasks = load_tasks(DATASET)

    assert len(tasks) == 20
    capabilities = {task.capability for task in tasks}
    assert capabilities == {"tool_selection", "argument_extraction", "multi_step"}


def test_every_task_references_known_tools_and_valid_expected_calls() -> None:
    for task in load_tasks(DATASET):
        for name in task.input.available_tools:
            assert name in WORKSPACE_TOOLS, f"{task.id}: unknown tool {name}"
        assert isinstance(task.verification, ToolCallMatchSpec)
        for call in task.verification.expected_tool_calls:
            tool = WORKSPACE_TOOLS[call.name]
            error = validate_args(tool.parameters, call.arguments)
            assert error is None, f"{task.id}: expected call invalid: {error}"


def test_every_task_has_initial_state_and_dev_split() -> None:
    for task in load_tasks(DATASET):
        assert task.initial_state is not None, task.id
        assert task.metadata.split == "dev"
        assert task.metadata.world_template_id == "workspace-v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/datasets -v`
Expected: FAIL — `FileNotFoundError` for `workspace_tool_use_v1.jsonl`.

- [ ] **Step 3: Write the dataset and remove the legacy file**

Every line shares this system message (abbreviated below as `SYS`):

`You are a support agent for the Workspace tool suite. Complete the request by calling the available tools with exactly the argument values the request specifies. When done, reply with a short confirmation.`

And all tasks expose all three tools (`"available_tools": ["search_docs", "create_ticket", "update_ticket"]`) so the unused two act as distractors.

Write `examples/datasets/workspace_tool_use_v1.jsonl` with exactly these 20 lines (`SYS` expanded; one JSON object per line):

```jsonl
{"id":"ws-001","capability":"tool_selection","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Search the docs for 'refund policy'."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"search_docs","arguments":{"query":"refund policy"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{"doc-1":{"title":"Refund policy","body":"Refunds are processed within 5 business days."},"doc-2":{"title":"Onboarding guide","body":"New accounts are activated after email verification."}},"tickets":{}}}
{"id":"ws-002","capability":"tool_selection","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Search the docs for 'email verification'."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"search_docs","arguments":{"query":"email verification"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{"doc-2":{"title":"Onboarding guide","body":"New accounts are activated after email verification."}},"tickets":{}}}
{"id":"ws-003","capability":"tool_selection","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Create a ticket titled 'Printer offline' with priority low."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"Printer offline","priority":"low"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{}}}
{"id":"ws-004","capability":"tool_selection","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Close ticket T-7."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"update_ticket","arguments":{"ticket_id":"T-7","status":"closed"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{"T-7":{"title":"Login broken","priority":"high","status":"open"}}}}
{"id":"ws-005","capability":"tool_selection","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Create a ticket titled 'VPN drops every hour' with priority high."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"VPN drops every hour","priority":"high"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{}}}
{"id":"ws-006","capability":"tool_selection","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Search the docs for 'self-service'."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"search_docs","arguments":{"query":"self-service"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{"doc-3":{"title":"Password reset","body":"Use the self-service portal to reset passwords."}},"tickets":{}}}
{"id":"ws-007","capability":"tool_selection","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Reopen ticket T-3."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"update_ticket","arguments":{"ticket_id":"T-3","status":"open"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{"T-3":{"title":"Billing question","priority":"low","status":"closed"}}}}
{"id":"ws-008","capability":"tool_selection","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Create a ticket titled 'Email bounce' with priority medium."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"Email bounce","priority":"medium"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{}}}
{"id":"ws-009","capability":"argument_extraction","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"File a high-priority ticket titled 'Checkout page returns 500'."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"Checkout page returns 500","priority":"high"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{}}}
{"id":"ws-010","capability":"argument_extraction","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"File a low-priority ticket titled 'Typo on the pricing page'."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"Typo on the pricing page","priority":"low"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{}}}
{"id":"ws-011","capability":"argument_extraction","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Mark ticket T-12 as closed."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"update_ticket","arguments":{"ticket_id":"T-12","status":"closed"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{"T-12":{"title":"Exports stuck","priority":"medium","status":"open"}}}}
{"id":"ws-012","capability":"argument_extraction","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Look up the phrase 'business days' in the docs."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"search_docs","arguments":{"query":"business days"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{"doc-1":{"title":"Refund policy","body":"Refunds are processed within 5 business days."}},"tickets":{}}}
{"id":"ws-013","capability":"argument_extraction","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Open a medium-priority ticket titled 'Slow dashboard loading'."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"Slow dashboard loading","priority":"medium"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{}}}
{"id":"ws-014","capability":"argument_extraction","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"A customer cannot sign in. Create a ticket titled 'Cannot sign in' with priority high."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"Cannot sign in","priority":"high"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{}}}
{"id":"ws-015","capability":"argument_extraction","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Set the status of ticket T-2 to open."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"update_ticket","arguments":{"ticket_id":"T-2","status":"open"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{"T-2":{"title":"Refund request","priority":"medium","status":"closed"}}}}
{"id":"ws-016","capability":"argument_extraction","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Look up the phrase 'password reset' in the docs."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"search_docs","arguments":{"query":"password reset"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{"doc-3":{"title":"Password reset","body":"Use the self-service portal to reset passwords."}},"tickets":{}}}
{"id":"ws-017","capability":"multi_step","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Create a ticket titled 'Data export failing' with priority high, then close it."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"Data export failing","priority":"high"}},{"name":"update_ticket","arguments":{"ticket_id":"T-1","status":"closed"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{}}}
{"id":"ws-018","capability":"multi_step","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Create a ticket titled 'Broken webhook' with priority medium, then close it."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"Broken webhook","priority":"medium"}},{"name":"update_ticket","arguments":{"ticket_id":"T-1","status":"closed"}}],"match":"exact_sequence"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{}}}
{"id":"ws-019","capability":"multi_step","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Create two tickets, both priority low: 'Audit log gap' and 'Metrics missing'."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"create_ticket","arguments":{"title":"Audit log gap","priority":"low"}},{"name":"create_ticket","arguments":{"title":"Metrics missing","priority":"low"}}],"match":"multiset"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{}}}
{"id":"ws-020","capability":"multi_step","input":{"messages":[{"type":"message","role":"system","content":"SYS"},{"type":"message","role":"user","content":"Close tickets T-4 and T-5."}],"available_tools":["search_docs","create_ticket","update_ticket"]},"verification":{"type":"tool_call_match","expected_tool_calls":[{"name":"update_ticket","arguments":{"ticket_id":"T-4","status":"closed"}},{"name":"update_ticket","arguments":{"ticket_id":"T-5","status":"closed"}}],"match":"multiset"},"metadata":{"split":"dev","version":"1","provenance":"hand_written","world_template_id":"workspace-v1"},"initial_state":{"docs":{},"tickets":{"T-4":{"title":"Stale cache","priority":"low","status":"open"},"T-5":{"title":"Slow search","priority":"medium","status":"open"}}}}
```

Then:

```bash
git rm examples/datasets/tool_selection.jsonl
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/datasets -v`
Expected: 3 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add examples/datasets tests/datasets
git commit -m "feat: add 20-task workspace tool-use dataset; retire legacy seed dataset"
```

---

### Task 19: CLI orchestration

**Files:**
- Create: `src/agent_eval_lab/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import json
from pathlib import Path

import httpx

from agent_eval_lab.cli import main


def _handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if any(message["role"] == "tool" for message in body["messages"]):
        message = {"role": "assistant", "content": "Done."}
    else:
        user = next(m for m in body["messages"] if m["role"] == "user")
        query = user["content"].split("'")[1]
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "search_docs",
                        "arguments": json.dumps({"query": query}),
                    },
                }
            ],
        }
    return httpx.Response(
        200,
        json={
            "choices": [{"message": message}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


def _write_dataset(path: Path) -> Path:
    lines = []
    for index, query in enumerate(["refund policy", "email verification"], start=1):
        lines.append(
            {
                "id": f"ws-{index:03d}",
                "capability": "tool_selection",
                "input": {
                    "messages": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": f"Search the docs for '{query}'.",
                        }
                    ],
                    "available_tools": ["search_docs", "create_ticket", "update_ticket"],
                },
                "verification": {
                    "type": "tool_call_match",
                    "expected_tool_calls": [
                        {"name": "search_docs", "arguments": {"query": query}}
                    ],
                    "match": "exact_sequence",
                },
                "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
                "initial_state": {"docs": {}, "tickets": {}},
            }
        )
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    return path


def test_run_baseline_writes_report_and_traces(tmp_path: Path, capsys) -> None:
    dataset = _write_dataset(tmp_path / "tasks.jsonl")
    out_dir = tmp_path / "out"
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    exit_code = main(
        [
            "run-baseline",
            "--dataset", str(dataset),
            "--provider", "local",
            "--k", "2",
            "--out", str(out_dir),
        ],
        http_client=client,
    )

    assert exit_code == 0
    report = (out_dir / "baseline-local.md").read_text()
    assert "pass@1 (trial accuracy): 1.000" in report
    assert "pass^2 (task reliability): 1.000" in report
    runs = (out_dir / "runs-local.jsonl").read_text().strip().splitlines()
    assert len(runs) == 4  # 2 tasks x k=2
    first = json.loads(runs[0])
    assert first["task_id"] == "ws-001"
    assert first["grade"]["passed"] is True
    assert str(out_dir / "baseline-local.md") in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.cli'`

- [ ] **Step 3: Implement**

```python
# src/agent_eval_lab/cli.py
"""EDGE: command-line orchestration. All logic lives in the pure core."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

import httpx

from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.serialize import run_result_to_dict
from agent_eval_lab.reports.baseline import build_baseline_report, render_markdown
from agent_eval_lab.runners.config import PROVIDERS, ProviderConfig
from agent_eval_lab.runners.multi_run import run_task_k
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS


def run_baseline(
    *,
    dataset_path: Path,
    config: ProviderConfig,
    k: int,
    max_steps: int,
    temperature: float,
    out_dir: Path,
    price: TokenPrice | None,
    http_client: httpx.Client,
) -> Path:
    tasks = load_tasks(dataset_path)
    results = tuple(
        run
        for task in tasks
        for run in run_task_k(
            task=task,
            registry=WORKSPACE_TOOLS,
            config=config,
            http_client=http_client,
            k=k,
            max_steps=max_steps,
            temperature=temperature,
        )
    )
    report = build_baseline_report(
        results,
        dataset_id=dataset_path.stem,
        condition_id=f"{config.id}:{config.model_id}",
        k=k,
        price=price,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_path = out_dir / f"runs-{config.id}.jsonl"
    runs_path.write_text(
        "\n".join(json.dumps(run_result_to_dict(run)) for run in results) + "\n"
    )
    report_path = out_dir / f"baseline-{config.id}.md"
    report_path.write_text(render_markdown(report))
    return report_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-eval-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)
    baseline = subparsers.add_parser("run-baseline", help="run the baseline eval")
    baseline.add_argument("--dataset", required=True, type=Path)
    baseline.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    baseline.add_argument("--model", help="override the provider's default model id")
    baseline.add_argument("--k", type=int, default=3)
    baseline.add_argument("--max-steps", type=int, default=6)
    baseline.add_argument("--temperature", type=float, default=0.0)
    baseline.add_argument("--out", type=Path, default=Path("reports"))
    baseline.add_argument("--input-price-per-mtok", type=float)
    baseline.add_argument("--output-price-per-mtok", type=float)
    return parser


def main(argv: list[str] | None = None, http_client: httpx.Client | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = PROVIDERS[args.provider]
    if args.model:
        config = replace(config, model_id=args.model)
    price = None
    if args.input_price_per_mtok is not None and args.output_price_per_mtok is not None:
        price = TokenPrice(
            input_per_mtok=args.input_price_per_mtok,
            output_per_mtok=args.output_price_per_mtok,
        )
    client = http_client or httpx.Client(timeout=120.0)
    try:
        report_path = run_baseline(
            dataset_path=args.dataset,
            config=config,
            k=args.k,
            max_steps=args.max_steps,
            temperature=args.temperature,
            out_dir=args.out,
            price=price,
            http_client=client,
        )
    finally:
        if http_client is None:
            client.close()
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 1 passed.

- [ ] **Step 5: Validate and commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
git add src/agent_eval_lab/cli.py tests/test_cli.py
git commit -m "feat: add run-baseline CLI writing traces and the baseline report"
```

---

### Task 20: Docs, final validation, optional live baseline

**Files:**
- Modify: `README.md` (Quick Start section)
- Modify: `docs/ROADMAP.md` (no change expected — verify only)

- [ ] **Step 1: Add baseline instructions to README Quick Start**

In `README.md`, append to the **Quick Start** section (after the existing ```bash fence):

```markdown
Run the tool-use baseline (requires a local OpenAI-compatible server, e.g.
Ollama/MLX serving `qwen3-8b` on `localhost:11434`, or a provider key):

```bash
uv run python -m agent_eval_lab.cli run-baseline \
  --dataset examples/datasets/workspace_tool_use_v1.jsonl \
  --provider local --k 3
```

Outputs: `reports/baseline-<provider>.md` (headline `pass@1`, `pass^k`, tokens,
cost, latency, failure taxonomy) and `reports/runs-<provider>.jsonl` (full
graded trajectories). Hosted providers read their key from the environment
variable named in `src/agent_eval_lab/runners/config.py` (e.g.
`DASHSCOPE_API_KEY`); pass `--input-price-per-mtok/--output-price-per-mtok`
to include estimated cost.
```

Also update the **Status** section's first paragraph to:

```markdown
This repository has the Weeks 1–2 tool-use slice implemented: locked record
types, a schema-validated workspace-world, the AST tool-call grader with a
structured failure taxonomy, a multi-run runner with cost capture, a 20-task
dataset, a golden conformance suite, and a baseline report command. The full
pipeline is specified in [docs/superpowers/specs/](docs/superpowers/specs/)
and built slice by slice.
```

- [ ] **Step 2: Full validation**

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Expected: all tests pass (≈70), no lint or format errors.

- [ ] **Step 3: Optional live baseline (only if a provider is reachable)**

If `curl -s http://localhost:11434/v1/models` responds (local model serving) or a provider key env var is set, generate a real baseline report and commit it as the Week-2 deliverable evidence:

```bash
uv run python -m agent_eval_lab.cli run-baseline \
  --dataset examples/datasets/workspace_tool_use_v1.jsonl \
  --provider local --k 3 --out reports
git add reports/
```

If no provider is reachable, skip — the report generator is fully verified by `tests/test_cli.py`; note the skip in the commit message.

- [ ] **Step 4: Commit**

```bash
git add README.md reports/ 2>/dev/null || git add README.md
git commit -m "docs: add baseline run instructions; update status for tool-use slice"
```

---

## Spec coverage (self-review)

| §16 deliverable | Tasks |
|---|---|
| Locked `VerificationSpec` subset + task schema | 5 (schema/parse), 2–4 (records it builds on) |
| `workspace-world` 2–3 tools + schema validation | 7 |
| AST grader + failure taxonomy | 8 (canonicalize), 9 (grader), 10 (dispatch), 3 (taxonomy in `records/grade.py`) |
| Provider client | 12 (config), 13 (client) |
| Runner with limits, multi-run from day 1, cost capture | 14 (loop/limits/usage), 15 (multi-run), 16 (metrics/cost) |
| ~20 tool-use tasks (roadmap Weeks 1–2) | 18 |
| Initial golden conformance suite | 11 |
| Baseline report | 17 (model/render), 19 (CLI), 20 (instructions + optional live run) |
| TDD / property tests / CI (spec §12) | every task step 1; properties in 7 and 8; existing CI runs pytest+ruff unchanged |

**Known limitations carried forward (by design, Weeks 3–4+):** no `FinalStateSpec`/`AllOf`/`TrajectorySpec` yet; `normalizer` accepts only `None`; exact-argument prompts make grading brittle to paraphrase (mitigated by pinning values in user messages); no `adapter` implementations yet (field reserved); no seeds in `ExperimentSpec` sense (arrives Weeks 7–8).






