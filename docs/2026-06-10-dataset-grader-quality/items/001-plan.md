# Composite Verification Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the locked `VerificationSpec` union with `FinalStateSpec`, `TrajectorySpec`, and `AllOf` (plus their constraint data variants), record the final world-state on `Trajectory`, add pure state/policy/composite graders, wire them into dispatch + parsing + serialization, and prove every behavior with hand-verified golden cases.

**Architecture:** Strictly additive and pure-functional. New frozen `kw_only` dataclasses carry only data (no behavior). Three small pure interpreter modules (`graders/state.py`, `graders/policy.py`, `graders/composite.py`) grade against `(spec, initial_state, trajectory)`. `Trajectory` gains one optional defaulted `final_state` field; the runner populates it; serialization round-trips it. `grade_trajectory` gains one optional `initial_state` parameter and three `isinstance` branches; the `AllOf` branch recurses threading both `registry` and `initial_state`. Missing dot-paths and non-containers degrade to clean grade misses, never raise.

**Tech Stack:** Python 3.11, stdlib only (`collections.abc`, `dataclasses`, `typing`). Tests via `uv run pytest`. Lint/format via `uv run ruff`. No new runtime dependencies.

---

## Canonical verification gates (run after every task)

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Expected throughout: pytest all green (baseline 130 tests at start, growing as tasks add tests); ruff check reports `All checks passed!`; ruff format reports `<N> files already formatted`.

Baseline sanity check before starting:

```bash
uv run pytest -q
```

Expected: `130 passed` (last line). If this is not 130, STOP and reconcile before proceeding.

---

## File Structure

**Create:**
- `src/agent_eval_lab/graders/state.py` — pure `FinalStateSpec` interpreter (dot-path walk, `StateEquals`/`StateContains`). ≤ ~80 lines.
- `src/agent_eval_lab/graders/policy.py` — pure `TrajectorySpec` interpreter (`NoToolCall`/`OnlyModifies`/`MaxToolCalls`, leaf-diff, prefix coverage). ≤ ~120 lines.
- `src/agent_eval_lab/graders/composite.py` — pure `AllOf` interpreter (evaluate-all, AND, first-failure reason). ≤ ~60 lines.
- `tests/graders/test_state.py` — unit tests for the state grader.
- `tests/graders/test_policy.py` — unit tests for the policy grader.
- `tests/graders/test_composite.py` — unit tests for the composite grader.
- 11 new golden JSON cases under `tests/golden/` (see Task 13).

**Modify:**
- `src/agent_eval_lab/tasks/schema.py` — add the new spec + constraint dataclasses, widen `VerificationSpec`.
- `src/agent_eval_lab/records/trajectory.py` — add `final_state` field to `Trajectory`.
- `src/agent_eval_lab/records/serialize.py` — round-trip `final_state` in `trajectory_to_dict`/`trajectory_from_dict`.
- `src/agent_eval_lab/runners/loop.py` — record post-loop `state` into `Trajectory.final_state`.
- `src/agent_eval_lab/graders/dispatch.py` — add `initial_state` param + three `isinstance` branches.
- `src/agent_eval_lab/runners/multi_run.py` — pass `initial_state=task.initial_state` into `grade_trajectory`.
- `src/agent_eval_lab/tasks/parse.py` — parse `final_state`/`trajectory`/`all_of` discriminators + constraint sub-dicts.
- `tests/tasks/test_parse.py` — retarget the "unknown type" test (it currently uses `"final_state"`, which becomes a *known* type).
- `tests/test_golden_conformance.py` — bump suite-size assertion to 22; thread `initial_state=case.get("initial_state")`.

**Dependency order:** records (Trajectory field) → schema (specs) → graders (state, policy, composite) → dispatch → parse → serialize → runner threading → golden suite. Each task is independently committed.

---

## Task 1: Add `final_state` field to `Trajectory`

**Files:**
- Modify: `src/agent_eval_lab/records/trajectory.py`
- Test: `tests/records/test_trajectory.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/records/test_trajectory.py` (end of file):

```python
def test_trajectory_defaults_to_no_final_state() -> None:
    trajectory = _trajectory()

    assert trajectory.final_state is None


def test_trajectory_records_final_state() -> None:
    trajectory = _trajectory(final_state={"tickets": {"T-1": {"status": "closed"}}})

    assert trajectory.final_state == {"tickets": {"T-1": {"status": "closed"}}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/records/test_trajectory.py::test_trajectory_records_final_state -q`
Expected: FAIL with `TypeError: ... got an unexpected keyword argument 'final_state'`.

- [ ] **Step 3: Add the field**

In `src/agent_eval_lab/records/trajectory.py`, change the imports line:

```python
from dataclasses import dataclass
from typing import Any, Literal
```

becomes:

```python
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
```

Then add the field to `Trajectory` (after `parse_failure`):

```python
@dataclass(frozen=True, kw_only=True)
class Trajectory:
    turns: tuple[Turn, ...]
    usage: Usage
    run_index: int
    stop_reason: Literal["completed", "max_steps", "parse_failure"]
    parse_failure: ParseFailure | None = None
    final_state: Mapping[str, Any] | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/records/test_trajectory.py -q`
Expected: PASS (all trajectory tests green).

- [ ] **Step 5: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green (132 passed); ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/records/trajectory.py tests/records/test_trajectory.py
git commit -m "feat: record optional final_state on Trajectory"
```

---

## Task 2: Round-trip `final_state` in serialization

**Files:**
- Modify: `src/agent_eval_lab/records/serialize.py`
- Test: `tests/records/test_serialize.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/records/test_serialize.py` (end of file):

```python
def test_trajectory_to_dict_omits_final_state_when_none() -> None:
    trajectory = Trajectory(
        turns=TURNS,
        usage=Usage(prompt_tokens=1, completion_tokens=2, latency_s=0.1),
        run_index=0,
        stop_reason="completed",
    )

    data = trajectory_to_dict(trajectory)

    assert data["final_state"] is None


def test_trajectory_round_trips_final_state() -> None:
    state = {"tickets": {"T-1": {"status": "closed"}}}
    trajectory = Trajectory(
        turns=TURNS,
        usage=Usage(prompt_tokens=1, completion_tokens=2, latency_s=0.1),
        run_index=0,
        stop_reason="completed",
        final_state=state,
    )

    restored = trajectory_from_dict(trajectory_to_dict(trajectory))

    assert restored.final_state == state
```

Note: `TURNS`, `Trajectory`, and `Usage` are already imported at the top of `tests/records/test_serialize.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/records/test_serialize.py::test_trajectory_round_trips_final_state -q`
Expected: FAIL with `KeyError: 'final_state'` (the key is absent from the emitted dict).

- [ ] **Step 3: Emit `final_state` in `trajectory_to_dict`**

In `src/agent_eval_lab/records/serialize.py`, in `trajectory_to_dict`, add a `final_state` key to the returned dict (after `parse_failure`):

```python
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
        "final_state": (
            None
            if trajectory.final_state is None
            else dict(trajectory.final_state)
        ),
    }
```

- [ ] **Step 4: Read `final_state` in `trajectory_from_dict`**

In the same file, in `trajectory_from_dict`, add `final_state=data.get("final_state")` as the last argument:

```python
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
        final_state=data.get("final_state"),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/records/test_serialize.py -q`
Expected: PASS.

- [ ] **Step 6: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green (134 passed); ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/records/serialize.py tests/records/test_serialize.py
git commit -m "feat: round-trip Trajectory.final_state in serialization"
```

---

## Task 3: Record final state in the runner loop

**Files:**
- Modify: `src/agent_eval_lab/runners/loop.py`
- Test: `tests/runners/test_loop.py`

This is an EDGE module (I/O loop). It is tested via the existing runner tests with a stub HTTP client.

- [ ] **Step 1: Inspect the existing loop test harness**

Run: `uv run pytest tests/runners/test_loop.py -q`
Expected: existing loop tests pass. Read `tests/runners/test_loop.py` to learn the stub-client fixture pattern used (a `_stub_client` / fake `httpx.Client` that returns canned tool-call then message payloads). You will reuse that exact pattern.

- [ ] **Step 2: Write the failing test**

Add to `tests/runners/test_loop.py` a test that drives one `create_ticket` call and asserts the returned trajectory's `final_state` contains the created ticket. Mirror the existing stub pattern in that file; the canonical shape is:

```python
def test_run_single_records_final_state(stub_client_factory) -> None:
    # stub_client_factory is whatever fixture/helper the existing tests use to
    # build an httpx.Client returning scripted provider payloads. Script:
    #   response 1: assistant emits a create_ticket tool call
    #   response 2: assistant emits a terminal message
    client = stub_client_factory(
        [
            _tool_call_payload(
                name="create_ticket",
                arguments={"title": "Broken login", "priority": "high"},
            ),
            _message_payload("Created the ticket."),
        ]
    )
    task = _task(
        available_tools=("create_ticket",),
        initial_state={"tickets": {}},
        verification=OutputMatchSpec(expected_output="Created the ticket."),
    )

    trajectory = run_single(
        task=task,
        registry=WORKSPACE_TOOLS,
        config=_config(),
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
    )

    assert trajectory.final_state is not None
    assert trajectory.final_state["tickets"]["T-1"]["title"] == "Broken login"
```

