# Item 002 — `max_rounds` plumbing + recorded policy fields — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the agent loop a real per-domain turn budget (`max_rounds`), record the configured policy (`max_rounds` / `safety_cap` / `max_rounds_bound`) on every trajectory, retire the two defensive `getattr` reads, and split resource-vs-time aggregation honestly — `safety_cap` demoted to a backstop, runner-level `max_steps` argument superseded (ADR-0017).

**Architecture:** `run_single` (loop.py) gains a `max_rounds: int | None` argument checked at the **end** of each iteration beside the existing `safety_cap` check (so the turn's tool calls are kept; a `max_rounds` stop means the model was still editing). `Trajectory` gains three record fields, round-tripped by `serialize.py` with backward-compatible defaults. A new pure per-domain resolver (`runners/round_budget.py`) resolves `metadata.max_rounds` (task) over a per-domain default `{F:20, D:50}`, threaded into `make_f_run_fn` and `dset_run`. `ExperimentSpec`/`ConditionDef` schema is **untouched** (record-level change only), so frozen M1 specs keep verifying.

**Tech Stack:** Python 3.12, `uv run pytest`, frozen `@dataclass(kw_only=True)` value objects, `httpx.MockTransport` stub loops (no provider calls — §G2), ruff for lint/format.

---

## Orientation — read before starting

- **Spec:** `docs/2026-06-15-harness-rounds-f-ablation/items/002-spec.md`
- **Carry-forwards (mandatory):** `docs/2026-06-15-harness-rounds-f-ablation/items/001-review.md` — CF1 (serialize round-trip test for `max_rounds_bound=True`), CF2 (swap two `getattr` for direct attribute access), N3 (`"max_rounds"` into the `stop_reason` Literal).
- **Design:** `docs/superpowers/specs/2026-06-15-agentic-v1-harness-rounds-F-ablation-design.md` — Part A (A.1/A.2/A.3), §9.2, §D.3, §11.2/§11.3.
- **ADR:** `docs/adr/0017-loop-budget-is-safety-cap-plus-max-rounds-runner-max-steps-superseded.md`

**Ground truth (line numbers verified at plan time):**
- `src/agent_eval_lab/runners/loop.py` — `run_single` signature at L81-95 (`safety_cap: int = 200` at L93); flags initialized at L110-111 (`stop_reason = "completed_natural"`, `safety_cap_bound = False`); `rounds += 1` at L142; `completed_natural` natural-break at L161-163; safety-cap check at L178-181; `Trajectory(...)` construction at L200-218 (`safety_cap_bound=safety_cap_bound` at L215).
- `src/agent_eval_lab/records/trajectory.py` — `stop_reason` Literal at L50-60; `safety_cap_bound` field at L76-77; `v1_compat` at L83-102.
- `src/agent_eval_lab/records/serialize.py` — `trajectory_to_dict` at L100-135 (`"safety_cap_bound"` key at L125); `trajectory_from_dict` at L138-181 (`safety_cap_bound=...` at L178).
- `src/agent_eval_lab/experiments/aggregate.py` — `EfficiencySummary` at L105-111 (`n_censored` doc at L110); `efficiency_summary` at L114-131 (`n_censored=sum(...)` at L129).
- `src/agent_eval_lab/metrics/reliability.py` — `_run_passes` at L21-33; the defensive read at L32.
- `src/agent_eval_lab/reports/classify.py` — `_cap_bound` at L123-137; the defensive read at L135; `_CAP_STOP_REASONS` at L120.
- `src/agent_eval_lab/runners/f_candidate.py` — `make_f_run_fn` at L132-159 (`safety_cap: int = 60` at L139; `run_single(...)` at L145-157).
- `src/agent_eval_lab/runners/dset_run.py` — `run_dset` at L47-103; `run_task_k_valid(...)` call at L86-100 (`max_steps=0` at L93).
- `src/agent_eval_lab/runners/multi_run.py` — `_run_one` at L49-83 (`run_single(...)` at L63-75, no `safety_cap`/`max_rounds` passed); `run_task_k_valid` at L146-... (`max_steps: int` at L154).
- `src/agent_eval_lab/tasks/schema.py` — `TaskMetadata` at L196-204 (`max_steps: int | None = None` at L203).
- `src/agent_eval_lab/tasks/parse.py` — metadata parse at ~L177 (`max_steps=data.get("max_steps")`).
- `src/agent_eval_lab/experiments/evaluator_config.py` — `RunnerConfig` at L53-57 (runtime config — NOT the frozen spec).

**Decision (judgment call — see report):** per-domain `max_rounds` config lives in a NEW pure resolver module `runners/round_budget.py`, **NOT** on `ExperimentSpec`. The spec docstring at `experiments/schema.py:3-5` forbids modifying `ExperimentSpec`/`ConditionDef` field signatures, and the item-002 spec (Constraints) requires `verify_spec_hash` to keep passing as a *record-level* change. Adding a spec field would re-hash the frozen M1 spec. The resolver reads the per-task `metadata.max_rounds` override (new `TaskMetadata` field) over a per-domain default dict.

**House conventions:**
- All `uv run` commands run from the repo root `/Users/snow/Documents/Repository/agent-eval-lab`.
- `Trajectory` is `frozen=True, kw_only=True`; construct with keywords only.
- Do NOT create a feature branch or push — the orchestrator owns branch/PR/push.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/agent_eval_lab/records/trajectory.py` | add `"max_rounds"` stop_reason literal + 3 record fields | Modify |
| `src/agent_eval_lab/records/serialize.py` | round-trip the 3 new fields (safe defaults) | Modify |
| `src/agent_eval_lab/runners/loop.py` | `max_rounds` arg + end-of-iteration check + record fields | Modify |
| `src/agent_eval_lab/metrics/reliability.py` | CF2: direct attribute read | Modify |
| `src/agent_eval_lab/reports/classify.py` | CF2: direct attribute read | Modify |
| `src/agent_eval_lab/experiments/aggregate.py` | §D.3: `n_censored` includes `max_rounds_bound`; doc the split | Modify |
| `src/agent_eval_lab/tasks/schema.py` | `TaskMetadata.max_rounds: int | None = None` | Modify |
| `src/agent_eval_lab/tasks/parse.py` | parse `max_rounds` from task metadata dict | Modify |
| `src/agent_eval_lab/runners/round_budget.py` | NEW pure per-domain `max_rounds` resolver | Create |
| `src/agent_eval_lab/runners/f_candidate.py` | thread `max_rounds` into `make_f_run_fn`/`run_single` | Modify |
| `src/agent_eval_lab/runners/multi_run.py` | thread `safety_cap`/`max_rounds` through `_run_one`/`run_task_k_valid` | Modify |
| `src/agent_eval_lab/runners/dset_run.py` | resolve + thread `max_rounds` (D default 50) into `run_task_k_valid` | Modify |
| `tests/runners/test_loop.py` | loop bound + ordering tests | Modify |
| `tests/records/test_trajectory.py` | new-field defaults + `"max_rounds"` literal | Modify |
| `tests/records/test_serialize.py` | CF1 round-trip + back-compat tests | Modify |
| `tests/metrics/test_reliability.py` | CF2 direct-read still censors | Modify (or create) |
| `tests/reports/test_classify.py` | CF2 direct-read still classifies `budget_exhausted` | Modify (or create) |
| `tests/experiments/test_aggregate_efficiency.py` | §D.3 `max_rounds_bound` censoring + tokens-over-all | Modify |
| `tests/runners/test_round_budget.py` | NEW resolver tests (task > domain) | Create |
| `tests/runners/test_f_candidate.py` | `make_f_run_fn` threads `max_rounds` | Modify |
| `tests/runners/test_dset_run.py` | `run_dset` threads resolved `max_rounds` | Modify |

---

## Task 1 — `Trajectory`: `"max_rounds"` literal + 3 recorded policy fields

**Files:**
- Modify: `src/agent_eval_lab/records/trajectory.py:50-77`
- Test: `tests/records/test_trajectory.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/records/test_trajectory.py` (the `_trajectory` helper at top already exists; reuse it):

```python
def test_trajectory_accepts_max_rounds_stop_reason() -> None:
    assert _trajectory(stop_reason="max_rounds").stop_reason == "max_rounds"


def test_trajectory_round_policy_fields_default_safely() -> None:
    t = _trajectory(stop_reason="completed_natural")
    assert t.max_rounds is None
    assert t.safety_cap is None
    assert t.max_rounds_bound is False


def test_trajectory_records_round_policy_fields() -> None:
    t = _trajectory(
        stop_reason="max_rounds",
        max_rounds=20,
        safety_cap=200,
        max_rounds_bound=True,
    )
    assert t.max_rounds == 20
    assert t.safety_cap == 200
    assert t.max_rounds_bound is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/records/test_trajectory.py::test_trajectory_records_round_policy_fields tests/records/test_trajectory.py::test_trajectory_accepts_max_rounds_stop_reason -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'max_rounds'` (and the literal test fails type-checking only, not at runtime, so rely on the field tests for red).

- [ ] **Step 3: Add the literal + fields**

In `src/agent_eval_lab/records/trajectory.py`, extend the `stop_reason` Literal (L50-60) — add `"max_rounds"` to the censoring-contract block:

```python
    stop_reason: Literal[
        # legacy values — never emitted by the censoring runner, kept parseable
        # for v1 artifacts (records+runner revision §7 / item 001 scope A)
        "completed",
        "max_steps",
        "parse_failure",
        # censoring-contract values emitted by the new runner
        "completed_natural",
        "safety_cap",
        "max_rounds",
        "env_unhealthy",
    ]
```

Then add three fields immediately after `safety_cap_bound` (after L77, before `env_health`):

```python
    safety_cap_bound: bool = False
    """True iff the run stopped because it reached the safety cap (D35)."""
    max_rounds: int | None = None
    """The per-run turn budget in effect (model turns); None ⇒ unbounded (§A.2)."""
    safety_cap: int | None = None
    """The tool-call backstop in effect; recorded so an artifact proves its policy."""
    max_rounds_bound: bool = False
    """True iff the run stopped because it reached max_rounds (§A.2/§D.1)."""
```

(`v1_compat` needs no change — it constructs via keywords and the three new fields default safely; legacy artifacts stay `max_rounds=None`/`safety_cap=None`/`max_rounds_bound=False`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/records/test_trajectory.py -v`
Expected: PASS (all, including the existing `test_trajectory_accepts_new_stop_reasons`).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/records/trajectory.py tests/records/test_trajectory.py
git commit -m "feat(002): Trajectory gains max_rounds stop_reason + 3 policy fields"
```

---

## Task 2 — `serialize.py`: round-trip the 3 new fields (CF1)

**Files:**
- Modify: `src/agent_eval_lab/records/serialize.py:122-135` (to_dict), `:166-181` (from_dict)
- Test: `tests/records/test_serialize.py`

- [ ] **Step 1: Write the failing CF1 + back-compat tests**

Add to `tests/records/test_serialize.py` (imports `Trajectory`, `Usage`, `trajectory_from_dict`, `trajectory_to_dict` already present; `TURNS` constant exists in-file):

```python
def test_max_rounds_bound_survives_round_trip_cf1() -> None:
    # CF1 (001 review, P1): without this, a genuinely max-rounds-capped run
    # silently deserializes to max_rounds_bound=False and is scored as a
    # reliable pass^k pass instead of budget_exhausted.
    trajectory = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason="max_rounds",
        rounds=20,
        tool_call_counts={"str_replace": 20},
        safety_cap_bound=False,
        max_rounds=20,
        safety_cap=200,
        max_rounds_bound=True,
    )
    restored = trajectory_from_dict(trajectory_to_dict(trajectory))
    assert restored.stop_reason == "max_rounds"
    assert restored.max_rounds_bound is True
    assert restored.max_rounds == 20
    assert restored.safety_cap == 200
    assert restored == trajectory