IMPORTANT: Replace `stub_client_factory`, `_tool_call_payload`, `_message_payload`, `_task`, `_config`, and the imports with the EXACT helpers/fixtures already present in `tests/runners/test_loop.py`. Do not invent new helpers — reuse what the file already defines. If the file uses inline payload dicts rather than helpers, copy that inline style. The single load-bearing assertions are the last two lines.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_loop.py::test_run_single_records_final_state -q`
Expected: FAIL — `trajectory.final_state` is `None` (assertion `is not None` fails) because the loop does not yet thread state into the returned trajectory.

- [ ] **Step 4: Record `state` on the returned `Trajectory`**

In `src/agent_eval_lab/runners/loop.py`, the final `return Trajectory(...)` currently ends with `parse_failure=parse_failure,`. Add `final_state=state,` as the last argument:

```python
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
        final_state=state,
    )
```

The `state` local is already maintained through the loop via the pure `apply` calls (`state, outcome = apply(...)`), so this records the post-loop world verbatim.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_loop.py -q`
Expected: PASS.

- [ ] **Step 6: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green (135 passed); ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/runners/loop.py tests/runners/test_loop.py
git commit -m "feat: record post-loop world-state as Trajectory.final_state"
```

---

## Task 4: Add the new spec + constraint dataclasses to the schema

**Files:**
- Modify: `src/agent_eval_lab/tasks/schema.py`
- Test: `tests/tasks/test_schema.py` (create if absent)

- [ ] **Step 1: Check whether a schema test file exists**

Run: `ls tests/tasks/test_schema.py 2>/dev/null && echo EXISTS || echo MISSING`
If MISSING, create `tests/tasks/test_schema.py` with the content from Step 2. If EXISTS, append the test bodies.

- [ ] **Step 2: Write the failing tests**

Write (or append to) `tests/tasks/test_schema.py`:

```python
from agent_eval_lab.tasks.schema import (
    AllOf,
    FinalStateSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    OutputMatchSpec,
    StateContains,
    StateEquals,
    TrajectorySpec,
)


def test_final_state_spec_holds_state_constraints() -> None:
    spec = FinalStateSpec(
        constraints=(
            StateEquals(path="tickets.T-1.status", expected="closed"),
            StateContains(path="docs.ids", expected="doc-1"),
        )
    )

    assert spec.type == "final_state"
    assert spec.constraints[0].path == "tickets.T-1.status"
    assert spec.constraints[1].expected == "doc-1"


def test_trajectory_spec_holds_trajectory_constraints() -> None:
    spec = TrajectorySpec(
        constraints=(
            NoToolCall(name="delete_ticket"),
            OnlyModifies(paths=("tickets.T-1",)),
            MaxToolCalls(n=3),
        )
    )

    assert spec.type == "trajectory"
    assert spec.constraints[0].name == "delete_ticket"
    assert spec.constraints[1].paths == ("tickets.T-1",)
    assert spec.constraints[2].n == 3


def test_all_of_nests_verification_specs_recursively() -> None:
    spec = AllOf(
        specs=(
            OutputMatchSpec(expected_output="done"),
            AllOf(specs=(FinalStateSpec(constraints=()),)),
        )
    )

    assert spec.type == "all_of"
    assert isinstance(spec.specs[1], AllOf)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/tasks/test_schema.py -q`
Expected: FAIL with `ImportError: cannot import name 'FinalStateSpec'`.

- [ ] **Step 4: Add the dataclasses and widen the union**

In `src/agent_eval_lab/tasks/schema.py`, replace the block from the `OutputMatchSpec`/`ToolCallMatchSpec` definitions through the `VerificationSpec` alias. Insert the new constraint and spec dataclasses **before** the `VerificationSpec` alias and rewrite the alias. The full replacement (keep `ExpectedToolCall`, `OutputMatchSpec`, `ToolCallMatchSpec` exactly as-is; add everything below them):

```python
@dataclass(frozen=True, kw_only=True)
class StateEquals:
    type: Literal["state_equals"] = "state_equals"
    path: str
    expected: Any


@dataclass(frozen=True, kw_only=True)
class StateContains:
    type: Literal["state_contains"] = "state_contains"
    path: str
    expected: Any


StateConstraint = StateEquals | StateContains


@dataclass(frozen=True, kw_only=True)
class NoToolCall:
    type: Literal["no_tool_call"] = "no_tool_call"
    name: str


@dataclass(frozen=True, kw_only=True)
class OnlyModifies:
    type: Literal["only_modifies"] = "only_modifies"
    paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class MaxToolCalls:
    type: Literal["max_tool_calls"] = "max_tool_calls"
    n: int


TrajectoryConstraint = NoToolCall | OnlyModifies | MaxToolCalls


@dataclass(frozen=True, kw_only=True)
class FinalStateSpec:
    type: Literal["final_state"] = "final_state"
    constraints: tuple[StateConstraint, ...]


@dataclass(frozen=True, kw_only=True)
class TrajectorySpec:
    type: Literal["trajectory"] = "trajectory"
    constraints: tuple[TrajectoryConstraint, ...]


@dataclass(frozen=True, kw_only=True)
class AllOf:
    type: Literal["all_of"] = "all_of"
    specs: "tuple[VerificationSpec, ...]"


# Weeks 3-4 deterministic tier. LlmJudgeSpec (item 003) and ExecutionSpec
# (Weeks 5-6) extend this union later without breaking serialization.
VerificationSpec = (
    OutputMatchSpec | ToolCallMatchSpec | FinalStateSpec | TrajectorySpec | AllOf
)
```

Delete the old two-line comment + `VerificationSpec = OutputMatchSpec | ToolCallMatchSpec` (lines 32-34 of the original file); the block above replaces them. `AllOf.specs` uses a forward-reference string so it can name `VerificationSpec` before the alias is bound.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/tasks/test_schema.py -q`
Expected: PASS.

- [ ] **Step 6: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green (138 passed); ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/tasks/schema.py tests/tasks/test_schema.py
git commit -m "feat: add FinalStateSpec/TrajectorySpec/AllOf and constraint variants"
```

---

## Task 5: Pure state grader — dot-path walk + `_MISSING` sentinel

**Files:**
- Create: `src/agent_eval_lab/graders/state.py`
- Test: `tests/graders/test_state.py`

This task builds the `FinalStateSpec` interpreter incrementally: first the path walker, then `StateEquals`, then `StateContains`, then the spec-level grader. Each sub-step is red-green.

- [ ] **Step 1: Write the failing test for the path walker**

Create `tests/graders/test_state.py`:

```python
from agent_eval_lab.graders.state import _MISSING, resolve_path


def test_resolve_path_walks_nested_mappings() -> None:
    state = {"tickets": {"T-1": {"status": "closed"}}}

    assert resolve_path(state, "tickets.T-1.status") == "closed"


def test_resolve_path_missing_key_yields_sentinel() -> None:
    state = {"tickets": {}}

    assert resolve_path(state, "tickets.T-9.status") is _MISSING


def test_resolve_path_non_mapping_intermediate_yields_sentinel() -> None:
    state = {"tickets": {"T-1": "not-a-mapping"}}

    assert resolve_path(state, "tickets.T-1.status") is _MISSING


def test_resolve_path_over_none_state_yields_sentinel() -> None:
    assert resolve_path(None, "tickets.T-1") is _MISSING
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_state.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.graders.state'`.

- [ ] **Step 3: Implement the walker and sentinel**

Create `src/agent_eval_lab/graders/state.py`:

```python
"""Pure FinalStateSpec interpreter: dot-path walk over world-state (spec §6).

Missing paths and non-mapping intermediates degrade to a _MISSING sentinel that
fails the constraint and never raises — the executable form of "distinguish
agent failures from harness failures".
"""

from collections.abc import Mapping
from typing import Any, Final

from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.tasks.schema import (
    FinalStateSpec,
    StateConstraint,
    StateContains,
    StateEquals,
)

GRADER_ID = "final_state"


class _Missing:
    """Singleton sentinel for an unresolvable dot-path."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "<MISSING>"


_MISSING: Final = _Missing()


def resolve_path(state: Mapping[str, Any] | None, path: str) -> Any:
    """Walk `state` segment-by-segment; return _MISSING on any miss. Never raises."""
    current: Any = state
    for segment in path.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return _MISSING
        current = current[segment]
    return current
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_state.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing test for `StateEquals`/`StateContains` constraint grading**

Append to `tests/graders/test_state.py`:

```python
from agent_eval_lab.tasks.schema import StateContains, StateEquals  # noqa: E402

from agent_eval_lab.graders.state import grade_state_constraint  # noqa: E402


def test_state_equals_passes_on_match() -> None:
    state = {"tickets": {"T-1": {"status": "closed"}}}
    constraint = StateEquals(path="tickets.T-1.status", expected="closed")

    assert grade_state_constraint(constraint, state) is True


def test_state_equals_fails_on_mismatch() -> None:
    state = {"tickets": {"T-1": {"status": "open"}}}
    constraint = StateEquals(path="tickets.T-1.status", expected="closed")

    assert grade_state_constraint(constraint, state) is False


def test_state_equals_fails_on_missing_path() -> None:
    constraint = StateEquals(path="tickets.T-9.status", expected="closed")

    assert grade_state_constraint(constraint, {"tickets": {}}) is False


def test_state_contains_passes_when_member_present() -> None:
    state = {"docs": {"ids": ["doc-1", "doc-2"]}}
    constraint = StateContains(path="docs.ids", expected="doc-1")

    assert grade_state_constraint(constraint, state) is True


def test_state_contains_fails_when_member_absent() -> None:
    state = {"docs": {"ids": ["doc-2"]}}
    constraint = StateContains(path="docs.ids", expected="doc-1")

    assert grade_state_constraint(constraint, state) is False


def test_state_contains_fails_on_non_container() -> None:
    state = {"docs": {"ids": 42}}
    constraint = StateContains(path="docs.ids", expected="doc-1")

    assert grade_state_constraint(constraint, state) is False


def test_state_contains_fails_on_missing_path() -> None:
    constraint = StateContains(path="docs.ids", expected="doc-1")

    assert grade_state_constraint(constraint, {"docs": {}}) is False
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_state.py -q`
Expected: FAIL with `ImportError: cannot import name 'grade_state_constraint'`.

- [ ] **Step 7: Implement `grade_state_constraint`**

Append to `src/agent_eval_lab/graders/state.py`:

```python
def _contains(haystack: Any, needle: Any) -> bool:
    """Membership test that fails (never raises) on a non-container haystack."""
    if isinstance(haystack, (str, bytes, Mapping)) or hasattr(haystack, "__iter__"):
        try:
            return needle in haystack
        except TypeError:
            return False
    return False


def grade_state_constraint(constraint: StateConstraint, state: Mapping[str, Any] | None) -> bool:
    """Pure constraint check; True iff satisfied. Never raises."""
    value = resolve_path(state, constraint.path)
    if value is _MISSING:
        return False
    if isinstance(constraint, StateEquals):
        return value == constraint.expected
    return _contains(value, constraint.expected)
```

Note: `_contains` deliberately treats `str`/`bytes` as containers (so `StateContains` over a string substring works) but guards every membership test with `try/except TypeError` so an unhashable/incompatible pair degrades to `False` rather than raising. A non-container (e.g. `int`) without `__iter__` returns `False` immediately.

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_state.py -q`
Expected: PASS.

- [ ] **Step 9: Write the failing test for the spec-level grader**

Append to `tests/graders/test_state.py`:

```python
from agent_eval_lab.records.trajectory import Trajectory, Usage  # noqa: E402

from agent_eval_lab.graders.state import grade_final_state  # noqa: E402
from agent_eval_lab.tasks.schema import FinalStateSpec  # noqa: E402


def _trajectory(final_state):
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def test_grade_final_state_passes_when_all_constraints_hold() -> None:
    spec = FinalStateSpec(
        constraints=(StateEquals(path="tickets.T-1.status", expected="closed"),)
    )
    result = grade_final_state(
        spec=spec,
        initial_state=None,
        trajectory=_trajectory({"tickets": {"T-1": {"status": "closed"}}}),
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.failure_reason is None
    assert result.grader_id == "final_state"


def test_grade_final_state_fails_with_none_failure_reason() -> None:
    spec = FinalStateSpec(
        constraints=(StateEquals(path="tickets.T-1.status", expected="closed"),)
    )
    result = grade_final_state(
        spec=spec,
        initial_state=None,
        trajectory=_trajectory({"tickets": {"T-1": {"status": "open"}}}),
    )

    assert result.passed is False
    assert result.score == 0.0
    assert result.failure_reason is None
    assert "constraints" in result.evidence


def test_grade_final_state_missing_path_fails_without_raising() -> None:
    spec = FinalStateSpec(
        constraints=(StateEquals(path="tickets.T-9.status", expected="closed"),)
    )
    result = grade_final_state(
        spec=spec, initial_state=None, trajectory=_trajectory({"tickets": {}})
    )

    assert result.passed is False
```

- [ ] **Step 10: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_state.py -q`
Expected: FAIL with `ImportError: cannot import name 'grade_final_state'`.

- [ ] **Step 11: Implement `grade_final_state`**

Append to `src/agent_eval_lab/graders/state.py`:

```python
def grade_final_state(
    *,
    spec: FinalStateSpec,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
) -> GradeResult:
    """Grade a FinalStateSpec; a constraint miss carries failure_reason=None."""
    state = trajectory.final_state
    results = tuple(
        {
            "path": c.path,
            "type": c.type,
            "expected": c.expected,
            "actual": _evidence_value(resolve_path(state, c.path)),
            "passed": grade_state_constraint(c, state),
        }
        for c in spec.constraints
    )
    passed = all(r["passed"] for r in results)
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={"constraints": results},
        failure_reason=None,
    )


def _evidence_value(value: Any) -> Any:
    return None if value is _MISSING else value
```

The `initial_state` parameter is unused by the state grader (state lives on the trajectory) but is part of the uniform `(spec, initial_state, trajectory)` grader signature so dispatch can call every grader the same way; keep it.

- [ ] **Step 12: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_state.py -q`
Expected: PASS.

- [ ] **Step 13: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green (~152 passed); ruff clean. If `ruff check` flags the `# noqa: E402` lines, that is expected — they suppress "import not at top of file" for the incremental-append test style and are intentional.

- [ ] **Step 14: Commit**

```bash
git add src/agent_eval_lab/graders/state.py tests/graders/test_state.py
git commit -m "feat: pure FinalStateSpec grader with total dot-path resolution"
```

---

## Task 6: Pure policy grader — `NoToolCall` + `MaxToolCalls`

**Files:**
- Create: `src/agent_eval_lab/graders/policy.py`
- Test: `tests/graders/test_policy.py`

This task builds `policy.py` in two commits: call-name/count constraints here, `OnlyModifies` (leaf-diff + prefix coverage) in Task 7.

- [ ] **Step 1: Write the failing test**

Create `tests/graders/test_policy.py`:

```python
from agent_eval_lab.graders.policy import grade_trajectory_spec
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.tasks.schema import MaxToolCalls, NoToolCall, TrajectorySpec


def _trajectory(*turns, final_state=None):
    return Trajectory(
        turns=turns,
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def _call(name, **arguments):
    return ToolCall(call_id="c", name=name, arguments=arguments)


def test_no_tool_call_passes_when_absent() -> None:
    spec = TrajectorySpec(constraints=(NoToolCall(name="delete_ticket"),))
    trajectory = _trajectory(
        ToolCallTurn(tool_calls=(_call("update_ticket", ticket_id="T-1"),))
    )

    result = grade_trajectory_spec(
        spec=spec, initial_state=None, trajectory=trajectory
    )

    assert result.passed is True
    assert result.failure_reason is None


def test_no_tool_call_fails_with_forbidden_action() -> None:
    spec = TrajectorySpec(constraints=(NoToolCall(name="delete_ticket"),))
    trajectory = _trajectory(
        ToolCallTurn(tool_calls=(_call("delete_ticket", ticket_id="T-1"),))
    )

    result = grade_trajectory_spec(
        spec=spec, initial_state=None, trajectory=trajectory
    )

    assert result.passed is False
    assert result.failure_reason == "forbidden_action"


def test_max_tool_calls_passes_at_limit() -> None:
    spec = TrajectorySpec(constraints=(MaxToolCalls(n=2),))
    trajectory = _trajectory(
        ToolCallTurn(tool_calls=(_call("a"), _call("b"))),
    )

    result = grade_trajectory_spec(
        spec=spec, initial_state=None, trajectory=trajectory
    )

    assert result.passed is True


def test_max_tool_calls_fails_with_step_limit_exceeded() -> None:
    spec = TrajectorySpec(constraints=(MaxToolCalls(n=2),))
    trajectory = _trajectory(
        ToolCallTurn(tool_calls=(_call("a"), _call("b"))),
        MessageTurn(role="assistant", content="thinking"),
        ToolCallTurn(tool_calls=(_call("c"),)),
    )

    result = grade_trajectory_spec(
        spec=spec, initial_state=None, trajectory=trajectory
    )

    assert result.passed is False
    assert result.failure_reason == "step_limit_exceeded"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_policy.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.graders.policy'`.

- [ ] **Step 3: Implement the call-name/count half of the policy grader**

Create `src/agent_eval_lab/graders/policy.py`:

```python
"""Pure TrajectorySpec interpreter: policy grading over the run (spec §6).

NoToolCall / OnlyModifies breaches are forbidden_action; MaxToolCalls breaches
are step_limit_exceeded. All checks are pure functions of
(spec, initial_state, trajectory) and never raise.
"""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.grade import FailureCategory, GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import ToolCallTurn
from agent_eval_lab.tasks.schema import (
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    TrajectoryConstraint,
    TrajectorySpec,
)

GRADER_ID = "trajectory_policy"


def _all_calls(trajectory: Trajectory) -> tuple[Any, ...]:
    return tuple(
        call
        for turn in trajectory.turns
        if isinstance(turn, ToolCallTurn)
        for call in turn.tool_calls
    )


def _check_no_tool_call(
    constraint: NoToolCall, trajectory: Trajectory
) -> tuple[bool, FailureCategory | None, dict[str, Any]]:
    hit = any(call.name == constraint.name for call in _all_calls(trajectory))
    if hit:
        return False, "forbidden_action", {"forbidden_tool": constraint.name}
    return True, None, {"forbidden_tool": constraint.name}


def _check_max_tool_calls(
    constraint: MaxToolCalls, trajectory: Trajectory
) -> tuple[bool, FailureCategory | None, dict[str, Any]]:
    count = len(_all_calls(trajectory))
    evidence = {"limit": constraint.n, "observed": count}
    if count > constraint.n:
        return False, "step_limit_exceeded", evidence
    return True, None, evidence
```