def test_old_v2_record_without_round_policy_keys_defaults_safely() -> None:
    # Backward compat: a schema_version="2" dict written before item 002 has
    # none of the three new keys; it must deserialize with safe defaults.
    d = {
        "schema_version": "2",
        "turns": [],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "latency_s": 0.0},
        "run_index": 0,
        "stop_reason": "completed_natural",
        "parse_failure": None,
        "final_state": None,
        "rounds": 3,
        "wall_time_s": 1.0,
        "tool_call_counts": {},
        "safety_cap_bound": False,
        "env_health": None,
        "run_uid": None,
    }
    t = trajectory_from_dict(d)
    assert t.max_rounds is None
    assert t.safety_cap is None
    assert t.max_rounds_bound is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/records/test_serialize.py::test_max_rounds_bound_survives_round_trip_cf1 -v`
Expected: FAIL — `AssertionError: assert False is True` (the deserializer drops `max_rounds_bound`, so it defaults `False`).

- [ ] **Step 3: Add the three keys to both directions**

In `src/agent_eval_lab/records/serialize.py` `trajectory_to_dict`, add three keys to the `d` dict right after the `"safety_cap_bound"` line (L125):

```python
        "safety_cap_bound": trajectory.safety_cap_bound,
        "max_rounds": trajectory.max_rounds,
        "safety_cap": trajectory.safety_cap,
        "max_rounds_bound": trajectory.max_rounds_bound,
```

In `trajectory_from_dict`, add three keyword args to the `Trajectory(...)` return right after `safety_cap_bound=...` (L178):

```python
        safety_cap_bound=data.get("safety_cap_bound", False),
        max_rounds=data.get("max_rounds"),
        safety_cap=data.get("safety_cap"),
        max_rounds_bound=data.get("max_rounds_bound", False),
```

(The v1 branch at L153-164 is untouched — `v1_compat` already defaults all three.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/records/test_serialize.py -v`
Expected: PASS (all, including the existing `test_trajectory_round_trips_all_new_fields` and `test_v2_dict_round_trip_is_idempotent_on_disk_keys`).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/records/serialize.py tests/records/test_serialize.py
git commit -m "feat(002): serialize round-trips max_rounds/safety_cap/max_rounds_bound (CF1)"
```

---

## Task 3 — `run_single`: `max_rounds` arg + end-of-iteration bound (stub loop, §G2)

**Files:**
- Modify: `src/agent_eval_lab/runners/loop.py:81-218`
- Test: `tests/runners/test_loop.py`

- [ ] **Step 1: Write the failing tests**

`tests/runners/test_loop.py` already has `_always_tool_call_client()` (L426-438) — a `httpx.MockTransport` handler that returns a fresh tool call every turn so the loop NEVER naturally completes. This IS the stub loop the spec mandates (no provider calls — §G2). Reuse it for the cap test; add a scripted client for the ordering test. Append:

```python
def test_loop_stops_at_max_rounds_keeping_the_turns_work() -> None:
    # Stub loop (§G2): always returns a tool call, so only max_rounds stops it.
    # Checked at END of iteration, so the cap-th round's tool call is applied
    # and kept (the model was still editing — uncommitted/incomplete).
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_always_tool_call_client(),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
        max_rounds=3,
        safety_cap=200,  # backstop far above max_rounds, so max_rounds wins
    )
    assert trajectory.stop_reason == "max_rounds"
    assert trajectory.max_rounds_bound is True
    assert trajectory.safety_cap_bound is False
    assert trajectory.rounds == 3  # stopped exactly at the cap
    # the 3rd round's tool call was applied before the break (turn's work kept)
    assert sum(trajectory.tool_call_counts.values()) == 3


def test_loop_natural_completion_breaks_before_max_rounds() -> None:
    # A model that finishes in 2 rounds (tool call, then final message) stops
    # at completed_natural BEFORE the max_rounds=5 cap — so a max_rounds stop
    # genuinely means "still editing at the cap", never a natural finish.
    responses = [
        _tool_call_response("search_docs", {"query": "x"}, "c1"),
        _final_response("done"),
    ]
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_scripted_client(responses),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
        max_rounds=5,
    )
    assert trajectory.stop_reason == "completed_natural"
    assert trajectory.max_rounds_bound is False
    assert trajectory.rounds == 2


def test_loop_unbounded_when_max_rounds_none_records_policy_none() -> None:
    responses = [_final_response("hi")]
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_scripted_client(responses),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )
    assert trajectory.stop_reason == "completed_natural"
    assert trajectory.max_rounds is None
    assert trajectory.max_rounds_bound is False
    assert trajectory.safety_cap == 200  # default backstop recorded


def test_max_rounds_default_is_none() -> None:
    import inspect

    sig = inspect.signature(run_single)
    assert sig.parameters["max_rounds"].default is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runners/test_loop.py::test_loop_stops_at_max_rounds_keeping_the_turns_work tests/runners/test_loop.py::test_max_rounds_default_is_none -v`
Expected: FAIL — `TypeError: run_single() got an unexpected keyword argument 'max_rounds'`.

- [ ] **Step 3: Add the argument, the flag, the end-of-iteration check, and the record fields**

In `src/agent_eval_lab/runners/loop.py`:

(a) Add `max_rounds` to the signature right after `safety_cap` (L93):

```python
    safety_cap: int = 200,
    max_rounds: int | None = None,
    health_probe_fn: "Callable[[], EnvHealth] | None" = None,
```

(b) Initialize the bound flag beside `safety_cap_bound` (after L111):

```python
    stop_reason = "completed_natural"
    safety_cap_bound = False
    max_rounds_bound = False
```

(c) Add the end-of-iteration check immediately AFTER the safety-cap block (after L181, still inside `while True`). Order matters: natural completion already broke at L161-163; the safety-cap check is at L178-181; append the max_rounds check last so the round's tool calls are already applied:

```python
        if sum(tool_call_counts.values()) >= safety_cap:
            stop_reason = "safety_cap"
            safety_cap_bound = True
            break
        if max_rounds is not None and rounds >= max_rounds:
            stop_reason = "max_rounds"
            max_rounds_bound = True
            break
```

(d) Record the three policy fields on the returned `Trajectory` — add to the construction right after `safety_cap_bound=safety_cap_bound,` (L215):

```python
        safety_cap_bound=safety_cap_bound,
        max_rounds=max_rounds,
        safety_cap=safety_cap,
        max_rounds_bound=max_rounds_bound,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/runners/test_loop.py -v`
Expected: PASS (all, including existing `test_loop_stops_at_safety_cap`, `test_safety_cap_default_is_200`, `test_loop_completes_naturally_emits_completed_natural`).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/loop.py tests/runners/test_loop.py
git commit -m "feat(002): run_single max_rounds turn-bound at end of iteration"
```