- [ ] **Step 4: Write the dispatching `grade_trajectory_spec` (call-name/count only for now)**

Append to `src/agent_eval_lab/graders/policy.py`:

```python
def _check_constraint(
    constraint: TrajectoryConstraint,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
) -> tuple[bool, FailureCategory | None, dict[str, Any]]:
    if isinstance(constraint, NoToolCall):
        return _check_no_tool_call(constraint, trajectory)
    if isinstance(constraint, MaxToolCalls):
        return _check_max_tool_calls(constraint, trajectory)
    return _check_only_modifies(constraint, initial_state, trajectory)


def grade_trajectory_spec(
    *,
    spec: TrajectorySpec,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
) -> GradeResult:
    """Grade a TrajectorySpec; first failing constraint sets failure_reason."""
    checks = tuple(
        (constraint, _check_constraint(constraint, initial_state, trajectory))
        for constraint in spec.constraints
    )
    passed = all(ok for _, (ok, _, _) in checks)
    first_failure = next(
        (reason for _, (ok, reason, _) in checks if not ok), None
    )
    evidence = {
        "constraints": [
            {"type": c.type, "passed": ok, **info}
            for c, (ok, _, info) in checks
        ]
    }
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence=evidence,
        failure_reason=first_failure,
    )
```

`_check_only_modifies` is referenced here but implemented in Task 7. Until then it does not exist, so DO NOT run the policy tests after this step — proceed directly to Step 5, which adds a temporary stub so the module imports. (Task 7 replaces the stub with the real implementation.)

- [ ] **Step 5: Add a temporary `_check_only_modifies` stub so the module imports**

Append to `src/agent_eval_lab/graders/policy.py` (will be replaced in Task 7):

```python
def _check_only_modifies(
    constraint: OnlyModifies,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
) -> tuple[bool, FailureCategory | None, dict[str, Any]]:
    raise NotImplementedError  # implemented in Task 7
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_policy.py -q`
Expected: PASS (the four `NoToolCall`/`MaxToolCalls` tests; none exercise `OnlyModifies` yet).

- [ ] **Step 7: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green; ruff clean.

- [ ] **Step 8: Commit**

```bash
git add src/agent_eval_lab/graders/policy.py tests/graders/test_policy.py
git commit -m "feat: pure TrajectorySpec grader for NoToolCall and MaxToolCalls"
```

---

## Task 7: Policy grader — `OnlyModifies` leaf-diff + dot-segment prefix coverage

**Files:**
- Modify: `src/agent_eval_lab/graders/policy.py`
- Test: `tests/graders/test_policy.py`

Implements ADR-0002: diff `initial_state` vs `final_state` into changed leaf dot-paths; a change is permitted iff some declared path **equals or is a dot-segment prefix of** the changed path. `tickets.T-1` covers `tickets.T-1.status` but NOT `tickets.T-10.status`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/graders/test_policy.py`:

```python
from agent_eval_lab.graders.policy import _changed_leaf_paths, _is_covered  # noqa: E402
from agent_eval_lab.tasks.schema import OnlyModifies  # noqa: E402


def test_changed_leaf_paths_detects_value_change() -> None:
    before = {"tickets": {"T-1": {"status": "open"}}}
    after = {"tickets": {"T-1": {"status": "closed"}}}

    assert _changed_leaf_paths(before, after) == {"tickets.T-1.status"}


def test_changed_leaf_paths_detects_added_and_removed() -> None:
    before = {"a": 1, "b": 2}
    after = {"a": 1, "c": 3}

    assert _changed_leaf_paths(before, after) == {"b", "c"}


def test_is_covered_is_dot_segment_aware() -> None:
    assert _is_covered("tickets.T-1.status", ("tickets.T-1",)) is True
    assert _is_covered("tickets.T-1", ("tickets.T-1",)) is True
    assert _is_covered("tickets.T-10.status", ("tickets.T-1",)) is False


def test_only_modifies_passes_when_change_is_covered() -> None:
    spec = TrajectorySpec(constraints=(OnlyModifies(paths=("tickets.T-1",)),))
    trajectory = _trajectory(
        final_state={"tickets": {"T-1": {"status": "closed"}}}
    )
    result = grade_trajectory_spec(
        spec=spec,
        initial_state={"tickets": {"T-1": {"status": "open"}}},
        trajectory=trajectory,
    )

    assert result.passed is True


def test_only_modifies_fails_forbidden_action_when_change_outside() -> None:
    spec = TrajectorySpec(constraints=(OnlyModifies(paths=("tickets.T-1",)),))
    trajectory = _trajectory(
        final_state={
            "tickets": {
                "T-1": {"status": "closed"},
                "T-2": {"status": "closed"},
            }
        }
    )
    result = grade_trajectory_spec(
        spec=spec,
        initial_state={
            "tickets": {
                "T-1": {"status": "open"},
                "T-2": {"status": "open"},
            }
        },
        trajectory=trajectory,
    )

    assert result.passed is False
    assert result.failure_reason == "forbidden_action"