---

## Task 4 — CF2: retire the two defensive `getattr` reads

**Files:**
- Modify: `src/agent_eval_lab/metrics/reliability.py:21-33`
- Modify: `src/agent_eval_lab/reports/classify.py:123-137`
- Test: `tests/metrics/test_reliability.py`, `tests/reports/test_classify.py`

- [ ] **Step 1: Write the guard tests**

The point of CF2: now that the field always exists (default `False`), a future rename becomes a loud `AttributeError`, not a silent `False`. Tests must prove the censor/classify still fire on a real `max_rounds_bound=True` trajectory. Add to `tests/metrics/test_reliability.py` (create the file if absent, mirroring the existing `RunResult`/`Trajectory`/`Usage`/`GradeResult` construction in `tests/experiments/test_aggregate_efficiency.py`):

```python
from agent_eval_lab.metrics.reliability import pass_pow_k
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _run(*, passed: bool, max_rounds_bound: bool) -> RunResult:
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason="max_rounds" if max_rounds_bound else "completed_natural",
        rounds=20,
        max_rounds_bound=max_rounds_bound,
    )
    return RunResult(
        task_id="t",
        condition_id="c",
        run_index=0,
        trajectory=traj,
        grade=GradeResult(grader_id="g", passed=passed, score=1.0, evidence={}),
    )


def test_graded_pass_but_max_rounds_capped_is_censored() -> None:
    # A graded-correct-but-capped run is NOT a reliable pass^k pass (§D.1).
    results = [_run(passed=True, max_rounds_bound=True)]
    assert pass_pow_k(results) == 0.0


def test_graded_pass_uncapped_passes() -> None:
    results = [_run(passed=True, max_rounds_bound=False)]
    assert pass_pow_k(results) == 1.0
```

Add to `tests/reports/test_classify.py` (mirror the file's existing `RunResult` construction; if a `_run`/builder helper exists, reuse it):

```python
def test_passed_but_max_rounds_capped_classifies_budget_exhausted() -> None:
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.reports.classify import classify_run

    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason="max_rounds",
        rounds=20,
        max_rounds_bound=True,
    )
    run = RunResult(
        task_id="t",
        condition_id="c",
        run_index=0,
        trajectory=traj,
        grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}),
    )
    result = classify_run(run)
    # budget_exhausted is a SUBCATEGORY under category "agent_failure"
    # (classify.py: RunClassification has .category + .subcategory; fc-v4 row at
    # _classify_grade_and_budget — a passed=True+cap_bound run falls through the
    # row-1 guard `if run.grade.passed and not cap_bound` into the cap branch).
    assert result.category == "agent_failure"
    assert result.subcategory == "budget_exhausted"
```

- [ ] **Step 2: Run tests to verify they pass already (green — defensive read still works)**

Run: `uv run pytest tests/metrics/test_reliability.py tests/reports/test_classify.py -v`
Expected: PASS — these pass under the current `getattr` read too. They are *guard* tests that must STAY green after the refactor. (If `test_classify.py`'s assertion name was wrong, fix it now until green.)

- [ ] **Step 3: Swap `getattr` for direct attribute access**

In `src/agent_eval_lab/metrics/reliability.py`, `_run_passes` (L32), replace:

```python
    capped = traj.safety_cap_bound or getattr(traj, "max_rounds_bound", False)
```

with:

```python
    capped = traj.safety_cap_bound or traj.max_rounds_bound
```

Also update the `_run_passes` docstring (L24-29) — drop the "read DEFENSIVELY (default False) … arrives in item 002" sentence and state the field is now a real `Trajectory` attribute (item 002). Suggested replacement for that sentence:

```python
    Enforces the pass_pow_k MetricDef's declared censoring_policy="failure"
    (§D.1). Both safety_cap_bound and max_rounds_bound are real Trajectory
    fields (item 002); a future rename now raises AttributeError (loud) rather
    than silently reading False. The censor is GLOBAL by design (§10.6): D/B
    inherit it through this shared module and the Fisher-F path in
    comparisons.py, which both route through task_reliability.
```

In `src/agent_eval_lab/reports/classify.py`, `_cap_bound` (L133-137), replace:

```python
    return (
        traj.safety_cap_bound
        or getattr(traj, "max_rounds_bound", False)
        or traj.stop_reason in _CAP_STOP_REASONS
    )
```

with:

```python
    return (
        traj.safety_cap_bound
        or traj.max_rounds_bound
        or traj.stop_reason in _CAP_STOP_REASONS
    )
```

Also update the `_cap_bound` docstring (L126-128) — drop "max_rounds_bound arrives in item 002, so it is read DEFENSIVELY (default False)" and state both flags are real fields now. Suggested:

```python
    Reads the safety_cap_bound and max_rounds_bound flags (both real Trajectory
    fields as of item 002) and the two cap stop reasons. Legacy max_steps is a
    TRUNCATION (step_exhaustion), NOT a budget cap (D2), so it is deliberately
    excluded here.
```

- [ ] **Step 4: Run tests to verify they still pass (and item-001 stays green)**

Run: `uv run pytest tests/metrics/test_reliability.py tests/reports/test_classify.py -v`
Expected: PASS (the guard tests stay green; the swap is behavior-preserving because the field always exists with default `False`).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/metrics/reliability.py src/agent_eval_lab/reports/classify.py tests/metrics/test_reliability.py tests/reports/test_classify.py
git commit -m "refactor(002): direct max_rounds_bound read in reliability + classify (CF2)"
```

---

## Task 5 — §D.3 aggregate split: `n_censored` includes `max_rounds_bound`

**Files:**
- Modify: `src/agent_eval_lab/experiments/aggregate.py:105-131`
- Test: `tests/experiments/test_aggregate_efficiency.py`

- [ ] **Step 1: Write the failing tests**

The existing `_run` helper at `tests/experiments/test_aggregate_efficiency.py:10-26` only takes `safety_cap`. Extend the helper and add tests. First widen the helper (modify L10-19):

```python
def _run(rounds, prompt, completion, wall, safety_cap=False, max_rounds=False):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=prompt, completion_tokens=completion, latency_s=wall),
        run_index=0,
        stop_reason=(
            "safety_cap" if safety_cap else "max_rounds" if max_rounds else "completed_natural"
        ),
        rounds=rounds,
        wall_time_s=wall,
        safety_cap_bound=safety_cap,
        max_rounds_bound=max_rounds,
    )
    return RunResult(
        task_id="t",
        condition_id="m1",
        run_index=0,
        trajectory=traj,
        grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}),
    )
```

Then append:

```python
def test_efficiency_summary_counts_max_rounds_as_censored():
    # §D.3: n_censored includes max_rounds_bound, not only safety_cap_bound.
    runs = [_run(3, 10, 5, 1.0), _run(20, 99, 99, 30.0, max_rounds=True)]
    s = efficiency_summary(outcomes=(_outcome(runs),))
    assert s.n_censored == 1


def test_efficiency_summary_tokens_include_capped_runs():
    # §D.3: resource (tokens) is fully spent even on capped runs -> summed over ALL.
    runs = [_run(3, 10, 5, 1.0), _run(20, 40, 20, 30.0, max_rounds=True)]
    s = efficiency_summary(outcomes=(_outcome(runs),))
    assert s.total_tokens == (10 + 40) + (5 + 20)  # capped run's tokens included
    assert s.n_censored == 1
    assert s.n_runs == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/experiments/test_aggregate_efficiency.py::test_efficiency_summary_counts_max_rounds_as_censored -v`
Expected: FAIL — `assert 0 == 1` (`n_censored` currently counts only `safety_cap_bound`).

- [ ] **Step 3: Widen `n_censored` and document the §D.3 split**

In `src/agent_eval_lab/experiments/aggregate.py`, update the `EfficiencySummary` docstring/comment (L107-111) and the `n_censored` sum (L129).

Replace the `n_censored` field comment (L110):

```python
    n_censored: int  # valid runs right-censored by a budget cap
    # (safety_cap_bound OR max_rounds_bound, §D.3/D35)
```

Replace the `efficiency_summary` `n_censored=` line (L129):

```python
        n_censored=sum(
            1
            for r in runs
            if r.trajectory.safety_cap_bound or r.trajectory.max_rounds_bound
        ),