def test_only_modifies_sibling_prefix_not_covered() -> None:
    spec = TrajectorySpec(constraints=(OnlyModifies(paths=("tickets.T-1",)),))
    trajectory = _trajectory(
        final_state={"tickets": {"T-10": {"status": "closed"}}}
    )
    result = grade_trajectory_spec(
        spec=spec,
        initial_state={"tickets": {"T-10": {"status": "open"}}},
        trajectory=trajectory,
    )

    assert result.passed is False
    assert result.failure_reason == "forbidden_action"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_policy.py -q`
Expected: FAIL — `_changed_leaf_paths`/`_is_covered` not importable, and the `OnlyModifies` cases hit the `NotImplementedError` stub.

- [ ] **Step 3: Implement leaf-diff and dot-segment prefix coverage**

In `src/agent_eval_lab/graders/policy.py`, add these helpers **above** `_check_only_modifies` (after `_check_max_tool_calls`):

```python
def _leaf_paths(state: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested mapping into {dot_path: leaf_value}. Non-mappings are leaves."""
    if not isinstance(state, Mapping):
        return {prefix: state}
    if not state:
        return {prefix: {}} if prefix else {}
    leaves: dict[str, Any] = {}
    for key, value in state.items():
        child_prefix = f"{prefix}.{key}" if prefix else str(key)
        leaves.update(_leaf_paths(value, child_prefix))
    return leaves


def _changed_leaf_paths(
    before: Mapping[str, Any] | None, after: Mapping[str, Any] | None
) -> set[str]:
    """Set of leaf dot-paths whose value was added, removed, or changed."""
    before_leaves = _leaf_paths(before or {})
    after_leaves = _leaf_paths(after or {})
    keys = set(before_leaves) | set(after_leaves)
    sentinel = object()
    return {
        key
        for key in keys
        if before_leaves.get(key, sentinel) != after_leaves.get(key, sentinel)
    }


def _is_covered(changed: str, allowed: tuple[str, ...]) -> bool:
    """True iff a declared path equals or is a dot-segment prefix of `changed`."""
    segments = changed.split(".")
    for path in allowed:
        path_segments = path.split(".")
        if segments[: len(path_segments)] == path_segments:
            return True
    return False
```

- [ ] **Step 4: Replace the `_check_only_modifies` stub with the real implementation**

In `src/agent_eval_lab/graders/policy.py`, replace the stub body:

```python
def _check_only_modifies(
    constraint: OnlyModifies,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
) -> tuple[bool, FailureCategory | None, dict[str, Any]]:
    raise NotImplementedError  # implemented in Task 7
```

with:

```python
def _check_only_modifies(
    constraint: OnlyModifies,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
) -> tuple[bool, FailureCategory | None, dict[str, Any]]:
    changed = _changed_leaf_paths(initial_state, trajectory.final_state)
    violations = sorted(
        path for path in changed if not _is_covered(path, constraint.paths)
    )
    evidence = {
        "allowed": list(constraint.paths),
        "changed": sorted(changed),
        "violations": violations,
    }
    if violations:
        return False, "forbidden_action", evidence
    return True, None, evidence
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_policy.py -q`
Expected: PASS (all policy tests, including the three `OnlyModifies` cases and the dot-segment-aware coverage checks).

- [ ] **Step 6: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/graders/policy.py tests/graders/test_policy.py
git commit -m "feat: OnlyModifies leaf-diff with dot-segment prefix coverage"
```

---

## Task 8: Pure composite grader — `AllOf`

**Files:**
- Create: `src/agent_eval_lab/graders/composite.py`
- Test: `tests/graders/test_composite.py`

Implements ADR-0003: evaluate every sub-spec (no short-circuit) by recursing through `grade_trajectory`; `passed` is the AND; `failure_reason` is the first failing sub-spec's; `evidence` lists all sub-results.

To avoid a circular import (`dispatch` imports `composite`, `composite` recurses into `dispatch.grade_trajectory`), `composite.grade_all_of` takes the grader function as an injected parameter rather than importing `dispatch` at module top.

- [ ] **Step 1: Write the failing tests**

Create `tests/graders/test_composite.py`:

```python
from agent_eval_lab.graders.composite import grade_all_of
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.tasks.schema import AllOf, OutputMatchSpec


def _trajectory():
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
    )


def _grader_returning(results):
    """Build a fake grade_trajectory that returns scripted results in order."""
    calls = iter(results)

    def grade(*, verification, trajectory, registry, initial_state):
        return next(calls)

    return grade


def _result(passed, failure_reason=None, grader_id="x"):
    return GradeResult(
        grader_id=grader_id,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={},
        failure_reason=failure_reason,
    )


def test_all_of_passes_when_every_sub_result_passes() -> None:
    spec = AllOf(
        specs=(
            OutputMatchSpec(expected_output="a"),
            OutputMatchSpec(expected_output="b"),
        )
    )
    grade = _grader_returning([_result(True), _result(True)])

    result = grade_all_of(
        spec=spec,
        initial_state=None,
        trajectory=_trajectory(),
        registry={},
        grade=grade,
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.failure_reason is None
    assert len(result.evidence["sub_results"]) == 2


def test_all_of_reports_first_failure_reason_and_lists_all_sub_results() -> None:
    spec = AllOf(
        specs=(
            OutputMatchSpec(expected_output="a"),
            OutputMatchSpec(expected_output="b"),
            OutputMatchSpec(expected_output="c"),
        )
    )
    grade = _grader_returning(
        [
            _result(True),
            _result(False, failure_reason="forbidden_action"),
            _result(False, failure_reason="step_limit_exceeded"),
        ]
    )

    result = grade_all_of(
        spec=spec,
        initial_state=None,
        trajectory=_trajectory(),
        registry={},
        grade=grade,
    )

    assert result.passed is False
    assert result.score == 0.0
    assert result.failure_reason == "forbidden_action"
    assert len(result.evidence["sub_results"]) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_composite.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_eval_lab.graders.composite'`.

- [ ] **Step 3: Implement `grade_all_of`**

Create `src/agent_eval_lab/graders/composite.py`:

```python
"""Pure AllOf interpreter: conjunction over sub-specs (ADR-0003, spec §6).

Evaluates every sub-spec (no short-circuit) so the audit trail sees every
co-occurring breach; passed is the AND; failure_reason is the first failing
sub-spec's; evidence lists all sub-results. The grader function is injected to
keep this module free of a circular import with dispatch.
"""

from collections.abc import Callable, Mapping
from typing import Any

from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.tasks.schema import AllOf, VerificationSpec
from agent_eval_lab.tools.workspace import ToolDef

GRADER_ID = "all_of"

GradeFn = Callable[..., GradeResult]


def grade_all_of(
    *,
    spec: AllOf,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
    registry: Mapping[str, ToolDef],
    grade: GradeFn,
) -> GradeResult:
    """Grade AllOf by recursing `grade` over every sub-spec in declared order."""
    sub_results = tuple(
        grade(
            verification=sub,
            trajectory=trajectory,
            registry=registry,
            initial_state=initial_state,
        )
        for sub in spec.specs
    )
    passed = all(r.passed for r in sub_results)
    first_failure = next(
        (r.failure_reason for r in sub_results if not r.passed), None
    )
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={
            "sub_results": [
                {
                    "grader_id": r.grader_id,
                    "passed": r.passed,
                    "failure_reason": r.failure_reason,
                    "evidence": dict(r.evidence),
                }
                for r in sub_results
            ]
        },
        failure_reason=first_failure,
    )


# Imported for type-completeness of the VerificationSpec union the caller passes.
_ = VerificationSpec
```

Note: the `_ = VerificationSpec` line keeps the import live and documents intent; if `ruff` flags it as unused, delete that line and the `VerificationSpec` import instead — it is not load-bearing.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_composite.py -q`
Expected: PASS.

- [ ] **Step 5: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green; ruff clean. If `ruff check` flags `VerificationSpec` as unused (F401), remove its import and the `_ = VerificationSpec` line, then re-run.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/graders/composite.py tests/graders/test_composite.py
git commit -m "feat: pure AllOf grader, evaluate-all with first-failure reason"
```

---

## Task 9: Wire the three new branches into `grade_trajectory`

**Files:**
- Modify: `src/agent_eval_lab/graders/dispatch.py`
- Test: `tests/graders/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/graders/test_dispatch.py`:

```python
from agent_eval_lab.records.trajectory import Trajectory, Usage  # noqa: E402
from agent_eval_lab.records.turns import ToolCall, ToolCallTurn  # noqa: E402
from agent_eval_lab.tasks.schema import (  # noqa: E402
    AllOf,
    FinalStateSpec,
    MaxToolCalls,
    NoToolCall,
    StateEquals,
    TrajectorySpec,
)


def _state_trajectory(final_state, *turns):
    return Trajectory(
        turns=turns,
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def test_dispatches_final_state_spec() -> None:
    spec = FinalStateSpec(
        constraints=(StateEquals(path="tickets.T-1.status", expected="closed"),)
    )
    trajectory = _state_trajectory({"tickets": {"T-1": {"status": "closed"}}})

    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )

    assert result.passed is True
    assert result.grader_id == "final_state"


def test_dispatches_trajectory_spec() -> None:
    spec = TrajectorySpec(constraints=(NoToolCall(name="update_ticket"),))
    trajectory = _state_trajectory(
        None,
        ToolCallTurn(
            tool_calls=(
                ToolCall(call_id="c", name="update_ticket", arguments={}),
            )
        ),
    )

    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )

    assert result.passed is False
    assert result.failure_reason == "forbidden_action"


def test_dispatches_all_of_threading_registry_and_initial_state() -> None:
    spec = AllOf(
        specs=(
            ToolCallMatchSpec(
                expected_tool_calls=(
                    ExpectedToolCall(name="search_docs", arguments={"query": "x"}),
                )
            ),
            FinalStateSpec(
                constraints=(
                    StateEquals(path="tickets.T-1.status", expected="closed"),
                )
            ),
        )
    )
    trajectory = _state_trajectory(
        {"tickets": {"T-1": {"status": "closed"}}},
        ToolCallTurn(
            tool_calls=(
                ToolCall(call_id="c", name="search_docs", arguments={"query": "x"}),
            )
        ),
    )

    result = grade_trajectory(
        verification=spec,
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        initial_state=None,
    )

    assert result.passed is True
    assert result.grader_id == "all_of"
    assert len(result.evidence["sub_results"]) == 2


def test_unknown_spec_still_raises() -> None:
    class _Unknown:
        pass

    with pytest.raises(ValueError, match="unsupported verification spec"):
        grade_trajectory(
            verification=_Unknown(),  # type: ignore[arg-type]
            trajectory=_state_trajectory(None),
            registry=WORKSPACE_TOOLS,
        )
```

`pytest` is already imported at the top of `tests/graders/test_dispatch.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graders/test_dispatch.py -q`
Expected: FAIL — `FinalStateSpec` etc. fall through to the existing `raise ValueError("unsupported verification spec...")`, so `test_dispatches_final_state_spec` raises instead of returning a passing result.

- [ ] **Step 3: Add `initial_state` param and the three branches**

Replace the whole `grade_trajectory` function in `src/agent_eval_lab/graders/dispatch.py` and update imports. New imports block at the top of the file:

```python
"""Pure dispatch from VerificationSpec variants to their graders."""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.graders.composite import grade_all_of
from agent_eval_lab.graders.exact_match import grade_exact_match
from agent_eval_lab.graders.policy import grade_trajectory_spec
from agent_eval_lab.graders.state import grade_final_state
from agent_eval_lab.graders.tool_call import grade_tool_call_match
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import (
    AllOf,
    FinalStateSpec,
    OutputMatchSpec,
    ToolCallMatchSpec,
    TrajectorySpec,
    VerificationSpec,
)
from agent_eval_lab.tools.workspace import ToolDef
```

Keep `grade_output_match` exactly as-is. Replace `grade_trajectory`:

```python
def grade_trajectory(
    *,
    verification: VerificationSpec,
    trajectory: Trajectory,
    registry: Mapping[str, ToolDef],
    initial_state: Mapping[str, Any] | None = None,
) -> GradeResult:
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
    if isinstance(verification, AllOf):
        return grade_all_of(
            spec=verification,
            initial_state=initial_state,
            trajectory=trajectory,
            registry=registry,
            grade=grade_trajectory,
        )
    raise ValueError(f"unsupported verification spec: {verification!r}")
```

The existing `OutputMatchSpec`/`ToolCallMatchSpec` branches are byte-for-byte unchanged and ignore `initial_state`. The `AllOf` branch injects `grade_trajectory` itself as the recursion function, threading both `registry` and `initial_state`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graders/test_dispatch.py -q`
Expected: PASS (new branches plus all pre-existing dispatch tests).

- [ ] **Step 5: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/graders/dispatch.py tests/graders/test_dispatch.py
git commit -m "feat: dispatch FinalState/Trajectory/AllOf with optional initial_state"
```

---

## Task 10: Thread `initial_state` from the multi-run runner

**Files:**
- Modify: `src/agent_eval_lab/runners/multi_run.py`
- Test: `tests/runners/test_multi_run.py`

- [ ] **Step 1: Inspect the existing multi-run test**

Run: `uv run pytest tests/runners/test_multi_run.py -q`
Expected: existing tests pass. Read `tests/runners/test_multi_run.py` to learn its stub-client + task fixtures.

- [ ] **Step 2: Write the failing test**

Add a test that runs a task whose verification is a `FinalStateSpec` over the post-loop state and asserts the grade reflects it — proving `initial_state` is threaded. Reuse the file's existing stub-client/task helpers; the canonical shape:

```python
def test_run_task_k_grades_final_state_spec(stub_client_factory) -> None:
    # Script: one create_ticket call, then a terminal message.
    client = stub_client_factory(
        [
            _tool_call_payload(
                name="create_ticket",
                arguments={"title": "Bug", "priority": "low"},
            ),
            _message_payload("done"),
        ]
    )
    task = _task(
        available_tools=("create_ticket",),
        initial_state={"tickets": {}},
        verification=FinalStateSpec(
            constraints=(
                StateEquals(path="tickets.T-1.status", expected="open"),
            )
        ),
    )

    results = run_task_k(
        task=task,
        registry=WORKSPACE_TOOLS,
        config=_config(),
        http_client=client,
        k=1,
        max_steps=4,
        temperature=0.0,
    )

    assert results[0].grade.passed is True
```

IMPORTANT: replace `stub_client_factory`, `_tool_call_payload`, `_message_payload`, `_task`, `_config` with the EXACT helpers already in `tests/runners/test_multi_run.py`, and add imports for `FinalStateSpec`, `StateEquals`. The load-bearing assertion is the last line: without threading, `grade_final_state` reads `trajectory.final_state` correctly (it is recorded since Task 3) BUT a `TrajectorySpec` using `OnlyModifies` would read `initial_state`; this `FinalStateSpec` test still passes only because state is on the trajectory. To make the test genuinely fail without threading, use an `OnlyModifies` constraint instead:

```python
        verification=TrajectorySpec(
            constraints=(OnlyModifies(paths=("tickets",)),),
        ),
```

and assert `results[0].grade.passed is True`. Run BEFORE the source change to confirm it fails (because `initial_state` defaults to `None`, so the leaf-diff sees the whole final state as "added" and — since `tickets` covers `tickets.T-1...` — actually still passes). Given that subtlety, use this discriminating assertion instead: declare `OnlyModifies(paths=())` (an empty allowlist) so ANY change is forbidden, and assert the run FAILS only when `initial_state` is threaded:

```python
    task = _task(
        available_tools=("create_ticket",),
        initial_state={"tickets": {"T-1": {"status": "open"}}},
        verification=TrajectorySpec(constraints=(OnlyModifies(paths=()),)),
    )
    ...
    # With initial_state threaded, creating T-2 changes a leaf outside the
    # (empty) allowlist -> forbidden_action. Without threading, initial_state
    # is None and the diff is computed against {} -> different result.
    assert results[0].grade.failure_reason == "forbidden_action"
```

Use whichever discriminating shape the existing fixtures make cleanest; the REQUIREMENT is: the test passes only when `multi_run` threads `initial_state=task.initial_state`. Confirm via Step 3.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_multi_run.py::test_run_task_k_grades_final_state_spec -q`
Expected: FAIL — `grade_trajectory` is called without `initial_state`, so the `OnlyModifies` diff is computed against `None`/`{}` rather than the task's `initial_state`, yielding the wrong `failure_reason`.

- [ ] **Step 4: Thread `initial_state` into the grade call**

In `src/agent_eval_lab/runners/multi_run.py`, change the `grade_trajectory(...)` call inside the loop:

```python
        grade = grade_trajectory(
            verification=task.verification, trajectory=trajectory, registry=registry
        )
```

to:

```python
        grade = grade_trajectory(
            verification=task.verification,
            trajectory=trajectory,
            registry=registry,
            initial_state=task.initial_state,
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_multi_run.py -q`
Expected: PASS.

- [ ] **Step 6: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/runners/multi_run.py tests/runners/test_multi_run.py
git commit -m "feat: thread task.initial_state into grade_trajectory from multi_run"
```

---

## Task 11: Parse the new spec discriminators in `verification_from_dict`

**Files:**
- Modify: `src/agent_eval_lab/tasks/parse.py`
- Test: `tests/tasks/test_parse.py`

- [ ] **Step 1: Retarget the existing "unknown type" test (it currently uses `final_state`)**

`tests/tasks/test_parse.py::test_verification_from_dict_rejects_unknown_type` currently asserts that `{"type": "final_state", "constraints": []}` raises. Once `final_state` is a known type, that input would parse successfully and the test would wrongly fail. Change the input to a genuinely-unknown type. Replace:

```python
def test_verification_from_dict_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown verification type"):
        verification_from_dict({"type": "final_state", "constraints": []})
```

with:

```python
def test_verification_from_dict_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown verification type"):
        verification_from_dict({"type": "llm_judge", "rubric": "x"})
```

- [ ] **Step 2: Write the failing tests for the new discriminators**

Append to `tests/tasks/test_parse.py`:

```python
from agent_eval_lab.tasks.schema import (  # noqa: E402
    AllOf,
    FinalStateSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    StateContains,
    StateEquals,
    TrajectorySpec,
)


def test_verification_from_dict_parses_final_state() -> None:
    spec = verification_from_dict(
        {
            "type": "final_state",
            "constraints": [
                {
                    "type": "state_equals",
                    "path": "tickets.T-1.status",
                    "expected": "closed",
                },
                {"type": "state_contains", "path": "docs.ids", "expected": "doc-1"},
            ],
        }
    )

    assert isinstance(spec, FinalStateSpec)
    assert isinstance(spec.constraints[0], StateEquals)
    assert spec.constraints[0].path == "tickets.T-1.status"
    assert isinstance(spec.constraints[1], StateContains)
    assert spec.constraints[1].expected == "doc-1"


def test_verification_from_dict_parses_trajectory() -> None:
    spec = verification_from_dict(
        {
            "type": "trajectory",
            "constraints": [
                {"type": "no_tool_call", "name": "delete_ticket"},
                {"type": "only_modifies", "paths": ["tickets.T-1"]},
                {"type": "max_tool_calls", "n": 3},
            ],
        }
    )

    assert isinstance(spec, TrajectorySpec)
    assert isinstance(spec.constraints[0], NoToolCall)
    assert isinstance(spec.constraints[1], OnlyModifies)
    assert spec.constraints[1].paths == ("tickets.T-1",)
    assert isinstance(spec.constraints[2], MaxToolCalls)
    assert spec.constraints[2].n == 3


def test_verification_from_dict_parses_all_of_recursively() -> None:
    spec = verification_from_dict(
        {
            "type": "all_of",
            "specs": [
                {"type": "output_match", "expected_output": "done"},
                {
                    "type": "all_of",
                    "specs": [{"type": "final_state", "constraints": []}],
                },
            ],
        }
    )

    assert isinstance(spec, AllOf)
    assert isinstance(spec.specs[1], AllOf)
    assert isinstance(spec.specs[1].specs[0], FinalStateSpec)


def test_verification_from_dict_rejects_unknown_state_constraint() -> None:
    with pytest.raises(ValueError, match="unknown state constraint"):
        verification_from_dict(
            {"type": "final_state", "constraints": [{"type": "state_gt"}]}
        )


def test_verification_from_dict_rejects_unknown_trajectory_constraint() -> None:
    with pytest.raises(ValueError, match="unknown trajectory constraint"):
        verification_from_dict(
            {"type": "trajectory", "constraints": [{"type": "min_tool_calls"}]}
        )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/tasks/test_parse.py -q`
Expected: FAIL — `verification_from_dict` raises `ValueError: unknown verification type: 'final_state'` for the new cases.

- [ ] **Step 4: Implement the new parse branches**

Rewrite `src/agent_eval_lab/tasks/parse.py`. Update imports:

```python
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExpectedToolCall,
    FinalStateSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    OutputMatchSpec,
    StateConstraint,
    StateContains,
    StateEquals,
    Task,
    TaskInput,
    TaskMetadata,
    ToolCallMatchSpec,
    TrajectoryConstraint,
    TrajectorySpec,
    VerificationSpec,
)
```

Add the constraint parsers and the new spec branches. Insert these helper functions above `verification_from_dict`:

```python
def _state_constraint_from_dict(data: Mapping[str, Any]) -> StateConstraint:
    kind = data["type"]
    if kind == "state_equals":
        return StateEquals(path=data["path"], expected=data["expected"])
    if kind == "state_contains":
        return StateContains(path=data["path"], expected=data["expected"])
    raise ValueError(f"unknown state constraint: {kind!r}")


def _trajectory_constraint_from_dict(data: Mapping[str, Any]) -> TrajectoryConstraint:
    kind = data["type"]
    if kind == "no_tool_call":
        return NoToolCall(name=data["name"])
    if kind == "only_modifies":
        return OnlyModifies(paths=tuple(data["paths"]))
    if kind == "max_tool_calls":
        return MaxToolCalls(n=data["n"])
    raise ValueError(f"unknown trajectory constraint: {kind!r}")
```

Then extend `verification_from_dict` — add these branches before the final `raise`:

```python
    if kind == "final_state":
        return FinalStateSpec(
            constraints=tuple(
                _state_constraint_from_dict(c) for c in data["constraints"]
            )
        )
    if kind == "trajectory":
        return TrajectorySpec(
            constraints=tuple(
                _trajectory_constraint_from_dict(c) for c in data["constraints"]
            )
        )
    if kind == "all_of":
        return AllOf(
            specs=tuple(verification_from_dict(s) for s in data["specs"])
        )
    raise ValueError(f"unknown verification type: {kind!r}")
```

The existing `output_match` and `tool_call_match` branches stay byte-for-byte unchanged. `all_of` recurses through `verification_from_dict` so nested composites parse.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/tasks/test_parse.py -q`
Expected: PASS (new branches + the retargeted unknown-type test + all pre-existing parse tests).

- [ ] **Step 6: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/tasks/parse.py tests/tasks/test_parse.py
git commit -m "feat: parse final_state/trajectory/all_of verification discriminators"
```

---

## Task 12: Extend the golden conformance harness

**Files:**
- Modify: `tests/test_golden_conformance.py`

This task updates the harness only (thread `initial_state`, bump the count). The new JSON cases land in Task 13; the count assertion is set to the final total (22) here, so this task's `test_golden_suite_is_present` will FAIL until Task 13 adds the 11 new files. That is the intended red. (Alternatively, do Task 13 first; the plan orders harness-then-cases so the count assertion documents the target.)

- [ ] **Step 1: Update the harness**

In `tests/test_golden_conformance.py`, change the count assertion:

```python
def test_golden_suite_is_present() -> None:
    assert len(GOLDEN_CASES) == 11
```

to:

```python
def test_golden_suite_is_present() -> None:
    assert len(GOLDEN_CASES) == 22
```

And thread `initial_state` into the grade call:

```python
    grade = grade_trajectory(
        verification=verification_from_dict(case["verification"]),
        trajectory=trajectory_from_dict(case["trajectory"]),
        registry=WORKSPACE_TOOLS,
    )
```

becomes:

```python
    grade = grade_trajectory(
        verification=verification_from_dict(case["verification"]),
        trajectory=trajectory_from_dict(case["trajectory"]),
        registry=WORKSPACE_TOOLS,
        initial_state=case.get("initial_state"),
    )
```

- [ ] **Step 2: Run to confirm the expected red on the count assertion**

Run: `uv run pytest tests/test_golden_conformance.py::test_golden_suite_is_present -q`
Expected: FAIL — `assert 11 == 22` (only 11 golden files exist so far). The 11 existing per-case conformance tests still PASS (threading `initial_state=None` for cases without the key changes nothing). This red is resolved by Task 13.

- [ ] **Step 3: Do NOT commit yet**

Leave this uncommitted; commit together with Task 13 (the harness change and the cases it requires form one logical unit). Proceed to Task 13.

---

## Task 13: Add the 11 hand-verified golden cases

**Files:**
- Create: 11 JSON files under `tests/golden/` (`12_*` … `22_*`).
- Modify (commit together): `tests/test_golden_conformance.py` (from Task 12).

Each case carries `verification`, `trajectory` (with `final_state` where the grader reads world-state), an optional top-level `initial_state` (threaded by the harness), and the hand-verified `expected` `{passed, failure_reason}`. Coverage maps to spec criterion 10 (a)-(j). Create each file exactly as shown.

- [ ] **Step 1: `tests/golden/12_final_state_equals_pass.json`** (criterion 10a)

```json
{
  "name": "final_state state_equals matches the closed ticket",
  "verification": {"type": "final_state", "constraints": [{"type": "state_equals", "path": "tickets.T-1.status", "expected": "closed"}]},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"ticket_id": "T-1", "status": "closed"}}}
  ], "final_state": {"tickets": {"T-1": {"title": "Bug", "priority": "high", "status": "closed"}}}},
  "expected": {"passed": true, "failure_reason": null}
}
```

- [ ] **Step 2: `tests/golden/13_final_state_equals_fail.json`** (criterion 10b)

```json
{
  "name": "final_state state_equals misses when ticket still open (failure_reason null)",
  "verification": {"type": "final_state", "constraints": [{"type": "state_equals", "path": "tickets.T-1.status", "expected": "closed"}]},
  "trajectory": {"turns": [], "final_state": {"tickets": {"T-1": {"title": "Bug", "priority": "high", "status": "open"}}}},
  "expected": {"passed": false, "failure_reason": null}
}
```

- [ ] **Step 3: `tests/golden/14_final_state_missing_path.json`** (criterion 10c)

```json
{
  "name": "final_state over a missing path fails without crashing",
  "verification": {"type": "final_state", "constraints": [{"type": "state_equals", "path": "tickets.T-9.status", "expected": "closed"}]},
  "trajectory": {"turns": [], "final_state": {"tickets": {}}},
  "expected": {"passed": false, "failure_reason": null}
}
```

- [ ] **Step 4: `tests/golden/15_state_contains_pass.json`** (criterion 10d, success)

```json
{
  "name": "state_contains passes when the doc id is present",
  "verification": {"type": "final_state", "constraints": [{"type": "state_contains", "path": "docs.found", "expected": "doc-1"}]},
  "trajectory": {"turns": [], "final_state": {"docs": {"found": ["doc-1", "doc-2"]}}},
  "expected": {"passed": true, "failure_reason": null}
}
```

- [ ] **Step 5: `tests/golden/16_state_contains_fail.json`** (criterion 10d, failure)

```json
{
  "name": "state_contains fails when the doc id is absent",
  "verification": {"type": "final_state", "constraints": [{"type": "state_contains", "path": "docs.found", "expected": "doc-1"}]},
  "trajectory": {"turns": [], "final_state": {"docs": {"found": ["doc-2"]}}},
  "expected": {"passed": false, "failure_reason": null}
}
```

- [ ] **Step 6: `tests/golden/17_no_tool_call_forbidden.json`** (criterion 10e)

```json
{
  "name": "no_tool_call breach emits forbidden_action",
  "verification": {"type": "trajectory", "constraints": [{"type": "no_tool_call", "name": "update_ticket"}]},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"ticket_id": "T-1", "status": "closed"}}}
  ], "final_state": {"tickets": {"T-1": {"status": "closed"}}}},
  "expected": {"passed": false, "failure_reason": "forbidden_action"}
}
```

- [ ] **Step 7: `tests/golden/18_max_tool_calls_step_limit.json`** (criterion 10f)

```json
{
  "name": "max_tool_calls breach emits step_limit_exceeded",
  "verification": {"type": "trajectory", "constraints": [{"type": "max_tool_calls", "n": 1}]},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "search_docs", "arguments": {"query": "a"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"doc_ids": []}}},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c2", "name": "search_docs", "arguments": {"query": "b"}}]},
    {"type": "tool_result", "call_id": "c2", "outcome": {"type": "success", "result": {"doc_ids": []}}}
  ], "final_state": {}},
  "expected": {"passed": false, "failure_reason": "step_limit_exceeded"}
}
```

- [ ] **Step 8: `tests/golden/19_only_modifies_breach.json`** (criterion 10g)

```json
{
  "name": "only_modifies breach: a ticket outside the allowed subtree changed",
  "verification": {"type": "trajectory", "constraints": [{"type": "only_modifies", "paths": ["tickets.T-1"]}]},
  "initial_state": {"tickets": {"T-1": {"status": "open"}, "T-2": {"status": "open"}}},
  "trajectory": {"turns": [], "final_state": {"tickets": {"T-1": {"status": "closed"}, "T-2": {"status": "closed"}}}},
  "expected": {"passed": false, "failure_reason": "forbidden_action"}
}
```

- [ ] **Step 9: `tests/golden/20_path_independence_a.json`** (criterion 10h, path A)

```json
{
  "name": "path-independence A: search-then-update reaches the closed state",
  "verification": {"type": "final_state", "constraints": [{"type": "state_equals", "path": "tickets.T-1.status", "expected": "closed"}]},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "search_docs", "arguments": {"query": "T-1"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"doc_ids": ["doc-1"]}}},
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c2", "name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}}]},
    {"type": "tool_result", "call_id": "c2", "outcome": {"type": "success", "result": {"ticket_id": "T-1", "status": "closed"}}}
  ], "final_state": {"tickets": {"T-1": {"status": "closed"}}}},
  "expected": {"passed": true, "failure_reason": null}
}
```

- [ ] **Step 10: `tests/golden/21_path_independence_b.json`** (criterion 10h, path B)

```json
{
  "name": "path-independence B: direct update reaches the same closed state",
  "verification": {"type": "final_state", "constraints": [{"type": "state_equals", "path": "tickets.T-1.status", "expected": "closed"}]},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"ticket_id": "T-1", "status": "closed"}}}
  ], "final_state": {"tickets": {"T-1": {"status": "closed"}}}},
  "expected": {"passed": true, "failure_reason": null}
}
```

- [ ] **Step 11: `tests/golden/22_all_of_conjunction.json`** (criteria 10i + 10j)

This single `all_of` case covers BOTH the all-pass nesting structure (10i, via a passing sub-spec) AND the multi-failure conjunction (10j): two sub-specs fail; the recorded `failure_reason` is the first failing sub-spec's (`forbidden_action` from the `no_tool_call`), and `evidence.sub_results` lists all three.

```json
{
  "name": "all_of: passing output_match then two failing policy sub-specs; first-failure reason wins",
  "verification": {"type": "all_of", "specs": [
    {"type": "final_state", "constraints": [{"type": "state_equals", "path": "tickets.T-1.status", "expected": "closed"}]},
    {"type": "trajectory", "constraints": [{"type": "no_tool_call", "name": "update_ticket"}]},
    {"type": "trajectory", "constraints": [{"type": "max_tool_calls", "n": 0}]}
  ]},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"ticket_id": "T-1", "status": "closed"}}}
  ], "final_state": {"tickets": {"T-1": {"status": "closed"}}}},
  "expected": {"passed": false, "failure_reason": "forbidden_action"}
}
```

Hand-verification of case 22: sub-spec 1 (`final_state` T-1 closed) → **passes**. Sub-spec 2 (`no_tool_call update_ticket`) → the trajectory calls `update_ticket` → **fails, `forbidden_action`**. Sub-spec 3 (`max_tool_calls n=0`) → one tool call > 0 → **fails, `step_limit_exceeded`**. `passed` = AND = `false`. First failing sub-spec in declared order is #2 → `failure_reason = "forbidden_action"`. `evidence.sub_results` has 3 entries. The harness asserts only `passed` and `failure_reason`; both match.

- [ ] **Step 12: Add an explicit all-pass `all_of` golden case for 10i**

To make criterion 10i (`AllOf` all-pass success) an independent oracle (case 22 is all-fail-dominated), add `tests/golden/23_all_of_all_pass.json`. (This makes the suite 23 cases — update the count accordingly; see Step 13.)

```json
{
  "name": "all_of all-pass: final_state and trajectory policy both satisfied",
  "verification": {"type": "all_of", "specs": [
    {"type": "final_state", "constraints": [{"type": "state_equals", "path": "tickets.T-1.status", "expected": "closed"}]},
    {"type": "trajectory", "constraints": [{"type": "max_tool_calls", "n": 3}, {"type": "no_tool_call", "name": "delete_ticket"}]}
  ]},
  "trajectory": {"turns": [
    {"type": "tool_call", "content": null, "tool_calls": [{"call_id": "c1", "name": "update_ticket", "arguments": {"ticket_id": "T-1", "status": "closed"}}]},
    {"type": "tool_result", "call_id": "c1", "outcome": {"type": "success", "result": {"ticket_id": "T-1", "status": "closed"}}}
  ], "final_state": {"tickets": {"T-1": {"status": "closed"}}}},
  "expected": {"passed": true, "failure_reason": null}
}
```

Hand-verification: sub-spec 1 passes (T-1 closed); sub-spec 2 passes (1 call ≤ 3, no `delete_ticket`). `passed` = `true`, `failure_reason` = `null`.

- [ ] **Step 13: Fix the suite-size assertion to the true total**

There are now 12 new cases (`12`…`23`), making 23 total. Update `tests/test_golden_conformance.py`:

```python
def test_golden_suite_is_present() -> None:
    assert len(GOLDEN_CASES) == 22
```

becomes:

```python
def test_golden_suite_is_present() -> None:
    assert len(GOLDEN_CASES) == 23
```

- [ ] **Step 14: Run the golden suite**

Run: `uv run pytest tests/test_golden_conformance.py -q`
Expected: PASS — 1 presence test + 23 per-case tests = 24 passing. If any per-case fails, the printed assertion message names the case and shows `passed`/`failure_reason` actual-vs-expected; reconcile the JSON against the hand-verification notes above (do not change grader logic to fit a case without re-deriving the oracle).

- [ ] **Step 15: Run the canonical gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all green (well above 130 total); ruff clean. JSON files are not linted by ruff.

- [ ] **Step 16: Commit (harness + all cases together)**

```bash
git add tests/test_golden_conformance.py tests/golden/12_final_state_equals_pass.json \
  tests/golden/13_final_state_equals_fail.json tests/golden/14_final_state_missing_path.json \
  tests/golden/15_state_contains_pass.json tests/golden/16_state_contains_fail.json \
  tests/golden/17_no_tool_call_forbidden.json tests/golden/18_max_tool_calls_step_limit.json \
  tests/golden/19_only_modifies_breach.json tests/golden/20_path_independence_a.json \
  tests/golden/21_path_independence_b.json tests/golden/22_all_of_conjunction.json \
  tests/golden/23_all_of_all_pass.json
git commit -m "test: golden conformance cases for FinalState/Trajectory/AllOf"
```

---

## Task 14: Final full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the complete canonical gate triple**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Expected:
- `pytest`: all green; total well above 130 (baseline 130 + new unit tests in `test_state.py`, `test_policy.py`, `test_composite.py`, `test_schema.py`, the new dispatch/parse/serialize/trajectory/loop/multi_run tests, and 12 new golden per-case tests).
- `ruff check .`: `All checks passed!`
- `ruff format --check .`: `N files already formatted`.

- [ ] **Step 2: Confirm all 11 original golden cases still pass unchanged**

Run: `uv run pytest "tests/test_golden_conformance.py" -q -k "exact_sequence or malformed or schema_violation or wrong_tool or wrong_args or missing_call or extra_call or order_mismatch or multiset or output_match"`
Expected: the original cases (`01`…`11`) all PASS — no v1 grading regression.

- [ ] **Step 3: Confirm no source file lost its frozen/kw_only discipline**

Run: `uv run ruff check src/agent_eval_lab/graders/state.py src/agent_eval_lab/graders/policy.py src/agent_eval_lab/graders/composite.py`
Expected: `All checks passed!`. Visually confirm each new dataclass in `schema.py` is `@dataclass(frozen=True, kw_only=True)` and each grader function takes no mutable default and mutates no argument.

- [ ] **Step 4: Commit the plan file itself is already done by the orchestrator; nothing to commit here.**

This task adds no code. If Steps 1-3 are all green, the item is complete.

---

## Self-Review (completed by plan author)

**Spec coverage** — every acceptance criterion maps to a task:
- Criterion 1 (union extension) → Task 4.
- Criterion 2 (final-state threading + serialize round-trip) → Tasks 1, 2, 3.
- Criterion 3 (pure state grader, total dot-path) → Task 5.
- Criterion 4 (pure trajectory grader; `OnlyModifies` dot-segment prefix) → Tasks 6, 7.
- Criterion 5 (`AllOf` conjunction) → Task 8.
- Criterion 6 (dispatch wiring, optional `initial_state`, `AllOf` threads `registry`+`initial_state`) → Task 9.
- Criterion 7 (runner pass-through) → Task 10.
- Criterion 8 (JSONL parsing incl. unknown-type/constraint raises) → Task 11.
- Criterion 9 (failure-category mapping; `FinalStateSpec` miss → `None`) → Tasks 5, 6, 7 (asserted in their tests + golden cases 13/14/16 carry `failure_reason: null`).
- Criterion 10 (golden extension a–j) → Tasks 12, 13.
- Criterion 11 (backward compat; canonical gates) → every task's gate step + Task 14.

**Known spec-gap judgment calls (flagged for the impl agent):**
1. The existing `tests/tasks/test_parse.py::test_verification_from_dict_rejects_unknown_type` used `"final_state"` as its *unknown-type* fixture. Once `final_state` is known, that fixture is wrong. Criterion 8 says unknown types still raise but does not flag this collision. Task 11 Step 1 retargets it to `"llm_judge"` (a genuinely-unknown, item-003 type). This is the minimal change that preserves the test's intent.
2. Criterion 10 enumerates cases (a)-(j) "at minimum"; (i) all-pass `AllOf` and (j) multi-fail `AllOf` are best served by two distinct files, so the plan ships 12 new cases (23 total) rather than 11 (22). The harness count assertion is set to 23 accordingly. The grill's "bump from 11 to the new total" wording permits any total above 11.
3. `grade_all_of` injects the recursion function (`grade=grade_trajectory`) rather than importing `dispatch` to avoid a circular import (`dispatch` → `composite` → `dispatch`). The spec's "recurses through `grade_trajectory`" (criterion 5) is honored; the injection is an implementation detail invisible to callers.
4. The `final_state` golden cases hand-author `trajectory.final_state` directly (the grader reads it off the trajectory per ADR-0001) rather than replaying tools, which is exactly the self-contained replay-artifact contract the golden suite relies on.

**Type consistency** — verified: `resolve_path`, `_MISSING`, `grade_state_constraint`, `grade_final_state` (state); `grade_trajectory_spec`, `_changed_leaf_paths`, `_is_covered`, `_check_only_modifies` (policy); `grade_all_of` (composite); `grade_trajectory(..., initial_state=...)` (dispatch) — names match across every task that references them. All new specs use `@dataclass(frozen=True, kw_only=True)` with `type` discriminators matching the parser's string literals.