```

Add a one-line clarifying comment above the `return EfficiencySummary(` at L125 to encode §D.3 (resource over all, time censored):

```python
    # §D.3 split: total_tokens is summed over ALL runs (resource is spent even on
    # capped runs); median_rounds / median_wall_time_s are time-to-completion and
    # are right-censored — they are LOWER BOUNDS once n_censored > 0.
    return EfficiencySummary(
```

(No change to `total_tokens` / `median_rounds` / `median_wall_time_s` computation: `token_totals(runs)` already sums over all runs incl. capped — §D.3 resource side is already correct.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/experiments/test_aggregate_efficiency.py -v`
Expected: PASS (all, including existing `test_efficiency_summary_counts_safety_cap_as_censored`).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/experiments/aggregate.py tests/experiments/test_aggregate_efficiency.py
git commit -m "feat(002): n_censored counts max_rounds_bound; document D.3 split"
```

---

## Task 6 — `TaskMetadata.max_rounds` field + parse

**Files:**
- Modify: `src/agent_eval_lab/tasks/schema.py:196-204`
- Modify: `src/agent_eval_lab/tasks/parse.py:~177`
- Test: `tests/tasks/test_parse.py` (find the metadata-parse test; if absent, add a focused one)

- [ ] **Step 1: Write the failing test**

Locate the existing metadata-parse test. Confirm the test module:

Run: `uv run python -c "import glob; print([p for p in glob.glob('tests/tasks/*.py') if 'parse' in p])"`
Expected: a path such as `tests/tasks/test_parse.py`.

Add to that file (reuse its existing `parse_task` import and a minimal task dict from the file; the snippet below is self-contained):

```python
def test_parse_task_reads_metadata_max_rounds() -> None:
    from agent_eval_lab.tasks.parse import parse_task

    task = parse_task(
        {
            "id": "t1",
            "capability": "edit",
            "input": {"messages": [{"type": "message", "role": "user", "content": "x"}],
                       "available_tools": []},
            "verification": {"type": "tool_call_match", "expected_tool_calls": [],
                              "match": "exact_sequence"},
            "metadata": {"split": "dev", "version": "1", "provenance": "hand",
                          "max_rounds": 40},
        }
    )
    assert task.metadata.max_rounds == 40


def test_parse_task_defaults_metadata_max_rounds_none() -> None:
    from agent_eval_lab.tasks.parse import parse_task

    task = parse_task(
        {
            "id": "t1",
            "capability": "edit",
            "input": {"messages": [{"type": "message", "role": "user", "content": "x"}],
                       "available_tools": []},
            "verification": {"type": "tool_call_match", "expected_tool_calls": [],
                              "match": "exact_sequence"},
            "metadata": {"split": "dev", "version": "1", "provenance": "hand"},
        }
    )
    assert task.metadata.max_rounds is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tasks/test_parse.py::test_parse_task_reads_metadata_max_rounds -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'max_rounds'` (after parse passes it) or `AttributeError` (max_rounds not on TaskMetadata).

- [ ] **Step 3: Add the field + parse it**

In `src/agent_eval_lab/tasks/schema.py`, `TaskMetadata` (after L203):

```python
    max_steps: int | None = None
    max_rounds: int | None = None
    review: str | None = None
```

In `src/agent_eval_lab/tasks/parse.py`, at the metadata construction (~L177, beside `max_steps=data.get("max_steps")`):

```python
        max_steps=data.get("max_steps"),
        max_rounds=data.get("max_rounds"),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/tasks/test_parse.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/tasks/schema.py src/agent_eval_lab/tasks/parse.py tests/tasks/test_parse.py
git commit -m "feat(002): TaskMetadata.max_rounds override field + parse"
```

---

## Task 7 — Pure per-domain `max_rounds` resolver (task > domain)

**Files:**
- Create: `src/agent_eval_lab/runners/round_budget.py`
- Test: `tests/runners/test_round_budget.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/runners/test_round_budget.py`:

```python
import pytest

from agent_eval_lab.runners.round_budget import (
    DOMAIN_MAX_ROUNDS,
    resolve_max_rounds,
)
from agent_eval_lab.tasks.parse import parse_task


def _task(*, max_rounds=None):
    meta = {"split": "dev", "version": "1", "provenance": "hand"}
    if max_rounds is not None:
        meta["max_rounds"] = max_rounds
    return parse_task(
        {
            "id": "t1",
            "capability": "edit",
            "input": {"messages": [{"type": "message", "role": "user", "content": "x"}],
                       "available_tools": []},
            "verification": {"type": "tool_call_match", "expected_tool_calls": [],
                              "match": "exact_sequence"},
            "metadata": meta,
        }
    )


def test_default_per_domain_caps():
    assert DOMAIN_MAX_ROUNDS == {"F": 20, "D": 50}


def test_domain_default_used_when_no_task_override():
    assert resolve_max_rounds(domain="F", task=_task()) == 20
    assert resolve_max_rounds(domain="D", task=_task()) == 50


def test_task_override_wins_over_domain_default():
    assert resolve_max_rounds(domain="F", task=_task(max_rounds=40)) == 40
    assert resolve_max_rounds(domain="D", task=_task(max_rounds=7)) == 7


def test_unknown_domain_falls_back_to_task_override_or_none():
    # B is config-only/deferred (no live runner); an unmapped domain returns the
    # task override if present, else None (unbounded — never invents a cap).
    assert resolve_max_rounds(domain="B", task=_task()) is None
    assert resolve_max_rounds(domain="B", task=_task(max_rounds=12)) == 12
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/runners/test_round_budget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.runners.round_budget'`.

- [ ] **Step 3: Write the resolver**

Create `src/agent_eval_lab/runners/round_budget.py`:

```python
"""Pure per-domain `max_rounds` resolution (ADR-0017, §A.2/§11.3).

The user-facing turn budget. A per-task `metadata.max_rounds` override WINS over
the per-domain default; an unmapped domain (B is config-only/deferred — §9.9)
yields the task override if present, else None (unbounded — never invent a cap).
Lives here, NOT on ExperimentSpec: adding a spec field would re-hash the frozen
M1 spec (experiments/schema.py forbids field changes; verify_spec_hash must keep
passing — item-002 spec Constraints). This is a runtime resolver, not pre-reg.
"""

from __future__ import annotations

from agent_eval_lab.tasks.schema import Task

# Per-domain defaults (ADR-0017 Decision): code 20, browser 50. The F-ablation
# pins {F:40} at its own experiment level (item 003+), not here.
DOMAIN_MAX_ROUNDS: dict[str, int] = {"F": 20, "D": 50}


def resolve_max_rounds(*, domain: str, task: Task) -> int | None:
    """Resolution order: task override (`metadata.max_rounds`) > domain default.

    Returns None (unbounded) for an unmapped domain with no task override.
    """
    override = task.metadata.max_rounds
    if override is not None:
        return override
    return DOMAIN_MAX_ROUNDS.get(domain)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/runners/test_round_budget.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/round_budget.py tests/runners/test_round_budget.py
git commit -m "feat(002): pure per-domain max_rounds resolver (task > domain)"
```

---

## Task 8 — Thread `max_rounds` into `make_f_run_fn` (F edit loop)

**Files:**
- Modify: `src/agent_eval_lab/runners/f_candidate.py:132-159`
- Test: `tests/runners/test_f_candidate.py`

- [ ] **Step 1: Write the failing test**

`make_f_run_fn` returns a `run_fn(edit_task, run_index)` that calls `run_single`. The cleanest unit test stubs `run_single` (monkeypatch) and asserts the resolved `max_rounds` is forwarded. Add to `tests/runners/test_f_candidate.py`:

```python
def test_make_f_run_fn_forwards_max_rounds(monkeypatch) -> None:
    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.records.trajectory import Trajectory, Usage

    captured = {}

    def fake_run_single(**kwargs):
        captured["max_rounds"] = kwargs.get("max_rounds")
        captured["safety_cap"] = kwargs.get("safety_cap")
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(fc, "run_single", fake_run_single)

    run_fn = fc.make_f_run_fn(
        config=CONFIG,                 # reuse the module's CONFIG/test fixture
        http_client=DUMMY_CLIENT,      # reuse the module's client fixture
        temperature=0.0,
        max_tokens=4096,
        condition_id="cond__bare",
        safety_cap=200,
        max_rounds=40,
    )
    run_fn(EDIT_TASK, 0)               # reuse the module's edit-task fixture
    assert captured["max_rounds"] == 40
    assert captured["safety_cap"] == 200
```

> Before writing: open `tests/runners/test_f_candidate.py` and reuse its existing `CONFIG`, client, and edit-task fixtures (names may differ — `DUMMY_CLIENT`/`EDIT_TASK` are placeholders for whatever the file already defines). If the file builds a client via `httpx.Client(transport=httpx.MockTransport(...))`, reuse that.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_f_candidate.py::test_make_f_run_fn_forwards_max_rounds -v`
Expected: FAIL — `TypeError: make_f_run_fn() got an unexpected keyword argument 'max_rounds'`.

- [ ] **Step 3: Add `max_rounds` to `make_f_run_fn` and forward it**

In `src/agent_eval_lab/runners/f_candidate.py`, extend the signature (after `safety_cap: int = 60` at L139):

```python
    condition_id: str,
    safety_cap: int = 60,
    max_rounds: int | None = None,
) -> Callable[[Task, int], Trajectory]:
```

And forward it in the inner `run_single(...)` call (after `safety_cap=safety_cap,` at L156):

```python
            run_uid=f"{condition_id}__f__{run_index:04d}",
            safety_cap=safety_cap,
            max_rounds=max_rounds,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_f_candidate.py -v`
Expected: PASS (all).

- [ ] **Step 5: Wire the CLI `run-f` call to resolve via the resolver**

In `src/agent_eval_lab/cli.py` `make_f_run_fn(...)` call (~L898-906), pass a resolved `max_rounds`. Because `make_f_run_fn` is arm-wide (not per-task) while the resolver is per-task, the F default is uniform per domain, so resolve against the F domain default with no task (override only applies per-task in the loop — F uses the domain default here). Add `max_rounds=DOMAIN_MAX_ROUNDS["F"]` and import it:

```python
    from agent_eval_lab.runners.round_budget import DOMAIN_MAX_ROUNDS
    ...
    run_fn = make_f_run_fn(
        config=...,
        http_client=...,
        temperature=...,
        max_tokens=...,
        condition_id=...,
        safety_cap=cfg.runner.safety_cap,
        max_rounds=DOMAIN_MAX_ROUNDS["F"],
    )
```

> Read the exact current `make_f_run_fn(...)` call args at cli.py:898 first and add only the `max_rounds=` keyword + the import. Do not alter the other args.

- [ ] **Step 6: Run the runners suite to confirm no regression**

Run: `uv run pytest tests/runners/ -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/runners/f_candidate.py src/agent_eval_lab/cli.py tests/runners/test_f_candidate.py
git commit -m "feat(002): thread max_rounds into make_f_run_fn + run-f CLI (F=20)"
```

---

## Task 9 — Thread `safety_cap` + `max_rounds` through `multi_run` into `run_single`

**Files:**
- Modify: `src/agent_eval_lab/runners/multi_run.py:49-83` (`_run_one`), `:146-...` (`run_task_k_valid`)
- Test: `tests/runners/test_multi_run.py`

- [ ] **Step 1: Write the failing test**

`_run_one` is the single place `run_task_k_valid` calls `run_single`, but it currently passes neither `safety_cap` nor `max_rounds`. Thread both as keyword args (defaulting to the `run_single` defaults so existing call sites are unaffected). Add to `tests/runners/test_multi_run.py`:

```python
def test_run_task_k_valid_forwards_max_rounds(monkeypatch) -> None:
    import agent_eval_lab.runners.multi_run as mr
    from agent_eval_lab.records.trajectory import Trajectory, Usage

    captured = {}

    def fake_run_single(**kwargs):
        captured["max_rounds"] = kwargs.get("max_rounds")
        captured["safety_cap"] = kwargs.get("safety_cap")
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(mr, "run_single", fake_run_single)
    monkeypatch.setattr(mr, "_grade_one", lambda **k: GRADE_PASS)  # reuse fixture

    mr.run_task_k_valid(
        task=TASK,                 # reuse the module's TASK fixture
        registry=REGISTRY,         # reuse the module's registry fixture
        config=CONFIG,
        http_client=DUMMY_CLIENT,
        k_valid=1,
        max_invalid_rate=0.4,
        max_steps=0,
        temperature=0.0,
        max_tokens=4096,
        safety_cap=123,
        max_rounds=50,
    )
    assert captured["max_rounds"] == 50
    assert captured["safety_cap"] == 123
```

> Reuse the test module's existing fixtures (`TASK`, `REGISTRY`, `CONFIG`, a mock client, and a passing `GradeResult` for `GRADE_PASS`). Names are placeholders — inspect the file and substitute.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_multi_run.py::test_run_task_k_valid_forwards_max_rounds -v`
Expected: FAIL — `TypeError: run_task_k_valid() got an unexpected keyword argument 'safety_cap'`.

- [ ] **Step 3: Thread the two args through `_run_one` and `run_task_k_valid`**

In `src/agent_eval_lab/runners/multi_run.py`:

(a) `_run_one` (L49-62) — add two keyword params after `health_probe_fn` and forward them in the `run_single(...)` call (L63-75):

```python
    health_probe_fn: "Callable[[], EnvHealth] | None",
    safety_cap: int = 200,
    max_rounds: int | None = None,
) -> RunResult:
    trajectory = run_single(
        task=task,
        registry=registry,
        config=config,
        http_client=http_client,
        run_index=run_index,
        temperature=temperature,
        max_tokens=max_tokens,
        apply_fn=apply_fn,
        executor=executor,
        run_uid=f"{condition}__{run_index:04d}",
        health_probe_fn=health_probe_fn,
        safety_cap=safety_cap,
        max_rounds=max_rounds,
    )
```

(b) `run_task_k_valid` (L146-161) — add `safety_cap: int = 200` and `max_rounds: int | None = None` to the signature (after `max_steps: int,`), and pass both into the `_run_one(...)` call at L174-186:

```python
            executor=executor,
            health_probe_fn=health_probe_fn,
            safety_cap=safety_cap,
            max_rounds=max_rounds,
        )
```

(c) Leave `run_task_k` (L86-118) unchanged — it is the back-compat non-replacement path; its `max_steps` is unaffected (the `metadata.max_steps` data field stays untouched; only the runner-level *argument* is superseded, and `run_task_k` already documents `max_steps` is no longer a loop bound).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_multi_run.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/multi_run.py tests/runners/test_multi_run.py
git commit -m "feat(002): thread safety_cap + max_rounds through multi_run loop"
```

---

## Task 10 — Resolve + thread `max_rounds` into `dset_run` (D=50)

**Files:**
- Modify: `src/agent_eval_lab/runners/dset_run.py:47-103`
- Test: `tests/runners/test_dset_run.py`

- [ ] **Step 1: Write the failing test**

`run_dset` builds the per-task executor then calls `run_task_k_valid`. The D-domain `max_rounds` must be the resolved value (task override > D default 50). Add to `tests/runners/test_dset_run.py`:

```python
def test_run_dset_threads_resolved_max_rounds(monkeypatch) -> None:
    import agent_eval_lab.runners.dset_run as dr

    captured = {}

    def fake_run_task_k_valid(**kwargs):
        captured.setdefault("max_rounds", []).append(kwargs.get("max_rounds"))
        return REPLACEMENT_OUTCOME  # reuse a void/non-void fixture

    monkeypatch.setattr(dr, "run_task_k_valid", fake_run_task_k_valid)
    # stub the bash executor so no real session is opened
    monkeypatch.setattr(dr, "make_bash_executor", lambda **k: (object(), lambda: None))

    list(
        dr.run_dset(
            evaluator_store=TMP_STORE,         # tmp_path-based fixture
            tasks=(D_TASK_DEFAULT, D_TASK_OVERRIDE_7),  # one default, one metadata.max_rounds=7
            config=CONFIG,
            http_client=DUMMY_CLIENT,
            k_valid=1,
            max_invalid_rate=0.4,
            temperature=0.0,
            max_tokens=4096,
        )
    )
    # first task uses the D domain default (50); second uses its task override (7)
    assert captured["max_rounds"] == [50, 7]
```

> Reuse / construct: `D_TASK_DEFAULT` = a D-domain task with no `metadata.max_rounds`; `D_TASK_OVERRIDE_7` = same with `metadata.max_rounds=7`. Build via `parse_task` mirroring the file's existing task fixtures. `REPLACEMENT_OUTCOME` = a non-void `ReplacementOutcome` (reuse the module's helper or build a minimal one).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/runners/test_dset_run.py::test_run_dset_threads_resolved_max_rounds -v`
Expected: FAIL — `TypeError: run_task_k_valid() got an unexpected keyword argument 'max_rounds'` is NOT it (Task 9 added it); instead FAIL — `assert None == 50` because `run_dset` does not yet resolve/pass `max_rounds` (it defaults `None`).

- [ ] **Step 3: Resolve + pass `max_rounds` per task**

In `src/agent_eval_lab/runners/dset_run.py`, import the resolver at the top:

```python
from agent_eval_lab.runners.round_budget import resolve_max_rounds
```

In the per-task loop (the `run_task_k_valid(...)` call at L86-100), resolve and pass `max_rounds` (the D backstop `safety_cap` stays the runtime config default — `run_task_k_valid` already defaults `safety_cap=200`, the code-200 backstop; do not override it here unless the runtime config carries one):

```python
            outcome = run_task_k_valid(
                task=task,
                registry=BROWSE_TOOLS,
                config=config,
                http_client=http_client,
                k_valid=k_valid,
                max_invalid_rate=max_invalid_rate,
                max_steps=0,  # unused: the censoring safety cap governs
                temperature=temperature,
                max_tokens=max_tokens,
                validity_fn=validity_fn,
                health_probe_fn=health_probe_fn,
                apply_fn=apply_browse,
                executor=executor,
                max_rounds=resolve_max_rounds(domain="D", task=task),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/runners/test_dset_run.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/dset_run.py tests/runners/test_dset_run.py
git commit -m "feat(002): dset_run resolves + threads D max_rounds (default 50)"
```

---

## Task 11 — Confirm frozen M1 specs still verify + full suite + lint

**Files:** none changed — verification only.

- [ ] **Step 1: Confirm `verify_spec_hash` on the frozen M1 spec still passes**

The item-002 change is record-level (`Trajectory`/serialize/`TaskMetadata`) and adds a new resolver module; `ExperimentSpec`/`ConditionDef` field signatures are untouched, so the stored M1 `spec_hash` recomputes identically.

Run: `uv run pytest tests/experiments/test_spec_hash.py tests/experiments/test_m1_spec.py -v`
Expected: PASS — including `test_verify_spec_hash_true_for_frozen` and `test_m1_spec.py`'s `verify_spec_hash(frozen)` assertion.

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS — no failures, no errors. (Item-001 censor/classifier tests stay green: the field is now always present with default `False`, so CF2's direct read is behavior-preserving.)

- [ ] **Step 3: Lint + format check**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!` and no files needing reformatting. If `ruff format --check` reports diffs, run `uv run ruff format .`, re-run the suite (Step 2), and amend the relevant commit.

- [ ] **Step 4: Final verification commit (only if formatting changed anything)**

```bash
git add -A
git commit -m "chore(002): ruff format after max_rounds plumbing"
```

---

## Self-Review (run after all tasks)

**Spec coverage — every acceptance criterion maps to a task:**
- Loop turn-bound, end-of-iteration, `"max_rounds"` literal (§A.1/A.2 + N3) → Tasks 1, 3.
- Natural completion breaks earlier (ordering test) → Task 3 (`test_loop_natural_completion_breaks_before_max_rounds`).
- 3 recorded policy fields (§9.2) → Task 1.
- CF1 serialize round-trip incl. `max_rounds_bound=True` → Task 2.
- CF2 direct attribute access (reliability + classify), item-001 tests stay green → Task 4.
- Per-domain default `{F:20, D:50}` + per-task override (task > domain) → Tasks 6, 7.
- `safety_cap` stays a higher backstop (code 200 / browser ~300) → Tasks 8/9/10 keep `safety_cap` defaults; resolver only sets `max_rounds`.
- Threaded into `make_f_run_fn` + `dset_run`; B config-only/deferred → Tasks 8, 10 (B unmapped → resolver returns None; no B loop built).
- Runner-level `max_steps` argument superseded; `metadata.max_steps` data field untouched → Task 9 leaves `run_task_k`/`max_steps`/`metadata.max_steps` alone (only the *argument* is no longer a loop bound, already the case).
- §D.3 split: resource over ALL incl. capped; rounds/wall-time censored; `n_censored` includes `max_rounds_bound` → Task 5.
- `verify_spec_hash` still passes (record-level) → Task 11.
- Backward compat (old records default safely) → Tasks 1, 2 (`test_old_v2_record_without_round_policy_keys_defaults_safely`, `v1_compat` unchanged).

**Placeholder scan:** test fixture names flagged with `>` notes (`DUMMY_CLIENT`, `EDIT_TASK`, `REGISTRY`, `GRADE_PASS`, `D_TASK_*`, `REPLACEMENT_OUTCOME`, `.category`) are explicitly called out to be resolved against the actual test files before writing — not silent TBDs. All production code blocks are complete.

**Type consistency:** `max_rounds: int | None`, `safety_cap: int | None`, `max_rounds_bound: bool` are spelled identically across `Trajectory` (Task 1), serialize keys (Task 2), `run_single` (Task 3), `multi_run` (Task 9). `resolve_max_rounds(*, domain, task)` and `DOMAIN_MAX_ROUNDS` (Task 7) are used verbatim in Tasks 8/10. `make_f_run_fn(..., max_rounds=...)` matches its call site (Task 8).

---

## Execution Handoff

The orchestrator owns the branch and PR/push. Execute tasks in order; each task is independently committable and leaves the suite green.
